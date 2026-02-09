import streamlit as st
import pandas as pd
from processing.projecao import projecao_ate_dezembro

from processing.visao_contratos import montar_tabela_contratos
from processing.utils import formatar

st.set_page_config(layout="wide")
st.title("📊 Painel Executivo de Contratos")

@st.cache_data
def carregar():
    import json
    with open("data/raw/contratos.json", encoding="utf-8") as f:
        contratos = json.load(f)
    with open("data/raw/historicos.json", encoding="utf-8") as f:
        historicos = json.load(f)
    with open("data/raw/empenhos.json", encoding="utf-8") as f:
        empenhos = json.load(f)

    return contratos, historicos, empenhos

contratos, historicos, empenhos = carregar()
ano = st.number_input("Exercício", value=2025)

df = montar_tabela_contratos(
    contratos,
    historicos,
    empenhos,
    ano
)

st.divider()

total_exercicio = df["Valor exercício"].sum()
total_empenhado = df["Empenhado"].sum()
gap_total = df["Gap"].sum()

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("Contratos ativos", len(df))
col2.metric("Valor exercício", formatar(total_exercicio))
col3.metric("Empenhado", formatar(total_empenhado))
col4.metric("Gap geral", formatar(gap_total))

criticos = df[df["Gap"] > 100000].shape[0]
col5.metric("Contratos críticos", criticos)

proj_empenho, proj_pago = projecao_ate_dezembro(empenhos, ano)
st.divider()
st.subheader("📈 Projeção até dezembro")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Empenhado projetado",
    formatar(proj_empenho)
)

col2.metric(
    "Pago projetado",
    formatar(proj_pago)
)

col3.metric(
    "Diferença p/ exercício",
    formatar(df["Valor exercício"].sum() - proj_empenho)
)


st.divider()
st.subheader("⚠️ Alertas gerenciais")

hoje = pd.Timestamp.today()

df["Vigência fim dt"] = pd.to_datetime(df["Vigência fim"])
a_encerrar = df[df["Vigência fim dt"] <= hoje + pd.Timedelta(days=90)]

sem_empenho = df[df["Empenhado"] == 0]
alto_gap = df[df["Gap"] > 50000]

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Encerram em 90 dias", len(a_encerrar))
    st.dataframe(a_encerrar[["Contrato","Vigência fim"]].head(5))

with col2:
    st.metric("Sem empenho", len(sem_empenho))
    st.dataframe(sem_empenho[["Contrato","Valor exercício"]].head(5))

with col3:
    st.metric("Gap alto", len(alto_gap))
    st.dataframe(alto_gap[["Contrato","Gap"]].head(5))


st.divider()
st.subheader("💰 Distribuição financeira")

cat = df.groupby("Categoria")["Valor exercício"].sum().sort_values(ascending=False)
st.bar_chart(cat)

forn = df.groupby("Fornecedor")["Valor exercício"].sum().sort_values(ascending=False).head(10)
st.bar_chart(forn)


st.divider()
st.subheader("🏆 Maiores contratos")

top = df.sort_values("Valor exercício", ascending=False).head(10)
top["Valor exercício"] = top["Valor exercício"].apply(formatar)

st.dataframe(top[["Contrato","Fornecedor","Valor exercício"]], use_container_width=True)


st.divider()
st.subheader("📋 Visão completa")

df_exib = df.copy()

for col in ["Valor exercício","Empenhado","Gap"]:
    df_exib[col] = df_exib[col].apply(formatar)

st.dataframe(df_exib, use_container_width=True, height=500)
