import streamlit as st
import pandas as pd

from processing.visao_contratos import montar_tabela_contratos
from processing.utils import formatar
from services.contratos import ContratosService
from services.api_client import APIClient

st.set_page_config(layout="wide")
st.title("📊 Gestão Financeira de Contratos")

# -------------------------------------------------
# MODAL FATURAS (CHAMADA API)
# -------------------------------------------------

@st.dialog("Faturas do contrato", width="large")
def abrir_faturas_modal(contrato):
    import pandas as pd
    from services.contratos import ContratosService
    from services.api_client import APIClient

    client = APIClient("https://contratos.comprasnet.gov.br/api")
    service = ContratosService(client)

    link = contrato["links"]["faturas"]

    with st.spinner("Buscando faturas..."):
        faturas = service.obter_link_api(link)

    if not faturas:
        st.info("Sem faturas")
        return

    df_f = pd.DataFrame(faturas)

    if "valor" in df_f.columns:
        df_f["valor"] = df_f["valor"].apply(formatar)

    st.dataframe(df_f, use_container_width=True)

# -------------------------------------------------
# CARREGAR BASE
# -------------------------------------------------

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


contratos, historicos, empenhos_base = carregar()

ano_referencia = st.number_input("Ano", value=2025)

df = montar_tabela_contratos(
    contratos,
    historicos,
    empenhos_base,
    ano_referencia
)

# -------------------------------------------------
# KPIs
# -------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Contratos ativos", len(df))
col2.metric("Total exercício", formatar(df["Valor exercício"].sum()))
col3.metric("Total a reforçar", formatar(df[df["Gap"] > 0]["Gap"].sum()))
col4.metric(
    "Total a anular",
    formatar(abs(df[df["Gap"] < 0]["Gap"].sum()))
)



st.divider()

# -------------------------------------------------
# LAYOUT
# -------------------------------------------------

col_tabela, col_painel = st.columns([2, 1])

# -------------------------------------------------
# TABELA
# -------------------------------------------------

def cor_status(val):
    if "Reforçar" in val:
        return "background-color:#ffe5e5"
    if "Anular" in val:
        return "background-color:#fff4cc"
    if "OK" in val:
        return "background-color:#e6ffe6"
    return ""

df_exib = df.copy()

for col in ["Valor exercício","Empenhado","Liquidado + Pago","A liquidar","Gap"]:
    df_exib[col] = df_exib[col].apply(formatar)

df_exib["Objeto"] = df_exib["Objeto"].str[:60] + "..."

df_style = df_exib.style.applymap(cor_status, subset=["Situação"])

with col_tabela:
    tabela_sel = st.dataframe(
        df_style,
        use_container_width=True,
        height=600,
        on_select="rerun",
        selection_mode="single-row"
    )

# -------------------------------------------------
# PAINEL
# -------------------------------------------------

with col_painel:
    st.subheader("🔎 Análise do contrato")

    if tabela_sel and tabela_sel.selection.rows:

        idx = tabela_sel.selection.rows[0]
        linha = df.iloc[idx]

        numero = linha["Contrato"]
        contrato = next(c for c in contratos if c["numero"] == numero)
        cid = str(contrato["id"])

        st.markdown(f"### {numero}")
        st.caption(contrato["fornecedor"]["nome"])

        st.metric("Valor exercício", formatar(linha["Valor exercício"]))
        st.metric("Empenhado", formatar(linha["Empenhado"]))
        st.metric("Gap", formatar(linha["Gap"]))

        st.divider()

        # -------------------------------------------------
        # BOTÃO MODAL FATURAS
        # -------------------------------------------------

        if st.button("📄 Ver faturas", use_container_width=True):
            abrir_faturas_modal(contrato)


    else:
        st.info("Selecione um contrato")



