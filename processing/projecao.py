import pandas as pd
from datetime import datetime

def parse_valor(v):
    if not v:
        return 0.0
    return float(v.replace(".", "").replace(",", "."))


def projecao_ate_dezembro(empenhos_base, ano):
    hoje = datetime.now()
    mes_atual = hoje.month

    total_empenhado = 0
    total_pago = 0

    for lista in empenhos_base.values():
        for emp in lista:
            data = emp.get("data_emissao")
            if not data or str(ano) not in data:
                continue

            total_empenhado += parse_valor(emp.get("empenhado"))
            total_pago += parse_valor(emp.get("pago"))

    if mes_atual == 0:
        return total_empenhado, total_pago

    media_empenho = total_empenhado / mes_atual
    media_pago = total_pago / mes_atual

    meses_restantes = 12 - mes_atual

    proj_empenho = total_empenhado + (media_empenho * meses_restantes)
    proj_pago = total_pago + (media_pago * meses_restantes)

    return proj_empenho, proj_pago
