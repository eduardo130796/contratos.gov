from datetime import datetime
import pandas as pd


def _parse_data(data):
    if not data:
        return None
    return datetime.fromisoformat(data)


def _resumir_observacao(texto):
    if not texto:
        return ""
    texto = texto.replace("\r", " ").replace("\n", " ")
    return texto[:180] + "..." if len(texto) > 180 else texto


def normalizar_historico(eventos):
    registros = []

    # ordena por data de assinatura (linha do tempo)
    eventos_ordenados = sorted(
        eventos,
        key=lambda e: e.get("data_assinatura") or ""
    )

    ordem = 1

    for e in eventos_ordenados:
        tipo = e.get("tipo")
        data_ass = e.get("data_assinatura")
        vig_ini = e.get("vigencia_inicio")
        vig_fim = e.get("vigencia_fim")

        # identifica impacto
        impacto = "—"
        evento = tipo

        qualificacoes = e.get("qualificacao_termo") or []

        if tipo == "Contrato":
            evento = "Assinatura do contrato"
            impacto = "Início"
        else:
            if any(q["descricao"] == "VIGÊNCIA" for q in qualificacoes):
                impacto = "Prazo"
                if "excepcional" in (e.get("observacao") or "").lower():
                    evento = "Prorrogação excepcional"
                else:
                    evento = "Prorrogação"
            if any(q["descricao"] in ["REAJUSTE", "ACRÉSCIMO / SUPRESSÃO"] for q in qualificacoes):
                impacto = "Valor"

        registros.append({
            "Ordem": ordem,
            "Tipo": tipo,
            "Data": data_ass,
            "Vigência": f"{vig_ini} → {vig_fim}" if vig_ini or vig_fim else "-",
            "Evento": evento,
            "Impacto": impacto,
            "Observação": _resumir_observacao(e.get("observacao"))
        })

        ordem += 1

    return registros


def houve_repactuacao_no_ano(
    contrato_id: int,
    historicos: dict,
    ano: int
) -> bool:
    """
    Verifica se houve repactuação/reajuste no exercício informado,
    com base em Termo de Apostilamento ou Termo Aditivo com REAJUSTE.
    """

    eventos = historicos.get(str(contrato_id), [])

    if not eventos:
        return False

    for ev in eventos:
        # -------- DATA DO EVENTO --------
        data_evento = ev.get("data_assinatura") or ev.get("data_publicacao")

        try:
            if pd.to_datetime(data_evento).year != ano:
                continue
        except Exception:
            continue

        tipo = (ev.get("tipo") or "").lower()

        # -------- REGRA 1: APOSTILAMENTO --------
        if "apostilamento" in tipo:
            return True


    return False