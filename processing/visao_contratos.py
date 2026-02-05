import pandas as pd
from datetime import date

from processing.calculo_exercicio import calcular_valor_exercicio
from processing.calculo_exercicio import parse_data


def parse_valor(v):
    if not v:
        return 0.0
    return float(v.replace(".", "").replace(",", "."))


# -------------------------------------------------
# SOMA EMPENHOS DO ANO
# -------------------------------------------------

def somar_empenhos_do_ano(empenhos, ano):
    total_empenhado = 0
    total_pago = 0
    total_liquidado = 0
    total_aliquidar = 0

    for emp in empenhos or []:
        data = emp.get("data_emissao")
        if not data:
            continue

        if str(ano) not in data:
            continue

        total_empenhado += parse_valor(emp.get("empenhado"))
        total_pago += parse_valor(emp.get("pago"))
        total_liquidado += parse_valor(emp.get("liquidado"))
        total_aliquidar += parse_valor(emp.get("aliquidar"))

    return (
        total_empenhado,
        total_pago + total_liquidado,
        total_aliquidar
    )


# -------------------------------------------------
# TABELA PRINCIPAL
# -------------------------------------------------

def montar_tabela_contratos(
    contratos,
    historicos,
    empenhos,
    ano
):

    linhas = []

    hoje = date.today()

    for c in contratos:

        vigencia_fim = parse_data(c.get("vigencia_fim"))
        if not vigencia_fim:
            continue

        # ---------------------------------------------
        # FILTRO: SOMENTE ATIVOS
        # ---------------------------------------------
        if vigencia_fim < hoje:
            continue

        cid = str(c["id"])

        historico = historicos.get(cid, [])
        empenho = empenhos.get(cid, [])

        valor_exercicio = calcular_valor_exercicio(
            c,
            historico,
            ano
        )

        empenhado, pago_liq, aliquidar = somar_empenhos_do_ano(
            empenho,
            ano
        )

        gap = valor_exercicio - empenhado

        if gap > 1:
            status = "🔴 Reforçar"
        elif gap < -1:
            status = "🟡 Anular"
        else:
            status = "🟢 OK"

        linhas.append({
            "Contrato": c["numero"],
            "Categoria": c["categoria"],
            "Objeto": c["objeto"],
            "Fornecedor": c["fornecedor"]["nome"],
            "Vigência fim": c["vigencia_fim"],
            "Valor exercício": valor_exercicio,
            "Empenhado": empenhado,
            "Liquidado + Pago": pago_liq,
            "A liquidar": aliquidar,
            "Gap": gap,
            "Situação": status
        })

    df = pd.DataFrame(linhas)

    return df
