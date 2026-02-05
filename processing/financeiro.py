from datetime import datetime


def parse_valor(valor):
    if not valor:
        return 0.0
    return float(valor.replace(".", "").replace(",", "."))


def ano_da_data(data_str):
    if not data_str:
        return None
    return datetime.fromisoformat(data_str).year


def consolidar_empenhos(empenhos, ano_referencia):
    """
    empenhos: lista de empenhos de um contrato
    ano_referencia: int (ex: 2025)
    """

    total_empenhado = 0.0
    total_aliquidar = 0.0
    total_liquidado = 0.0
    total_pago = 0.0

    for e in empenhos:
        ano = ano_da_data(e.get("data_emissao"))
        if ano != ano_referencia:
            continue

        total_empenhado += parse_valor(e.get("empenhado"))
        total_aliquidar += parse_valor(e.get("aliquidar"))
        total_liquidado += parse_valor(e.get("liquidado"))
        total_pago += parse_valor(e.get("pago"))

    return total_empenhado, total_aliquidar, total_liquidado, total_pago
