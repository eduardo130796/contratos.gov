import pandas as pd
from datetime import date

from processing.calculo_exercicio import calcular_valor_exercicio
from processing.calculo_exercicio import parse_data
from processing.historico import houve_repactuacao_no_ano, dias_para_encerrar
from processing.financeiro import obter_empenhos_str_por_ano

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

def moeda_para_float(valor):
    """
    Converte string monetária brasileira para float.
    Ex: '73.895,79' -> 73895.79
    """
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    return float(
        valor.replace(".", "").replace(",", ".")
    )

# -------------------------------------------------
# TABELA PRINCIPAL
# -------------------------------------------------

def montar_tabela_contratos(
    contratos,
    historicos,
    empenhos,
    ano,df_base_anterior=None
):

    linhas = []

    hoje = date.today()

    for c in contratos:

        vigencia_fim_raw = c.get("vigencia_fim")
        vigencia_fim = parse_data(vigencia_fim_raw)

        vigencia_indeterminada = False

        # Caso 1 — Vigência indeterminada (null)
        if vigencia_fim_raw is None:
            vigencia_indeterminada = True

        # Caso 2 — Vigência com data válida mas já vencida
        elif vigencia_fim and vigencia_fim < hoje:
            continue  # contrato vencido → exclui

        # Caso 3 — Data inválida inesperada
        elif not vigencia_fim:
            continue

        cid = str(c["id"])

        historico = historicos.get(cid, [])
        empenho = empenhos.get(cid, [])

        valor_exercicio = calcular_valor_exercicio(
            c,
            historico,
            ano
        )

        # -----------------------------
        # PROJEÇÃO REALISTA
        # -----------------------------

        valor_exercicio_teorico = valor_exercicio

        valor_exercicio_ajustado = valor_exercicio_teorico

        if df_base_anterior is not None:

            contrato_num = c["numero"]

            linha_anterior = df_base_anterior[
                df_base_anterior["Contrato"] == contrato_num
            ]

            if not linha_anterior.empty:

                valor_ex_ant = linha_anterior.iloc[0]["Valor exercício"]
                pago_ant = linha_anterior.iloc[0]["Liquidado + Pago"]

                if valor_ex_ant > 0:
                    indice = pago_ant / valor_ex_ant

                    # limitar distorção extrema
                    indice = max(0.6, min(indice, 1.2))

                    valor_exercicio_ajustado = (
                        valor_exercicio_teorico * indice
                    )



        repactuado = houve_repactuacao_no_ano(
            contrato_id=c["id"],
            historicos=historicos,
            ano=ano
        )


        empenhos_str = obter_empenhos_str_por_ano(
            empenho,
            ano
        )

        valor_parcela_float = moeda_para_float(c.get("valor_parcela"))
        valor_anual = valor_parcela_float * 12

        if vigencia_indeterminada:
            dias_encerrar = None
            risco_vigencia = "⚫ Indeterminada"
        else:
            dias_encerrar = dias_para_encerrar(c.get("vigencia_fim"))

            if dias_encerrar is None:
                risco_vigencia = "—"
            elif dias_encerrar <= 30:
                risco_vigencia = "🔴 Crítico"
            elif dias_encerrar <= 60:
                risco_vigencia = "🟡 Atenção"
            elif dias_encerrar <= 90:
                risco_vigencia = "🔵 Monitorar"
            else:
                risco_vigencia = "🟢 Regular"


        empenhado, pago_liq, aliquidar = somar_empenhos_do_ano(
            empenho,
            ano
        )

        diferenca = valor_exercicio_ajustado - empenhado


        if diferenca > 1:
            reforco = diferenca
            saldo_anulavel = 0
            situacao_orcamentaria = "🔴 Reforçar"
        elif diferenca < -1:
            reforco = 0
            saldo_anulavel = abs(diferenca)
            situacao_orcamentaria = "🟢 Anular"
        else:
            reforco = 0
            saldo_anulavel = 0
            situacao_orcamentaria = "⚪ OK"

        linhas.append({
            "ID": c["id"], 
            "Contrato": c["numero"],
            "Categoria": c["categoria"],
            "Objeto": c["objeto"],
            "Processo": c["processo"],
            "Fornecedor": c["fornecedor"]["nome"],
            "Cnpj": c["fornecedor"]["cnpj_cpf_idgener"],
            "Vigência inicio": c["vigencia_inicio"],
            "Vigência fim": c["vigencia_fim"],
            "Valor global": c["valor_global"],
            "modalidade": c["modalidade"],
            "valor_parcela": c["valor_parcela"],
            "Valor anual": valor_anual,
            "Nota(s) de empenho": empenhos_str if empenhos_str else "—",
            "Valor exercício": valor_exercicio_ajustado,
            "Empenhado": empenhado,
            "Liquidado + Pago": pago_liq,
            "A liquidar": aliquidar,
            "Reforco": reforco,
            "Anulavel": saldo_anulavel,
            "Diferenca": diferenca,
            "Situação": situacao_orcamentaria,
            "Dias para encerrar": dias_encerrar,
            "Risco Vigência": risco_vigencia,
            "Repactuação/Reajuste": "Sim" if repactuado else "Não",
        })

    df = pd.DataFrame(linhas)

    return df
