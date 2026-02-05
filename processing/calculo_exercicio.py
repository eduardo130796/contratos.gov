from datetime import date, datetime
import calendar


# -------------------------------------------------
# UTILS
# -------------------------------------------------

def parse_data(d):
    if not d:
        return None
    return datetime.fromisoformat(d).date()


def parse_valor(v):
    if not v:
        return 0.0
    return float(v.replace(".", "").replace(",", "."))


def dias_no_mes(ano, mes):
    return calendar.monthrange(ano, mes)[1]


def valor_periodo_proporcional(inicio, fim, valor_mensal):
    total = 0.0
    atual = date(inicio.year, inicio.month, 1)

    while atual <= fim:
        ano = atual.year
        mes = atual.month
        dias_mes = dias_no_mes(ano, mes)

        inicio_mes = date(ano, mes, 1)
        fim_mes = date(ano, mes, dias_mes)

        ini_val = max(inicio, inicio_mes)
        fim_val = min(fim, fim_mes)

        if ini_val <= fim_val:
            dias_validos = (fim_val - ini_val).days + 1
            valor_dia = valor_mensal / dias_mes
            total += valor_dia * dias_validos

        if mes == 12:
            atual = date(ano + 1, 1, 1)
        else:
            atual = date(ano, mes + 1, 1)

    return total


# -------------------------------------------------
# VALOR VIGENTE ANTES DE UMA DATA
# -------------------------------------------------

def valor_vigente_antes_da_data(contrato, historico, data_evento):
    valor_global = parse_valor(contrato.get("valor_global"))
    parcelas = contrato.get("num_parcelas") or 12
    valor_mensal = valor_global / parcelas

    eventos = []

    for h in historico or []:
        d = h.get("data_inicio_novo_valor")
        if not d:
            continue

        data_ev = parse_data(d)

        if data_ev and data_ev < data_evento:
            eventos.append((data_ev, h))

    eventos = sorted(eventos, key=lambda x: x[0])

    for _, h in eventos:
        novo_valor = parse_valor(h.get("novo_valor_global"))
        if novo_valor > 0:
            parcelas = h.get("novo_num_parcelas") or parcelas
            valor_mensal = novo_valor / parcelas

    return valor_mensal

def consolidar_eventos_do_ano(historico, ano):
    """
    Considera apenas eventos que realmente alteram valor.
    Evita duplicidade e eventos sem impacto financeiro.
    """

    eventos_temp = []

    for h in historico or []:
        d = h.get("data_inicio_novo_valor")
        if not d:
            continue

        data_ev = parse_data(d)
        if not data_ev or data_ev.year != ano:
            continue

        # verificar se há valor novo
        novo_valor_global = parse_valor(h.get("novo_valor_global"))
        novo_valor_parcela = parse_valor(h.get("novo_valor_parcela"))

        if novo_valor_global <= 0 and novo_valor_parcela <= 0:
            # evento não altera valor → ignorar
            continue

        data_ass = parse_data(h.get("data_assinatura")) if h.get("data_assinatura") else None

        eventos_temp.append((data_ev, data_ass, h))

    if not eventos_temp:
        return []

    # agrupar por data
    from collections import defaultdict
    grupos = defaultdict(list)

    for data_ev, data_ass, h in eventos_temp:
        grupos[data_ev].append((data_ass, h))

    consolidados = []

    for data_ev, lista in grupos.items():
        lista_ordenada = sorted(lista, key=lambda x: (x[0] is None, x[0]))
        _, evento_final = lista_ordenada[-1]
        consolidados.append((data_ev, evento_final))

    consolidados.sort(key=lambda x: x[0])
    return consolidados




# -------------------------------------------------
# MOTOR PRINCIPAL
# -------------------------------------------------

def calcular_valor_exercicio(contrato, historico, ano):

    inicio_contrato = parse_data(contrato["vigencia_inicio"])

    eventos = consolidar_eventos_do_ano(historico, ano)

    # -------------------------------------------------
    # SEM ALTERAÇÃO NO ANO
    # -------------------------------------------------
    if not eventos:
        valor_global = parse_valor(contrato.get("valor_global"))
        parcelas = contrato.get("num_parcelas") or 12
        valor_mensal = valor_global / parcelas

        if inicio_contrato.year == ano:
            return valor_periodo_proporcional(
                inicio_contrato,
                date(ano, 12, 31),
                valor_mensal
            )

        return valor_mensal * 12

    # -------------------------------------------------
    # COM ALTERAÇÕES
    # -------------------------------------------------

    total = 0.0
    mes_corrente = 1

    for data_ev, ev in eventos:

        valor_mensal = valor_vigente_antes_da_data(
            contrato,
            historico,
            data_ev
        )

        mes_ev = data_ev.month

        # meses cheios antes
        meses_cheios = mes_ev - mes_corrente
        if meses_cheios > 0:
            total += meses_cheios * valor_mensal

        # mês da alteração
        inicio_mes = date(ano, mes_ev, 1)
        fim_mes = date(ano, mes_ev, dias_no_mes(ano, mes_ev))

        # -------------------------------------------------
        # VERIFICAR SE EXISTE NOVO VALOR REAL
        # -------------------------------------------------

        novo_valor_global = parse_valor(ev.get("novo_valor_global"))
        novo_valor_parcela = parse_valor(ev.get("novo_valor_parcela"))

        # se não houver valor novo → IGNORA evento
        if novo_valor_global <= 0 and novo_valor_parcela <= 0:
            # trata como se não houvesse alteração
            total += valor_mensal
            mes_corrente = mes_ev + 1
            continue

        # definir valor novo
        if novo_valor_global > 0:
            parcelas = ev.get("novo_num_parcelas") or parcelas
            valor_mensal_novo = novo_valor_global / parcelas
        else:
            valor_mensal_novo = novo_valor_parcela

        # -------------------------------------------------
        # CASO: começa dia 1 → mês cheio novo valor
        # -------------------------------------------------
        if data_ev.day == 1:
            valor_mensal = valor_mensal_novo
            total += valor_mensal

        # -------------------------------------------------
        # CASO: começa no meio do mês
        # -------------------------------------------------
        else:
            # parte antiga
            fim_antigo = date(ano, mes_ev, data_ev.day - 1)

            total += valor_periodo_proporcional(
                inicio_mes,
                fim_antigo,
                valor_mensal
            )

            # parte nova
            valor_mensal = valor_mensal_novo

            total += valor_periodo_proporcional(
                data_ev,
                fim_mes,
                valor_mensal
            )

        mes_corrente = mes_ev + 1

    # meses restantes
    if mes_corrente <= 12:
        valor_final = valor_vigente_antes_da_data(
            contrato,
            historico,
            date(ano, 12, 31)
        )
        total += (12 - mes_corrente + 1) * valor_final

    return total

def calcular_valor_exercicio_debug(contrato, historico, ano):
    logs = []

    inicio_contrato = parse_data(contrato["vigencia_inicio"])

    eventos = consolidar_eventos_do_ano(historico, ano)

    # -------------------------------------------------
    # SEM ALTERAÇÃO
    # -------------------------------------------------
    if not eventos:
        valor_global = parse_valor(contrato.get("valor_global"))
        parcelas = contrato.get("num_parcelas") or 12
        valor_mensal = valor_global / parcelas

        if inicio_contrato.year == ano:
            valor = valor_periodo_proporcional(
                inicio_contrato,
                date(ano, 12, 31),
                valor_mensal
            )

            logs.append({
                "tipo": "inicio_no_ano",
                "valor_mensal": valor_mensal,
                "valor": valor
            })

            return valor, logs

        valor = valor_mensal * 12

        logs.append({
            "tipo": "12_meses_cheios",
            "valor_mensal": valor_mensal,
            "valor": valor
        })

        return valor, logs

    # -------------------------------------------------
    # COM ALTERAÇÃO
    # -------------------------------------------------

    total = 0.0
    mes_corrente = 1

    for data_ev, ev in eventos:

        valor_mensal = valor_vigente_antes_da_data(
            contrato,
            historico,
            data_ev
        )

        mes_ev = data_ev.month

        meses_cheios = mes_ev - mes_corrente
        if meses_cheios > 0:
            valor = meses_cheios * valor_mensal
            total += valor

            logs.append({
                "tipo": "meses_cheios_antes",
                "meses": meses_cheios,
                "valor_mensal": valor_mensal,
                "valor": valor
            })

        inicio_mes = date(ano, mes_ev, 1)
        fim_mes = date(ano, mes_ev, dias_no_mes(ano, mes_ev))

                # VERIFICAR SE EXISTE NOVO VALOR REAL
        # -------------------------------------------------

        novo_valor_global = parse_valor(ev.get("novo_valor_global"))
        novo_valor_parcela = parse_valor(ev.get("novo_valor_parcela"))

        # se não houver valor novo → IGNORA evento
        if novo_valor_global <= 0 and novo_valor_parcela <= 0:
            # trata como se não houvesse alteração
            total += valor_mensal
            mes_corrente = mes_ev + 1
            continue

        # definir valor novo
        if novo_valor_global > 0:
            parcelas = ev.get("novo_num_parcelas") or parcelas
            valor_mensal_novo = novo_valor_global / parcelas
        else:
            valor_mensal_novo = novo_valor_parcela

        # -------------------------------------------------
        # CASO: começa dia 1 → mês cheio novo valor
        # -------------------------------------------------
        if data_ev.day == 1:
            valor_mensal = valor_mensal_novo
            total += valor_mensal

        # -------------------------------------------------
        # CASO: começa no meio do mês
        # -------------------------------------------------
        else:
            # parte antiga
            fim_antigo = date(ano, mes_ev, data_ev.day - 1)

            total += valor_periodo_proporcional(
                inicio_mes,
                fim_antigo,
                valor_mensal
            )

            # parte nova
            valor_mensal = valor_mensal_novo

            total += valor_periodo_proporcional(
                data_ev,
                fim_mes,
                valor_mensal
            )
        mes_corrente = mes_ev + 1

    if mes_corrente <= 12:
        valor_final = valor_vigente_antes_da_data(
            contrato,
            historico,
            date(ano, 12, 31)
        )

        meses = 12 - mes_corrente + 1
        valor = meses * valor_final

        total += valor

        logs.append({
            "tipo": "meses_finais",
            "meses": meses,
            "valor_mensal": valor_final,
            "valor": valor
        })

    return total, logs
