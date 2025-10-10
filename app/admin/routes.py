import random
from markupsafe import Markup
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app
from app import supabase
from app.admin.utils import admin_required

admin = Blueprint('admin', __name__, template_folder='templates')

@admin.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == current_app.config['ADMIN_PASSWORD']:
            session['is_admin'] = True
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Senha incorreta.', 'danger')
    return render_template('admin/login.html')

@admin.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('admin.login'))

@admin.route('/dashboard')
@admin_required
def dashboard():
    teams_res = supabase.table('teams').select('*, players(*)').execute()
    matches_res = supabase.table('matches').select('*, team1:team1_id(*), team2:team2_id(*), winner:winner_id(*)').order('round_number').order('match_in_round').execute()

    # Organiza as partidas por rodada para facilitar a renderização
    bracket_data = {1: [], 2: [], 3: []}
    for match in matches_res.data:
        if match['round_number'] in bracket_data:
            bracket_data[match['round_number']].append(match)

    return render_template('admin/dashboard.html', teams=teams_res.data, bracket=bracket_data)

@admin.route('/generate-bracket', methods=['POST'])
@admin_required
def generate_bracket():
    try:
        # Validação 1: Verificar se a chave já não foi gerada
        matches_count_res = supabase.table('matches').select('id', count='exact').execute()
        if matches_count_res.count > 0:
            flash('A chave do torneio já foi gerada.', 'warning')
            return redirect(url_for('admin.dashboard'))

        # Validação 2: Verificar se há exatamente 8 times
        teams_res = supabase.table('teams').select('id').execute()
        if len(teams_res.data) != 8:
            flash('É necessário ter exatamente 8 equipes inscritas para gerar a chave.', 'danger')
            return redirect(url_for('admin.dashboard'))

        # Lógica de Geração
        team_ids = [team['id'] for team in teams_res.data]
        random.shuffle(team_ids)
        
        # 1. Criar partidas placeholder para as rodadas futuras para obter seus IDs
        final_match = supabase.table('matches').insert({'round_number': 3, 'match_in_round': 1}).execute().data[0]
        semi_1 = supabase.table('matches').insert({'round_number': 2, 'match_in_round': 1, 'next_match_id': final_match['id']}).execute().data[0]
        semi_2 = supabase.table('matches').insert({'round_number': 2, 'match_in_round': 2, 'next_match_id': final_match['id']}).execute().data[0]
        
        # 2. Criar partidas da primeira rodada com os times sorteados
        supabase.table('matches').insert([
            {'round_number': 1, 'match_in_round': 1, 'team1_id': team_ids[0], 'team2_id': team_ids[1], 'next_match_id': semi_1['id']},
            {'round_number': 1, 'match_in_round': 2, 'team1_id': team_ids[2], 'team2_id': team_ids[3], 'next_match_id': semi_1['id']},
            {'round_number': 1, 'match_in_round': 3, 'team1_id': team_ids[4], 'team2_id': team_ids[5], 'next_match_id': semi_2['id']},
            {'round_number': 1, 'match_in_round': 4, 'team1_id': team_ids[6], 'team2_id': team_ids[7], 'next_match_id': semi_2['id']},
        ]).execute()
        
        flash('Chave gerada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao gerar a chave: {e}', 'danger')

    return redirect(url_for('admin.dashboard'))

@admin.route('/set-winner/<int:match_id>/<int:winner_id>', methods=['POST'])
@admin_required
def set_winner(match_id, winner_id):
    try:
        # Atualiza o vencedor da partida atual
        current_match = supabase.table('matches').update({'winner_id': winner_id}).eq('id', match_id).execute().data[0]

        # Se houver uma próxima partida, avança o vencedor
        if current_match.get('next_match_id'):
            next_match_id = current_match['next_match_id']
            next_match = supabase.table('matches').select('*').eq('id', next_match_id).single().execute().data
            
            # Preenche a primeira vaga (team1) ou a segunda (team2)
            if next_match.get('team1_id') is None:
                supabase.table('matches').update({'team1_id': winner_id}).eq('id', next_match_id).execute()
            else:
                supabase.table('matches').update({'team2_id': winner_id}).eq('id', next_match_id).execute()
        
        flash('Vencedor definido e avançado na chave!', 'success')
    except Exception as e:
        flash(f'Erro ao definir vencedor: {e}', 'danger')

    return redirect(url_for('admin.dashboard'))
        
@admin.route('/generate-veto-link', methods=['POST'])
@admin_required
def generate_veto_link():
    match_id = request.form.get('match_id')
    veto_format = request.form.get('format')
    team1_id = int(request.form.get('team1_id'))
    team2_id = int(request.form.get('team2_id'))

    if not all([match_id, veto_format, team1_id, team2_id]):
        flash('Informações insuficientes para gerar o link de veto.', 'danger')
        return redirect(url_for('admin.dashboard'))

    try:
        # --- Alteração Inicia Aqui ---
        # 1. Buscar os nomes das equipes usando os IDs
        team1_data = supabase.table('teams').select('name').eq('id', team1_id).single().execute().data
        team2_data = supabase.table('teams').select('name').eq('id', team2_id).single().execute().data
        team1_name = team1_data['name']
        team2_name = team2_data['name']
        # --- Alteração Termina Aqui ---

        # Define aleatoriamente qual time começa o veto
        starting_team_id = random.choice([team1_id, team2_id])

        # Cria a sessão de veto no banco de dados
        # **JUSTIFICATIVA TÉCNICA:** Removemos as chaves 'banned_maps' e 'picked_maps' do insert.
        # Isso força o PostgreSQL a usar o valor DEFAULT definido na tabela ('[]'::jsonb),
        # que é a maneira mais confiável de inicializar um array JSONB vazio.
        veto_session = supabase.table('vetos').insert({
            'match_id': match_id,
            'format': veto_format,
            'status': 'pending',
            'current_turn_team_id': starting_team_id
        }).execute().data[0]
        
        access_token = veto_session['access_token']
        link1 = url_for('main.veto_room', token=access_token, team_id=team1_id, _external=True)
        link2 = url_for('main.veto_room', token=access_token, team_id=team2_id, _external=True)

        # --- Alteração na Mensagem Flash ---
        flash_message = f"""
        Sala de Veto criada com sucesso!
        <br><strong>Link para {team1_name}:</strong> <input type='text' class='form-control' value='{link1}' readonly>
        <br><strong>Link para {team2_name}:</strong> <input type='text' class='form-control' value='{link2}' readonly>
        """
        flash(Markup(flash_message), 'success')

    except Exception as e:
        flash(f'Erro ao criar sala de veto: {e}', 'danger')

    return redirect(url_for('admin.dashboard'))