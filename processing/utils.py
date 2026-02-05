def formatar(valor):
    """
    Formata número para padrão monetário brasileiro.
    Ex: 1234567.89 -> R$ 1.234.567,89
    """

    if valor is None:
        return "R$ 0,00"

    try:
        valor = float(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"

    return (
        f"R$ {valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )
