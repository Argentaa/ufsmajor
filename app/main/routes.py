from flask import Blueprint, render_template, request, flash, redirect, url_for
from app import supabase

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        # --- Lógica de Inscrição (POST) ---
        try:
            # 1. Verificar se ainda há vagas
            teams_count_res = supabase.table('teams').select('id', count='exact').execute()
            if teams_count_res.count >= 8:
                flash('As inscrições estão encerradas!', 'warning')
                return redirect(url_for('main.home'))

            # 2. Coletar dados do formulário
            team_name = request.form.get('team_name')
            
            p1_name = request.form.get('p1_name')
            p1_steam = request.form.get('p1_steam')
            p1_discord = request.form.get('p1_discord')
            
            p2_name = request.form.get('p2_name')
            p2_steam = request.form.get('p2_steam')
            p2_discord = request.form.get('p2_discord')
            
            # 3. Validação simples (campos não-vazios)
            if not all([team_name, p1_name, p1_steam, p1_discord, p2_name, p2_steam, p2_discord]):
                flash('Todos os campos são obrigatórios.', 'danger')
                return redirect(url_for('main.home'))

            # 4. Inserir time e jogadores no banco de dados
            # Inserir o time primeiro para obter o ID
            team_data = supabase.table('teams').insert({"name": team_name}).execute()
            new_team_id = team_data.data[0]['id']

            # Inserir os dois jogadores associados ao ID do time
            players_to_insert = [
                {"team_id": new_team_id, "name": p1_name, "steam_link": p1_steam, "discord": p1_discord, "is_leader": True},
                {"team_id": new_team_id, "name": p2_name, "steam_link": p2_steam, "discord": p2_discord}
            ]
            supabase.table('players').insert(players_to_insert).execute()

            flash(f'Equipe "{team_name}" inscrita com sucesso!', 'success')

        except Exception as e:
            # Em caso de erro (ex: nome de time duplicado), notificar o usuário
            flash(f'Ocorreu um erro ao inscrever a equipe. Verifique se o nome da equipe já existe. Erro: {e}', 'danger')
        
        return redirect(url_for('main.home'))

    # --- Lógica de Visualização (GET) ---
    teams_res = supabase.table('teams').select('id', count='exact').execute()
    vagas_restantes = 8 - teams_res.count
    
    return render_template('main/inscricao.html', vagas_restantes=vagas_restantes)
@main.route('/bracket')
def bracket_page():
    """Renderiza a página de visualização pública da chave."""
    return render_template('main/bracket.html')
@main.route('/veto/<token>')
def veto_room(token):
    """Renderiza a página da sala de veto."""
    team_id = request.args.get('team_id')
    if not team_id:
        return "Erro: ID do time não especificado.", 400

    # Apenas renderiza a página, a lógica será via API + JS
    return render_template('main/veto.html', token=token, team_id=team_id)

@main.route('/login')
def login_redirect():
    return redirect(url_for('admin.login'))

@main.route('/dashboard')
def dashboard_redirect():
    return redirect(url_for('admin.dashboard'))