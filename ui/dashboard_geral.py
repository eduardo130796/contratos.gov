import streamlit as st
import pandas as pd
from processing.prazos import dias_para_encerrar


# =========================================================
# REGRAS DE NEGÓCIO (gestão contratual)
# =========================================================

def contrato_ativo_vigente(c):
    if c.get("situacao") != "Ativo":
        return False

    dias = dias_para_encerrar(c.get("vigencia_fim"))
    if dias is None:
        return True  # regra conservadora

    return dias >= 0


def classificar_status_prazo(dias):
    if dias is None:
        return "Sem vigência"
    if dias < 0:
        return "🔴 Vencido"
    if dias <= 30:
        return "🔴 Crítico"
    if dias <= 60:
        return "🟡 Alerta"
    return "🟢 Regular"


def parse_valor(v):
    if not v:
        return 0.0
    return float(v.replace(".", "").replace(",", "."))


# =========================================================
# DASHBOARD GERAL
# =========================================================

def render_dashboard(contratos):

    st.title("📊 Dashboard Gerencial de Contratos")

    # =====================================================
    # PREPARAÇÃO DOS DADOS
    # =====================================================
    dados = []

    for c in contratos:
        dias = dias_para_encerrar(c.get("vigencia_fim"))

        dados.append({
            "ID": c["id"],
            "Contrato": c["numero"],
            "Fornecedor": c["fornecedor"]["nome"],
            "Categoria": c.get("categoria"),
            "Situação": c.get("situacao"),
            "Dias": dias,
            "Status Prazo": classificar_status_prazo(dias),
            "Valor Global": parse_valor(c.get("valor_global")),
            "Ativo Vigente": contrato_ativo_vigente(c)
        })

    df = pd.DataFrame(dados)

    # =====================================================
    # BLOCO 1 — KPIs DE GESTÃO (PANORAMA)
    # =====================================================
    total_contratos = len(df)
    ativos_vigentes = df["Ativo Vigente"].sum()
    vencidos = (df["Dias"] < 0).sum()
    criticos = ((df["Dias"] <= 30) & (df["Dias"] >= 0)).sum()
    alerta = ((df["Dias"] <= 60) & (df["Dias"] > 30)).sum()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Contratos cadastrados", total_contratos)
    c2.metric("Ativos vigentes", ativos_vigentes)
    c3.metric("Vencidos", vencidos)
    c4.metric("Críticos (≤30 dias)", criticos)
    c5.metric("Alerta (≤60 dias)", alerta)

    st.divider()

    # =====================================================
    # BLOCO 2 — DIAGNÓSTICO AUTOMÁTICO
    # =====================================================
    if vencidos > 0:
        st.error("Há contratos vencidos. Ação imediata necessária.")
    elif criticos > 0:
        st.warning("Existem contratos em fase crítica de encerramento.")
    elif alerta > 0:
        st.info("Existem contratos que exigem atenção nos próximos 60 dias.")
    else:
        st.success("Carteira contratual estável no momento.")

    # =====================================================
    # BLOCO 3 — AGENDA DE GESTÃO (PRIORIDADE)
    # =====================================================
    st.subheader("⏳ Contratos que exigem ação")

    df_risco = df[
        df["Status Prazo"].isin(["🔴 Vencido", "🔴 Crítico", "🟡 Alerta"])
    ].sort_values("Dias")

    if df_risco.empty:
        st.success("Nenhum contrato em risco de prazo.")
    else:
        st.dataframe(
            df_risco[[
                "Contrato",
                "Fornecedor",
                "Categoria",
                "Dias",
                "Status Prazo"
            ]],
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # =====================================================
    # BLOCO 4 — PERFIL DA CARTEIRA CONTRATUAL
    # =====================================================
    st.subheader("📌 Perfil da carteira")

    col1, col2 = st.columns(2)

    with col1:
        st.caption("Distribuição por categoria")
        cat = (
            df[df["Ativo Vigente"]]
            .groupby("Categoria")
            .size()
            .sort_values(ascending=False)
        )
        st.bar_chart(cat)

    with col2:
        st.caption("Concentração por fornecedor (top 10)")
        forn = (
            df[df["Ativo Vigente"]]
            .groupby("Fornecedor")
            .size()
            .sort_values(ascending=False)
            .head(10)
        )
        st.bar_chart(forn)

    st.divider()

    # =====================================================
    # BLOCO 5 — ACESSO AO CONTRATO
    # =====================================================
    st.subheader("🔍 Análise individual de contrato")

    contrato_id = st.selectbox(
        "Selecione o contrato",
        df.sort_values("Dias", na_position="last")["ID"]
    )

    if st.button("Abrir contrato"):
        st.session_state["contrato_id"] = contrato_id
        st.switch_page("pages/contrato.py")
