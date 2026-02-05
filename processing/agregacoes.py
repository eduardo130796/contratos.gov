def calcular_indicadores_gerais(contratos):
    if not contratos:
        return {
            "total": 0,
            "ativos": 0,
            "valor_global": 0.0,
            "valor_executado": 0.0,
            "execucao_media": 0.0,
            "contratos_criticos": 0,
            "contratos_vencidos": 0
        }

    def parse(v):
        if not v:
            return 0.0
        return float(v.replace(".", "").replace(",", "."))

    total = len(contratos)
    ativos = sum(1 for c in contratos if c.get("situacao") == "Ativo")

    valor_global = sum(parse(c.get("valor_global")) for c in contratos)
    valor_exec = sum(parse(c.get("valor_acumulado")) for c in contratos)

    exec_media = (valor_exec / valor_global) * 100 if valor_global else 0

    from processing.prazos import dias_para_encerrar

    vencidos = 0
    criticos = 0

    for c in contratos:
        dias = dias_para_encerrar(c.get("vigencia_fim"))
        if dias is not None:
            if dias < 0:
                vencidos += 1
            elif dias <= 30:
                criticos += 1

    return {
        "total": total,
        "ativos": ativos,
        "valor_global": valor_global,
        "valor_executado": valor_exec,
        "execucao_media": exec_media,
        "contratos_criticos": criticos,
        "contratos_vencidos": vencidos
    }
