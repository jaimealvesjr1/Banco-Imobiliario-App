# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
import uuid 
import random 
import json 
import os

app = Flask(__name__)
# Chave secreta é necessária para usar 'session' e 'flash'
app.secret_key = 'chave_chaves'

# Cores pré-definidas para os jogadores (Tailwind colors)
PRESET_COLORS = [
    '#3B82F6',  # Red-500
    '#EF4444',  # Blue-500
    '#10B981',  # Emerald-500
    '#F59E0B',  # Amber-500
    '#8B5CF6',  # Violet-500
    '#EC4899',  # Pink-500
    '#6B7280',  # Gray-500
    '#06B6D4'   # Cyan-500
]

# Variáveis globais para armazenar o estado do jogo
DATA_FILE = 'banco_imobiliario_state.json' 
PARTIDA = {}
SALDO_INICIAL = 250000

# --- FUNÇÕES DE PERSISTÊNCIA DE DADOS (NOVAS) ---

def load_game_state():
    """Carrega o estado do jogo do arquivo JSON, se existir."""
    global PARTIDA
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                PARTIDA = json.load(f)
            print(f"Estado do jogo carregado de {DATA_FILE}.")
        except Exception as e:
            print(f"Erro ao carregar o estado do jogo: {e}. Iniciando nova partida vazia.")
            PARTIDA = {} # Volta para estado vazio se houver erro
    else:
        print("Arquivo de estado do jogo não encontrado. Iniciando nova partida vazia.")
        PARTIDA = {}

def save_game_state():
    """Salva o estado atual do jogo no arquivo JSON."""
    global PARTIDA
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(PARTIDA, f, indent=4)
        print(f"Estado do jogo salvo em {DATA_FILE}.")
    except Exception as e:
        print(f"Erro ao salvar o estado do jogo: {e}")

# --- FUNÇÕES DE LÓGICA DO JOGO ---

def format_brl(value):
    """Formata um número inteiro para o formato BRL com separador de milhar (ex: 1.500)."""
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            return value # Retorna o valor original se não puder ser convertido
    
    # Usa a formatação local para o Brasil
    # No seu ambiente Python 3.13, isto deve funcionar bem.
    # Ex: 1500 -> 1.500
    return f"{value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

app.jinja_env.filters['format_brl'] = format_brl

def registrar_transacao(remetente_id, recebedor_id, valor):
    """
    Função para registrar uma transação.
    """
    agora = PARTIDA.get('timestamp', 0) + 1
    PARTIDA['timestamp'] = agora
    
    transacao = {
        'id': agora,
        'valor': valor,
        'remetente_id': remetente_id,
        'recebedor_id': recebedor_id,
        'timestamp': agora
    }
    
    # Adiciona ao histórico do remetente
    if remetente_id != 'Banco':
        PARTIDA[remetente_id]['historico'].append(transacao)
    
    # Adiciona ao histórico do recebedor
    if recebedor_id != 'Banco':
        PARTIDA[recebedor_id]['historico'].append(transacao)
    
    # Adiciona ao histórico geral do Banco
    PARTIDA['Banco']['historico'].append(transacao)
    save_game_state()


def executar_transacao(remetente_id, recebedor_id, valor):
    """
    Função para transações individuais.
    """
    try:
        valor = int(valor)
    except ValueError:
        return "Erro: O valor deve ser um número inteiro."
    
    if valor <= 0:
        return "Erro: O valor da transação deve ser positivo."

    # 1. Diminui o saldo do remetente
    if remetente_id != 'Banco':
        if remetente_id not in PARTIDA or PARTIDA[remetente_id]['saldo'] < valor:
             # Adicionando verificação de saldo
            return f"Erro: Saldo insuficiente para o remetente: {PARTIDA.get(remetente_id, {}).get('name', remetente_id)}."
        PARTIDA[remetente_id]['saldo'] -= valor
    
    # 2. Aumenta o saldo do recebedor
    if recebedor_id != 'Banco':
        if recebedor_id not in PARTIDA:
            return f"Erro: Recebedor ID '{recebedor_id}' não encontrado."
        PARTIDA[recebedor_id]['saldo'] += valor

    # 3. Registra a transação
    registrar_transacao(remetente_id, recebedor_id, valor)
    
    return "Transação realizada com sucesso!"


def executar_transacao_massa(tipo, valor):
    """
    NOVO: Transação em Massa (Cobrar ou Pagar todos os jogadores).
    Tipo: 'COBRAR' (Banco recebe) ou 'PAGAR' (Banco paga).
    """
    try:
        valor = int(valor)
    except ValueError:
        return "Erro: O valor deve ser um número inteiro."
    
    if valor <= 0:
        return "Erro: O valor da transação deve ser positivo."

    jogadores_ativos = [id for id in PARTIDA if id not in ('Banco', 'timestamp')]
    
    if tipo == 'COBRAR':
        for player_id in jogadores_ativos:
            # 1. Verifica saldo antes de cobrar
            if PARTIDA[player_id]['saldo'] < valor:
                flash(f"Aviso: Saldo insuficiente para {PARTIDA[player_id]['name']}. O saldo dele será negativo.", 'warning')
            
            PARTIDA[player_id]['saldo'] -= valor # Cobra o valor
            registrar_transacao(player_id, 'Banco', valor) # Registra (Jogador -> Banco)
        
        return f"Cobrança de R$ {valor} realizada com sucesso para todos os {len(jogadores_ativos)} jogadores."

    elif tipo == 'PAGAR':
        for player_id in jogadores_ativos:
            PARTIDA[player_id]['saldo'] += valor # Paga o valor
            registrar_transacao('Banco', player_id, valor) # Registra (Banco -> Jogador)
            
        return f"Pagamento de R$ {valor} realizado com sucesso para todos os {len(jogadores_ativos)} jogadores."
    
    return "Erro desconhecido na transação em massa."

def get_id_to_name_map():
    id_to_name = {
        id: data['name'] 
        for id, data in PARTIDA.items() 
        if id not in ('Banco', 'timestamp')
    }
    id_to_name['Banco'] = 'Banco'
    return id_to_name

# --- ROTAS DA APLICAÇÃO ---

load_game_state()
# 1. Rota de Gerenciamento do Jogo (Início, Continuação, Configuração)
@app.route('/', methods=['GET', 'POST'])
def dashboard():
    global PARTIDA, SALDO_INICIAL

    # Processa POST de Configuração de Partida
    if request.method == 'POST' and request.form.get('action') == 'iniciar':
        
        jogadores_data = []
        # O formulário será dinâmico, buscando por chaves com 'jogador_name_'
        for key, value in request.form.items():
            if key.startswith('jogador_name_'):
                # Assumimos que o índice está no final da chave (ex: jogador_name_0)
                index = key.split('_')[-1]
                name = value.strip()
                color = request.form.get(f'jogador_color_{index}')
                if name and color:
                    jogadores_data.append({'name': name, 'color': color})
            
        saldo_inicial_str = request.form.get('saldo_inicial', str(SALDO_INICIAL))
        
        try:
            saldo_inicial = int(saldo_inicial_str)
        except ValueError:
            flash("Saldo inicial deve ser um número inteiro.", 'error')
            return redirect(url_for('dashboard'))

        if len(jogadores_data) < 2:
            flash("São necessários pelo menos 2 jogadores.", 'error')
            return redirect(url_for('dashboard'))
            
        # Inicializa a nova partida
        PARTIDA = {
            'Banco': {'historico': []},
            'timestamp': 0
        }
        
        for p in jogadores_data:
            player_id = str(uuid.uuid4())
            PARTIDA[player_id] = {
                'name': p['name'], 
                'saldo': saldo_inicial, 
                'historico': [], 
                'color': p['color']
            }
        
        save_game_state()
        
        flash("Partida iniciada com sucesso! Escolha seu perfil para continuar.", 'success')
        return redirect(url_for('dashboard'))
        
    # Processa GET: Exibe a tela de configuração ou seleção
    game_active = 'Banco' in PARTIDA
    jogadores = [(id, data['name']) for id, data in PARTIDA.items() if id not in ('Banco', 'timestamp')]
    
    return render_template('dashboard.html', 
                           game_active=game_active, 
                           jogadores=jogadores, 
                           SALDO_INICIAL=SALDO_INICIAL, 
                           PRESET_COLORS=PRESET_COLORS,
                           PARTIDA=PARTIDA)


# 2. Rota para Excluir (Resetar) o Jogo
@app.route('/reset', methods=['POST'])
def reset_game():
    global PARTIDA
    PARTIDA = {}
    
    save_game_state()
    
    flash("O jogo foi resetado com sucesso! Inicie uma nova partida.", 'success')
    return redirect(url_for('dashboard'))

@app.route('/transacao-unificada', methods=['POST'])
def transacao_unificada():
    # Tipo de ação: 'COBRAR' (Banco recebe) ou 'PAGAR' (Banco paga)
    action_type = request.form['action_type'] 
    
    # Destinatário ou Pagador: player_id ou 'Todos'
    target_id = request.form['target_id']
    valor = request.form['valor']

    if target_id == 'Todos':
        # Transação em Massa (Sempre Banco vs Todos)
        if action_type == 'COBRAR':
            mensagem = executar_transacao_massa('COBRAR', valor)
        else: # PAGAR
            mensagem = executar_transacao_massa('PAGAR', valor)
        
        # Redireciona sempre para o banco após transação em massa
        redirect_to = url_for('pagina_banco') 

    else:
        # Transação Individual (Sempre Banco vs 1 Jogador)
        if action_type == 'COBRAR':
            # Cobrar: Jogador Paga (Remetente) -> Banco Recebe (Recebedor)
            remetente_id = target_id
            recebedor_id = 'Banco'
        else: # PAGAR
            # Pagar: Banco Paga (Remetente) -> Jogador Recebe (Recebedor)
            remetente_id = 'Banco'
            recebedor_id = target_id
        
        mensagem = executar_transacao(remetente_id, recebedor_id, valor)
        
        # Redireciona para o banco (já que a transação foi iniciada de lá)
        redirect_to = url_for('pagina_banco')

    if "Erro" in mensagem or "Aviso" in mensagem:
        flash(mensagem, 'error')
    else:
        flash(mensagem, 'success')
        
    return redirect(redirect_to)


# 🌟 Rota /banco (Integração do Ranking)
@app.route('/banco')
def pagina_banco():
    if 'Banco' not in PARTIDA:
        flash("Partida não iniciada.", 'error')
        return redirect(url_for('dashboard'))
        
    jogadores_data = {id: data for id, data in PARTIDA.items() if id not in ('Banco', 'timestamp')}
    
    # 🌟 NOVO: Criação do Ranking de Saldo
    ranking = sorted(
        jogadores_data.items(),
        key=lambda item: item[1]['saldo'],
        reverse=True
    )
    
    return render_template('banco.html', 
                           jogadores_data=jogadores_data,
                           ranking=ranking,  # Passa o ranking
                           id_to_name=get_id_to_name_map(),
                           partida=PARTIDA)

# 5. Rota de Transação Individual
@app.route('/transacao', methods=['POST'])
def transacao():
    remetente_id = request.form['remetente_id']
    recebedor_id = request.form['recebedor_id']
    valor = request.form['valor']
    
    mensagem = executar_transacao(remetente_id, recebedor_id, valor)
    
    if "Erro" in mensagem:
        flash(mensagem, 'error')
    else:
        flash(mensagem, 'success')
    
    if remetente_id == 'Banco':
        return redirect(url_for('pagina_banco'))
    else:
        return redirect(url_for('pagina_jogador', player_id=remetente_id))

# 6. Rota do Jogador (Permanece quase a mesma, usando IDs)
@app.route('/jogador/<player_id>')
def pagina_jogador(player_id):
    if player_id not in PARTIDA or player_id == 'Banco':
        flash("Jogador não encontrado.", 'error')
        return redirect(url_for('dashboard'))
        
    dados_jogador = PARTIDA[player_id]
    
    # Prepara destinatários para o formulário de pagamento
    destinatarios = [('Banco', 'Banco')] + [
        (id, data['name']) 
        for id, data in PARTIDA.items() 
        if id not in ('Banco', player_id, 'timestamp')
    ]

    historico = sorted(dados_jogador['historico'], key=lambda x: x['id'], reverse=True)
    
    id_to_name = {
        id: data['name'] 
        for id, data in PARTIDA.items() 
        if id not in ('Banco', 'timestamp')
    }
    id_to_name['Banco'] = 'Banco'

    return render_template('jogador.html', 
                           player_id=player_id, 
                           dados_jogador=dados_jogador,
                           destinatarios=destinatarios,
                           historico=historico,
                           id_to_name=id_to_name,
                           PARTIDA=PARTIDA)

if __name__ == '__main__':
    app.run(debug=True)