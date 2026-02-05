import json
import streamlit as st
import pandas as pd
from processing.prazos import dias_para_encerrar
from processing.financeiro import consolidar_empenhos
from datetime import datetime
from processing.utils import formatar
from processing.calculo_exercicio import calcular_valor_exercicio
from processing.visao_contratos import montar_tabela_contratos

st.set_page_config(
    page_title="Dashboard Gerencial de Contratos",
    layout="wide"
)

ano_referencia = datetime.now().year
#ano_referencia = 2025
# ================= CARREGAMENTO =================

with open("data/raw/contratos.json", encoding="utf-8") as f:
    contratos = json.load(f)

with open("data/raw/empenhos.json", encoding="utf-8") as f:
    empenhos_base = json.load(f)

with open("data/raw/historicos.json", encoding="utf-8") as f:
    historicos = json.load(f)

# ================= NORMALIZAÇÃO =================

registros = []

for c in contratos:
    dias = dias_para_encerrar(c.get("vigencia_fim"))
    empenhos_contrato = empenhos_base.get(str(c["id"]), [])

    valor_empenhado, valor_aliquidar, valor_liquidado, valor_pago = consolidar_empenhos(
        empenhos_contrato,
        ano_referencia
    )

    historico_contrato = historicos.get(str(c["id"]), [])

    valor_exercicio = calcular_valor_exercicio(
        c,
        historico_contrato,
        ano_referencia
    )

    registros.append({
        "ID": c["id"],
        "Contrato": c["numero"],
        "Fornecedor": c["fornecedor"]["nome"],
        "Categoria": c.get("categoria", "Não informada"),
        "Situação": c.get("situacao"),
        "Dias para encerrar": dias,
        "Valor Global": (
            float(c["valor_global"].replace(".", "").replace(",", "."))
            if c.get("valor_global") else 0
        ),
        # financeiro do ano
        "Empenhado (Ano)": valor_empenhado,
        "A liquidar (Ano)": valor_aliquidar,
        "Liquidado (Ano)": valor_liquidado,
        "Pago (Ano)": valor_pago,
        # NOVO: valor do exercício
        "Valor Exercício": valor_exercicio,
    })

df = pd.DataFrame(registros)

# ================= KPIs =================

total = len(df)
ativos = df[df["Situação"] == "Ativo"]
ativos = df[
    df["Dias para encerrar"].notnull() &
    (df["Dias para encerrar"] >= 0)
]
vencidos = df[
    df["Dias para encerrar"].notnull() &
    (df["Dias para encerrar"] < 0)
]

criticos = ativos[
    ativos["Dias para encerrar"] <= 30
]

alerta = ativos[
    (ativos["Dias para encerrar"] > 30) &
    (ativos["Dias para encerrar"] <= 60)
]


valor_empenhado_total = ativos["Empenhado (Ano)"].sum()
valor_liquidado_total = ativos["Liquidado (Ano)"].sum()
valor_aliquidar_total = ativos["A liquidar (Ano)"].sum()
valor_exercicio_total = ativos["Valor Exercício"].sum()

gap_total = valor_exercicio_total - valor_empenhado_total

valor_pago_total = ativos["Pago (Ano)"].sum()

percentual_execucao = (
    ((valor_pago_total+valor_liquidado_total) / valor_empenhado_total) * 100
    if valor_empenhado_total > 0 else 0
)

# ================= HEADER =================

st.title("📊 Dashboard Gerencial de Contratos")

st.subheader("Contratos")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total de contratos", total)
c2.metric("Contratos ativos", len(ativos))
c3.metric("Vencidos", len(vencidos))
c4.metric("Críticos (≤30 dias)", len(criticos))
c5.metric("Alerta (≤60 dias)", len(alerta))

st.divider()

st.subheader("Orçamentário")
c6, c7, c8, c9, c10 = st.columns(5)
c6.metric("Empenhado (Ano)", formatar(valor_empenhado_total))
c7.metric("A liquidar (Ano)", formatar(valor_aliquidar_total))
c8.metric("Liquidado/Pago (Ano)", formatar(valor_liquidado_total+valor_pago_total))
c9.metric("Execução (%)", f"{percentual_execucao:.1f}%")

st.divider()

st.subheader("Impacto Orçamentário")
c11, c12, c13 = st.columns(3)
c11.metric("Impacto contratual no exercício", formatar(valor_exercicio_total))
c12.metric("Empenhado no exercício", formatar(valor_empenhado_total))
c13.metric("Gap contratual", formatar(gap_total))

sem_empenho = ativos[
    ativos["Empenhado (Ano)"] == 0
]

if not sem_empenho.empty:
    st.warning(
        f"⚠️ {len(sem_empenho)} contratos vigentes sem empenho no exercício {ano_referencia}."
    )
else:
    st.success("🟢 Todos os conratos vigentes estão com empenho no momento.")

st.divider()

df = montar_tabela_contratos(
    contratos,
    historicos,
    empenhos_base,
    ano_referencia)

df_exibicao = df.copy()

for col in [
    "Valor exercício",
    "Empenhado",
    "Liquidado + Pago",
    "A liquidar",
    "Gap"
]:
    df_exibicao[col] = df_exibicao[col].apply(formatar)


st.dataframe(
    df_exibicao,
    use_container_width=True
)

# ================= AGENDA DE GESTÃO =================

st.subheader("⏳ Contratos que exigem ação")

df_risco = ativos[
    ativos["Dias para encerrar"].notnull() &
    (ativos["Dias para encerrar"] <= 60)
].sort_values("Dias para encerrar")

if df_risco.empty:
    st.success("Nenhum contrato em risco de prazo.")
else:
    st.dataframe(
        df_risco[[
            "Contrato",
            "Fornecedor",
            "Categoria",
            "Dias para encerrar"
        ]],
        use_container_width=True,
        hide_index=True
    )

st.divider()

# ================= PERFIL DA CARTEIRA =================

st.subheader("📌 Perfil Contratual")

col1, col2 = st.columns(2)

with col1:
    st.caption("Contratos ativos por categoria")
    st.bar_chart(
        ativos.groupby("Categoria").size().sort_values(ascending=False)
    )

with col2:
    st.caption("Top 10 fornecedores (contratos ativos)")
    st.bar_chart(
        ativos.groupby("Fornecedor").size().sort_values(ascending=False).head(10)
    )

st.divider()

# ================= ACESSO AO CONTRATO =================

st.subheader("🔍 Análise individual de contrato")

contrato_id = st.selectbox(
    "Selecione o contrato",
    ativos.sort_values("Dias para encerrar")["ID"]
)

if st.button("Abrir contrato"):
    st.session_state["contrato_id"] = contrato_id
    st.switch_page("pages/contrato.py")

