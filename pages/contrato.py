import streamlit as st
import json
from datetime import datetime

from processing.calculo_exercicio import (
    calcular_valor_exercicio_debug,
)

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

st.set_page_config(layout="wide")
st.title("📑 Análise detalhada do contrato")

ANO_TESTE = st.number_input(
    "Ano de referência",
    value=2025,
    step=1
)

# ---------------------------------------------------------
# CARREGAR BASE
# ---------------------------------------------------------

@st.cache_data
def carregar_dados():
    with open("data/raw/contratos.json", encoding="utf-8") as f:
        contratos = json.load(f)

    with open("data/raw/historicos.json", encoding="utf-8") as f:
        historicos = json.load(f)

    return contratos, historicos


contratos, historicos = carregar_dados()

# ---------------------------------------------------------
# SELEÇÃO DO CONTRATO
# ---------------------------------------------------------

mapa_contratos = {
    f'{c["numero"]} | {c["fornecedor"]["nome"]}': c
    for c in contratos
}

escolha = st.selectbox(
    "Selecione o contrato",
    list(mapa_contratos.keys())
)

contrato = mapa_contratos[escolha]
historico = historicos.get(str(contrato["id"]), [])

# ---------------------------------------------------------
# DADOS GERAIS
# ---------------------------------------------------------

st.subheader("📋 Dados do contrato")

c1, c2, c3 = st.columns(3)

c1.write(f"Número: {contrato['numero']}")
c2.write(f"Fornecedor: {contrato['fornecedor']['nome']}")
c3.write(f"Categoria: {contrato.get('categoria')}")

c4, c5, c6 = st.columns(3)

c4.write(f"Início: {contrato['vigencia_inicio']}")
c5.write(f"Fim: {contrato['vigencia_fim']}")
c6.write(f"Valor global: {contrato['valor_global']}")

# ---------------------------------------------------------
# HISTÓRICO
# ---------------------------------------------------------

st.subheader("📜 Histórico bruto")

if historico:
    st.dataframe(historico, use_container_width=True)
else:
    st.info("Sem histórico encontrado")

# ---------------------------------------------------------
# CÁLCULO DO EXERCÍCIO
# ---------------------------------------------------------

st.subheader("🧮 Cálculo do exercício")

valor, logs = calcular_valor_exercicio_debug(
    contrato,
    historico,
    ANO_TESTE
)

st.metric("Valor do exercício calculado", f"R$ {valor:,.2f}")

# ---------------------------------------------------------
# DEBUG DETALHADO
# ---------------------------------------------------------

st.subheader("🔍 Auditoria do cálculo")

if not logs:
    st.info("Nenhuma etapa registrada.")
else:
    for etapa in logs:
        with st.expander(etapa["tipo"]):
            st.json(etapa)
