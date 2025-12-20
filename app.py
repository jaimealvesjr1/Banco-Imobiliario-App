from flask import Flask, render_template, request, redirect, url_for, session, flash
import uuid
import time
import random 
import json 
import os

app = Flask(__name__)
app.secret_key = 'chave_chaves'

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
BANK_PIN = "2525"
LEILAO_ATUAL = {}
COBRANCAS_PARCELADAS = {}
SALDO_INICIAL = 500000

def verificar_encerramento_leilao():
    global LEILAO_ATUAL
    if LEILAO_ATUAL.get('ativo') and time.time() > LEILAO_ATUAL.get('expira_em', 0):
        vencedor_id = LEILAO_ATUAL.get('jogador_atual_id')
        valor_final = LEILAO_ATUAL.get('lance_atual')
        propriedade = LEILAO_ATUAL.get('propriedade')

        if vencedor_id:
            mensagem = executar_transacao(vencedor_id, 'Banco', valor_final)
            if "Erro" not in mensagem:
                flash(f"MARTELO BATIDO! {PARTIDA[vencedor_id]['name']} comprou {propriedade} por R$ {format_brl(valor_final)}!", 'success')
        
        LEILAO_ATUAL = {}
        save_game_state()

@app.route('/banco_login', methods=['GET', 'POST'])
def banco_login():
    if 'Banco' not in PARTIDA:
        flash("Partida não iniciada.", 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        pin = request.form['pin']
        if pin == BANK_PIN:
            session['bank_logged_in'] = True
            flash("Bem vindo ao Banco Central!", 'success')
            return redirect(url_for('pagina_banco'))
        else:
            flash("PIN Incorreto. Acesso Negado.", 'error')
            return redirect(url_for('banco_login'))
    
    # GET request: Exibir o formulário de login
    return render_template('banco_login.html')

@app.route('/banco_logout')
def banco_logout():
    session.pop('bank_logged_in', None)
    flash("Sessão do Banco encerrada.", 'success')
    return redirect(url_for('dashboard'))

# --- FUNÇÕES DE PERSISTÊNCIA DE DADOS (NOVAS) ---

def load_game_state():
    """Carrega o estado do jogo do arquivo JSON, se existir."""
    global PARTIDA, LEILAO_ATUAL, COBRANCAS_PARCELADAS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                PARTIDA = data.get('partida', {})
                LEILAO_ATUAL = data.get('leilao', {})
                COBRANCAS_PARCELADAS = data.get('cobrancas_parceladas', {})
            print(f"Estado do jogo carregado de {DATA_FILE}.")
        except Exception as e:
            print(f"Erro ao carregar o estado do jogo: {e}. Iniciando nova partida vazia.")
            PARTIDA = {}
            LEILAO_ATUAL = {}
            COBRANCAS_PARCELADAS = {}
    else:
        print("Arquivo de estado do jogo não encontrado. Iniciando nova partida vazia.")
        PARTIDA = {}
        LEILAO_ATUAL = {}
        COBRANCAS_PARCELADAS = {}

def save_game_state():
    """Salva o estado atual do jogo no arquivo JSON."""
    global PARTIDA, LEILAO_ATUAL, COBRANCAS_PARCELADAS
    try:
        data_to_save = {
            'partida': PARTIDA,
            'leilao': LEILAO_ATUAL,
            'cobrancas_parceladas': COBRANCAS_PARCELADAS
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=4)
        print(f"Estado do jogo salvo em {DATA_FILE}.")
    except Exception as e:
        print(f"Erro ao salvar o estado do jogo: {e}")

# --- FUNÇÕES DE LÓGICA DO JOGO ---

def calcular_valor_parcela(valor_total, num_parcelas):
    """Calcula o valor da parcela, jogando o resto para a primeira parcela."""
    valor_parcela_base = valor_total // num_parcelas
    ajuste_centavos = valor_total % num_parcelas
    
    parcela_1 = valor_parcela_base + ajuste_centavos
    valor_parcela_outras = valor_parcela_base
    
    return parcela_1, valor_parcela_outras

def criar_parcelamento(credor_id, devedor_id, valor_total, num_parcelas):
    global COBRANCAS_PARCELADAS
    
    try:
        valor_total = int(valor_total)
        num_parcelas = int(num_parcelas)
        if valor_total <= 0 or num_parcelas <= 0 or num_parcelas > 12:
            return "Erro: Valores inválidos. O número de parcelas deve ser entre 1 e 12."
    except ValueError:
        return "Erro: Valores devem ser números inteiros."
        
    if credor_id == devedor_id:
        return "Erro: Não é possível parcelar cobrança para si mesmo."

    parcela_1, valor_parcela_outras = calcular_valor_parcela(valor_total, num_parcelas)
    
    installment_id = str(uuid.uuid4())
    
    COBRANCAS_PARCELADAS[installment_id] = {
        'devedor_id': devedor_id,
        'credor_id': credor_id,
        'valor_total': valor_total,
        'num_parcelas_total': num_parcelas,
        'num_parcelas_pagas': 0,
        'valor_primeira_parcela': parcela_1,
        'valor_outras_parcelas': valor_parcela_outras
    }
    save_game_state()
    return f"Parcelamento criado! R$ {format_brl(valor_total)} em {num_parcelas}x (Primeira de R$ {format_brl(parcela_1)})."

def pagar_parcela(devedor_id, installment_id):
    global COBRANCAS_PARCELADAS
    
    cobranca = COBRANCAS_PARCELADAS.get(installment_id)
    
    # Validações
    if not cobranca: return "Erro: Cobrança parcelada não encontrada."
    if cobranca['devedor_id'] != devedor_id: return "Erro: Você não é o devedor desta cobrança."
    if cobranca['num_parcelas_pagas'] >= cobranca['num_parcelas_total']: return "Erro: Esta cobrança já foi quitada."
        
    num_pagas = cobranca['num_parcelas_pagas']
    
    # Determinar o valor da parcela
    valor_parcela = cobranca['valor_primeira_parcela'] if num_pagas == 0 else cobranca['valor_outras_parcelas']
        
    # Verificar Saldo (reusa a lógica de verificação de saldo da transação individual)
    saldo_devedor = PARTIDA[devedor_id]['saldo']
    if saldo_devedor < valor_parcela:
        return f"Erro: Saldo R$ {format_brl(saldo_devedor)} insuficiente para pagar a parcela de R$ {format_brl(valor_parcela)}."

    # Executar a Transação
    PARTIDA[devedor_id]['saldo'] -= valor_parcela
    PARTIDA[cobranca['credor_id']]['saldo'] += valor_parcela
    
    # Registrar a transação (Débito e Crédito)
    registrar_transacao(devedor_id, cobranca['credor_id'], valor_parcela) 
    
    # Atualizar o estado da cobrança
    cobranca['num_parcelas_pagas'] += 1
    
    num_total = cobranca['num_parcelas_total']
    num_restante = num_total - cobranca['num_parcelas_pagas']
    
    if num_restante == 0:
        del COBRANCAS_PARCELADAS[installment_id] # Remover a cobrança quitada
        save_game_state()
        return f"Parcelamento quitado! Parabéns!"
        
    save_game_state()
    return f"Parcela paga com sucesso! Restam {num_restante} de {num_total}."

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

def transferir_poupanca(player_id, valor, para_poupanca=True):
    """Transfere valor entre saldo e poupança de um jogador."""
    try:
        valor = int(valor)
        if valor <= 0: return "Erro: Valor deve ser positivo."
    except ValueError: return "Erro: Valor inválido."

    jogador = PARTIDA.get(player_id)
    if not jogador: return "Erro: Jogador não encontrado."
    
    if para_poupanca: # Saldo -> Poupança
        if jogador['saldo'] < valor: return "Erro: Saldo insuficiente para investir."
        jogador['saldo'] -= valor
        jogador['poupanca'] += valor
        return f"R$ {format_brl(valor)} investido na poupança com sucesso!"
    else: # Poupança -> Saldo (só se não estiver trancado)
        if PARTIDA['Banco']['poupanca_trancada']: return "Erro: Poupança está trancada. Não é possível resgatar."
        if jogador['poupanca'] < valor: return "Erro: Valor de resgate maior que a poupança."
        jogador['saldo'] += valor
        jogador['poupanca'] -= valor
        return f"R$ {format_brl(valor)} resgatado da poupança com sucesso!"

def trancar_poupanca(trancar):
    """Tranca/Destranca a poupança globalmente."""
    PARTIDA['Banco']['poupanca_trancada'] = trancar
    save_game_state()
    return "Poupança trancada com sucesso." if trancar else "Poupança destrancada com sucesso."

def aplicar_rendimento(percentual):
    if not PARTIDA['Banco']['poupanca_trancada']: 
        return "Erro: Poupança não está trancada."
    try:
        percentual = float(percentual)
        if percentual < -100 or percentual > 100: return "Erro: Limite de -100% a 100%."
    except ValueError: return "Erro: Valor inválido."
    
    fator = percentual / 100
    total_movimentado = 0
    for player_id, data in PARTIDA.items():
        if player_id not in ('Banco', 'timestamp'):
            rendimento = int(data['poupanca'] * fator)
            data['poupanca'] += rendimento
            total_movimentado += rendimento
    save_game_state()
    tipo = "Rendimento" if percentual >= 0 else "Taxa/Deflação"
    return f"{tipo} de {percentual}% aplicado! Total: R$ {format_brl(total_movimentado)}."

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

def executar_transacao(remetente_id, recebedor_id, valor):
    try:
        valor = int(valor)
    except ValueError:
        return "Erro: O valor deve ser um número inteiro."
    
    if valor <= 0:
        return "Erro: O valor da transação deve ser positivo."

    if remetente_id != 'Banco':
        if remetente_id not in PARTIDA:
            return f"Erro: Remetente ID '{remetente_id}' não encontrado."
            
        if PARTIDA[remetente_id]['saldo'] < valor:
            flash(f"ALERTA: {PARTIDA[remetente_id]['name']} ficou com saldo negativo!", "warning")
        
        PARTIDA[remetente_id]['saldo'] -= valor
    
    if recebedor_id != 'Banco':
        if recebedor_id not in PARTIDA:
            return f"Erro: Recebedor ID '{recebedor_id}' não encontrado."
        PARTIDA[recebedor_id]['saldo'] += valor

    registrar_transacao(remetente_id, recebedor_id, valor)
    save_game_state()
    return "Transação realizada com sucesso!"

def executar_transacao_massa(tipo, valor):
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
    
    save_game_state()
    return f"Cobrança de R$ {valor} realizada com sucesso para todos os {len(jogadores_ativos)} jogadores."

def executar_transacao_percentual(tipo, percentual):
    """
    Executa transação em massa baseada em um percentual do saldo atual do jogador.
    """
    try:
        percentual = float(percentual)
        if percentual <= 0 or percentual > 100:
            return "Erro: O percentual deve estar entre 0.01 e 100."
    except ValueError:
        return "Erro: O percentual deve ser um número válido."
        
    fator = percentual / 100
    jogadores_ativos = [id for id in PARTIDA if id not in ('Banco', 'timestamp')]
    
    total_movimentado = 0
    
    if tipo == 'COBRAR_PCT':
        for player_id in jogadores_ativos:
            saldo_jogador = PARTIDA[player_id]['saldo']
            valor_movimentado = int(saldo_jogador * fator) # Arredonda para baixo/inteiro para simplificar
            
            if valor_movimentado > 0:
                PARTIDA[player_id]['saldo'] -= valor_movimentado
                registrar_transacao(player_id, 'Banco', valor_movimentado)
                total_movimentado += valor_movimentado
        
        return f"Cobrança de {percentual}% (Total R$ {format_brl(total_movimentado)}) realizada com sucesso para todos os jogadores."

    elif tipo == 'PAGAR_PCT':
        for player_id in jogadores_ativos:
            saldo_jogador = PARTIDA[player_id]['saldo']
            valor_movimentado = int(saldo_jogador * fator) # Arredonda para baixo/inteiro
            
            if valor_movimentado > 0:
                PARTIDA[player_id]['saldo'] += valor_movimentado
                registrar_transacao('Banco', player_id, valor_movimentado)
                total_movimentado += valor_movimentado
                
        return f"Pagamento de {percentual}% (Total R$ {format_brl(total_movimentado)}) realizado com sucesso para todos os jogadores."
        
    return "Erro desconhecido na transação percentual."

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
            'Banco': {'historico': [], 'poupanca_trancada': False},
            'timestamp': 0
        }
        
        for p in jogadores_data:
            player_id = str(uuid.uuid4())
            PARTIDA[player_id] = {
                'name': p['name'], 
                'saldo': saldo_inicial, 
                'historico': [], 
                'color': p['color'],
                'poupanca': 0,
                'pin': None
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
    global PARTIDA, LEILAO_ATUAL
    PARTIDA = {}
    LEILAO_ATUAL = {}
    
    save_game_state()
    
    flash("O jogo foi resetado com sucesso! Inicie uma nova partida.", 'success')
    return redirect(url_for('dashboard'))

@app.route('/transacao-unificada', methods=['POST'])
def transacao_unificada():
    value_type = request.form.get('value_type', 'FIXO') 
    action_type_final = request.form['action_type_final']
    target_id = request.form['target_id']
    valor_raw = request.form.get('valor', 0)

    try:
        if value_type == 'PCT':
            percentual = float(valor_raw)
            if percentual <= 0 or percentual > 100:
                flash("Erro: O percentual deve estar entre 0.01 e 100.", 'error')
                return redirect(url_for('pagina_banco'))
        else:
            valor_base = float(valor_raw)
            ajuste_pct = float(request.form.get('ajuste_pct', 0)) / 100
            valor_final = int(valor_base * (1 + ajuste_pct))
            
            if valor_final <= 0:
                flash("Erro: O valor final da transação deve ser positivo.", 'error')
                return redirect(url_for('pagina_banco'))
                
    except ValueError:
        flash("Erro: Insira números válidos.", 'error')
        return redirect(url_for('pagina_banco'))

    if target_id == 'Todos':
        if value_type == 'PCT':
            mensagem = executar_transacao_percentual(action_type_final + '_PCT', percentual)
        else:
            mensagem = executar_transacao_massa(action_type_final, valor_final)
    else:
        if value_type == 'PCT':
            saldo_alvo = PARTIDA[target_id]['saldo']
            valor_calculado_pct = int(saldo_alvo * (percentual / 100))
            
            if valor_calculado_pct <= 0:
                flash(f"Erro: {percentual}% do saldo de {PARTIDA[target_id]['name']} é R$ 0. Operação cancelada.", 'error')
                return redirect(url_for('pagina_banco'))
            
            remetente_id = target_id if action_type_final == 'COBRAR' else 'Banco'
            recebedor_id = 'Banco' if action_type_final == 'COBRAR' else target_id
            mensagem = executar_transacao(remetente_id, recebedor_id, valor_calculado_pct)
            mensagem = f"({percentual}%) " + mensagem
        else:
            remetente_id = target_id if action_type_final == 'COBRAR' else 'Banco'
            recebedor_id = 'Banco' if action_type_final == 'COBRAR' else target_id
            mensagem = executar_transacao(remetente_id, recebedor_id, valor_final)

    flash(mensagem, 'error' if "Erro" in mensagem else 'success')
    return redirect(url_for('pagina_banco'))

@app.route('/leilao/iniciar', methods=['POST'])
def iniciar_leilao():
    global LEILAO_ATUAL
    tempo_segundos = 90
    
    # 1. Verificação de Pré-condição
    if LEILAO_ATUAL.get('ativo', False):
        flash("Erro: Já existe um leilão ativo. Finalize-o antes de começar outro.", 'error')
        return redirect(url_for('pagina_banco'))
        
    propriedade = request.form['propriedade']
    lance_inicial = request.form['lance_inicial']
    
    try:
        lance_inicial = int(lance_inicial)
        if lance_inicial <= 0: raise ValueError
    except ValueError:
        flash("Erro: O lance inicial deve ser um número inteiro positivo.", 'error')
        return redirect(url_for('pagina_banco'))

    # 2. Inicializa o Leilão
    LEILAO_ATUAL = {
        'ativo': True,
        'propriedade': propriedade,
        'lance_minimo': lance_inicial,
        'lance_atual': lance_inicial,
        'jogador_atual_id': None,
        'jogador_atual_nome': None,
        'expira_em': time.time() + tempo_segundos
    }
    save_game_state()
    flash(f"Leilão da propriedade '{propriedade}' iniciado com lance inicial de R$ {format_brl(lance_inicial)}!", 'success')
    return redirect(url_for('pagina_banco'))


@app.route('/leilao/lance/<player_id>', methods=['POST'])
def dar_lance(player_id):
    global LEILAO_ATUAL
    
    if LEILAO_ATUAL.get('ativo') and time.time() > LEILAO_ATUAL.get('expira_em', 0):
        verificar_encerramento_leilao()
        flash("Erro: O leilão encerrou enquanto você digitava!", 'error')
        return redirect(url_for('pagina_jogador', player_id=player_id))
    
    if not LEILAO_ATUAL.get('ativo', False) or time.time() > LEILAO_ATUAL.get('expira_em', 0):
        verificar_encerramento_leilao() 
        flash("Erro: O leilão já foi encerrado.", 'error')
        return redirect(url_for('pagina_jogador', player_id=player_id))
        
    try:
        novo_lance = int(request.form['lance'])
        
        saldo_jogador = PARTIDA[player_id]['saldo']
        if saldo_jogador < novo_lance:
            flash(f"Erro: Saldo R$ {format_brl(saldo_jogador)} insuficiente para cobrir o lance.", 'error')
            return redirect(url_for('pagina_jogador', player_id=player_id))

        if novo_lance <= LEILAO_ATUAL['lance_atual']:
            flash(f"Erro: Seu lance deve ser maior que R$ {format_brl(LEILAO_ATUAL['lance_atual'])}.", 'error')
            return redirect(url_for('pagina_jogador', player_id=player_id))
        
    except ValueError:
        flash("Erro: O lance deve ser um número inteiro.", 'error')
        return redirect(url_for('pagina_jogador', player_id=player_id))

    novo_registro = {
        'nome': PARTIDA[player_id]['name'],
        'valor': novo_lance
    }
    
    historico = LEILAO_ATUAL.get('ultimos_lances', [])
    historico.insert(0, novo_registro)
    LEILAO_ATUAL['ultimos_lances'] = historico[:3]

    LEILAO_ATUAL['lance_atual'] = novo_lance
    LEILAO_ATUAL['jogador_atual_id'] = player_id
    LEILAO_ATUAL['jogador_atual_nome'] = PARTIDA[player_id]['name']
    LEILAO_ATUAL['expira_em'] = time.time() + 30
    
    save_game_state()
    
    flash(f"Sucesso! Você lidera o leilão com R$ {format_brl(novo_lance)}.", 'success')
    return redirect(url_for('pagina_jogador', player_id=player_id))

@app.route('/leilao/finalizar', methods=['POST'])
def finalizar_leilao():
    global LEILAO_ATUAL
    
    if not LEILAO_ATUAL.get('ativo'):
        flash("Erro: Não há leilão ativo.", 'error')
        return redirect(url_for('pagina_banco'))
        
    vencedor_id = LEILAO_ATUAL['jogador_atual_id']
    valor_final = LEILAO_ATUAL['lance_atual']
    propriedade = LEILAO_ATUAL['propriedade']
    
    if vencedor_id is None:
        LEILAO_ATUAL = {}
        save_game_state()
        flash("Leilão encerrado sem licitantes.", 'warning')
        return redirect(url_for('pagina_banco'))

    mensagem = executar_transacao(vencedor_id, 'Banco', valor_final)
    
    if "Erro" not in mensagem:
        vencedor_nome = PARTIDA[vencedor_id]['name']
        flash(f"SUCESSO: {vencedor_nome} comprou {propriedade} por R$ {format_brl(valor_final)}!", 'success')
        LEILAO_ATUAL = {}
        save_game_state()
    else:
        flash(f"Erro ao processar venda: {mensagem}", 'error')

    return redirect(url_for('pagina_banco'))

# 🌟 Rota /banco (Integração do Ranking)
@app.route('/banco')
def pagina_banco():
    if 'Banco' not in PARTIDA:
        flash("Partida não iniciada.", 'error')
        return redirect(url_for('dashboard'))
    
    if not session.get('bank_logged_in'):
        return redirect(url_for('banco_login'))
        
    jogadores_data = {id: data for id, data in PARTIDA.items() if id not in ('Banco', 'timestamp')}
    
    ranking_corrente = sorted(
        jogadores_data.items(),
        key=lambda item: item[1]['saldo'],
        reverse=True
    )
    
    ranking_poupanca = sorted(
        jogadores_data.items(),
        key=lambda item: item[1]['poupanca'],
        reverse=True
    )
    
    return render_template('banco.html', 
                           jogadores_data=jogadores_data,
                           ranking_corrente=ranking_corrente,
                           ranking_poupanca=ranking_poupanca,
                           id_to_name=get_id_to_name_map(),
                           partida=PARTIDA,
                           LEILAO_ATUAL=LEILAO_ATUAL)

@app.route('/banco/reset_pin/<player_id>', methods=['POST'])
def reset_pin(player_id):
    if not session.get('bank_logged_in'):
        return redirect(url_for('banco_login'))
    
    if player_id in PARTIDA:
        PARTIDA[player_id]['pin'] = None
        save_game_state()
        flash(f"PIN de {PARTIDA[player_id]['name']} resetado!", "success")
    return redirect(url_for('pagina_banco'))

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

@app.route('/acessar_perfil/<player_id>')
def acessar_perfil(player_id):
    session.pop(f'auth_{player_id}', None)
    return redirect(url_for('jogador_auth', player_id=player_id))

@app.route('/jogador_auth/<player_id>', methods=['GET', 'POST'])
def jogador_auth(player_id):
    if player_id not in PARTIDA:
        return redirect(url_for('dashboard'))
    
    session.pop(f'auth_{player_id}', None)
    jogador = PARTIDA[player_id]

    if request.method == 'POST':
        if jogador.get('pin') is None:
            novo_pin = request.form.get('pin')
            if len(novo_pin) == 4 and novo_pin.isdigit():
                PARTIDA[player_id]['pin'] = novo_pin
                save_game_state()
                session[f'auth_{player_id}'] = True
                return redirect(url_for('pagina_jogador', player_id=player_id))
        
        else:
            pin_inserido = request.form.get('pin')
            if pin_inserido == jogador['pin']:
                session[f'auth_{player_id}'] = True
                return redirect(url_for('pagina_jogador', player_id=player_id))
        flash("PIN Incorreto!", "error")
    return render_template('jogador_login.html', jogador=jogador, jogador_id=player_id)

@app.route('/jogador/<player_id>')
def pagina_jogador(player_id):
    verificar_encerramento_leilao()
    if not session.get(f'auth_{player_id}'):
        return redirect(url_for('jogador_auth', player_id=player_id))
    
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
                           partida=PARTIDA,
                           LEILAO_ATUAL=LEILAO_ATUAL,
                           COBRANCAS_PARCELADAS=COBRANCAS_PARCELADAS)

@app.route('/jogador_logout/<player_id>')
def logout_jogador(player_id):
    session.pop(f'auth_{player_id}', None)
    return redirect(url_for('dashboard'))

@app.route('/poupanca/controle', methods=['POST'])
def controle_poupanca():
    action = request.form['action']
    
    if action == 'trancar':
        mensagem = trancar_poupanca(True)
    elif action == 'destrancar':
        mensagem = trancar_poupanca(False)
    elif action == 'render':
        percentual = request.form.get('percentual_render')
        mensagem = aplicar_rendimento(percentual)
    else:
        mensagem = "Ação de poupança inválida."
        
    flash(mensagem, 'error' if "Erro" in mensagem else 'success')
    return redirect(url_for('pagina_banco'))

@app.route('/jogador/poupanca/<player_id>', methods=['POST'])
def poupanca_jogador(player_id):
    action = request.form['action']
    valor = request.form['valor']
    
    if action == 'investir':
        mensagem = transferir_poupanca(player_id, valor, True)
    elif action == 'resgatar':
        mensagem = transferir_poupanca(player_id, valor, False)
    else:
        mensagem = "Ação inválida."

    flash(mensagem, 'error' if "Erro" in mensagem else 'success')
    return redirect(url_for('pagina_jogador', player_id=player_id))

@app.route('/cobrar/parcelar/<credor_id>', methods=['POST'])
def criar_cobranca_parcelada(credor_id):
    devedor_id = request.form['devedor_id']
    valor_total = request.form['valor_total']
    num_parcelas = request.form['num_parcelas']
    
    mensagem = criar_parcelamento(credor_id, devedor_id, valor_total, num_parcelas)
    
    flash(mensagem, 'error' if "Erro" in mensagem else 'success')
    return redirect(url_for('pagina_jogador', player_id=credor_id))

@app.route('/pagar/parcela/<devedor_id>/<installment_id>', methods=['POST'])
def pagar_cobranca_parcelada(devedor_id, installment_id):
    mensagem = pagar_parcela(devedor_id, installment_id)
    
    flash(mensagem, 'error' if "Erro" in mensagem else 'success')
    return redirect(url_for('pagina_jogador', player_id=devedor_id))

if __name__ == '__main__':
    app.run(debug=True)