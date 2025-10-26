import logging # Adicione esta linha no topo
from flask import Blueprint, jsonify, request, abort
from app import supabase

MAP_POOL = [
    "inferno", "nuke", "overpass", "vertigo", "mirage", "dust2", "shortdust"
]

api = Blueprint('api', __name__)

@api.route('/bracket-status')
def bracket_status():
    """
    Endpoint que retorna o estado atual de todas as partidas da chave
    em formato JSON, incluindo os jogadores de cada time.
    """
    try:
        matches_res = supabase.table('matches') \
            .select('*, team1:team1_id(name, players(*)), team2:team2_id(name, players(*)), winner:winner_id(name)') \
            .order('round_number') \
            .order('match_in_round') \
            .execute()

        return jsonify(matches_res.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api.route('/veto/<token>/status')
def veto_status(token):
    """Retorna o estado completo de uma sessão de veto."""
    # --- Alteração Inicia Aqui ---
    # Removemos o .single() e executamos a busca
    veto_res = supabase.table('vetos').select('*, match:match_id(*, team1:team1_id(id, name), team2:team2_id(id, name))') \
        .eq('access_token', token).execute()
    
    # Verificamos se a lista de dados está vazia
    if not veto_res.data:
        abort(404) # Se estiver vazia, o token não existe. Abortamos com um 404.

    # Se chegamos aqui, o veto existe. Pegamos o primeiro (e único) item da lista.
    veto_data = veto_res.data[0]
    # --- Alteração Termina Aqui ---

    return jsonify({
        "veto": veto_data, # Usamos a variável correta
        "map_pool": MAP_POOL
    })

@api.route('/veto/<token>/act', methods=['POST'])
def veto_act(token):
    """Processa uma ação de veto (ban ou pick)."""
    data = request.get_json()
    acting_team_id = data.get('team_id')
    action = data.get('action')
    map_name = data.get('map')

    # 1. Validação
    if not all([acting_team_id, action, map_name]):
        return jsonify({"error": "Dados incompletos."}), 400
    if map_name not in MAP_POOL:
        return jsonify({"error": "Mapa inválido."}), 400

    # 2. Busca o estado atual do veto
    try:
        veto_res = supabase.table('vetos').select('*, match:match_id(team1_id, team2_id)') \
            .eq('access_token', token).single().execute()
        
        if not veto_res.data:
            return jsonify({"error": "Sessão de veto não encontrada."}), 404
        
        veto = veto_res.data

        if veto['status'] == 'completed':
            return jsonify({"error": "O veto já foi finalizado."}), 400
        if veto['current_turn_team_id'] != acting_team_id:
            return jsonify({"error": "Não é a vez da sua equipe."}), 403

        banned = (veto.get('banned_maps') or []).copy()
        picked = (veto.get('picked_maps') or []).copy()
        
        picked_maps_names = [p['map'] for p in picked]

        if map_name in banned or map_name in picked_maps_names:
            return jsonify({"error": "Este mapa já foi utilizado no veto."}), 400

        # --- A CORREÇÃO ESTÁ AQUI ---
        # **JUSTIFICATIVA TÉCNICA:** Alteramos as strings para corresponder ao que o
        # frontend envia ('banir' e 'escolher'), resolvendo o bug lógico.
        if action == 'banir':
            banned.append(map_name)
        elif action == 'escolher':
            picked.append({'map': map_name, 'team_id': acting_team_id})

        next_turn_id = veto['match']['team2_id'] if acting_team_id == veto['match']['team1_id'] else veto['match']['team1_id']

        is_completed = False
        if veto['format'] == 'MD1' and len(banned) == 6:
            is_completed = True
        elif veto['format'] == 'MD3' and (len(banned) + len(picked)) == 6:
            is_completed = True

        new_status = 'completed' if is_completed else 'in_progress'

        update_payload = {
            'banned_maps': banned,
            'picked_maps': picked,
            'current_turn_team_id': next_turn_id,
            'status': new_status
        }
        
        # 4. Atualiza o banco de dados
        updated_veto_res = supabase.table('vetos').update(update_payload).eq('access_token', token).execute()
        
        return jsonify(updated_veto_res.data[0])

    except Exception as e:
        # Para um erro inesperado, é bom ter um log ou print no terminal
        print(f"ERRO CRÍTICO ao processar veto: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Falha ao salvar o estado do veto."}), 500