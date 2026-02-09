import json
import streamlit as st
import pandas as pd
from processing.prazos import dias_para_encerrar
from processing.financeiro import consolidar_empenhos
from datetime import datetime
from processing.utils import formatar
from processing.calculo_exercicio import calcular_valor_exercicio
from processing.visao_contratos import montar_tabela_contratos
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from services.contratos import ContratosService
from services.api_client import APIClient




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
# ================= TABELA =================
def obter_historico_local(contrato_id, historicos):
    """
    Retorna TODO o histórico do contrato, independente do exercício.
    """
    
    registros = historicos.get(str(contrato_id), [])

    if not registros:
        return pd.DataFrame()

    df = pd.DataFrame(registros)

    # ordenação temporal (se existir)
    if "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.sort_values("data")

    return df

import requests

def obter_faturas_contrato_api(contrato_obj):
    """
    contrato_obj: objeto do contrato vindo do contratos.json
    Retorna DataFrame com faturas
    """

    client = APIClient("https://contratos.comprasnet.gov.br/api")
    service = ContratosService(client)

    link = contrato_obj["links"]["faturas"]

    faturas = service.obter_link_api(link)

    if not faturas:
        return pd.DataFrame()

    df = pd.DataFrame(faturas)

    return df


@st.cache_data(show_spinner=False, ttl=3600)
def carregar_faturas_contrato_cache(contrato_id, contratos):
    """
    Cache por contrato
    """
    contrato_obj = next(
        (c for c in contratos if c["numero"] == contrato_id),
        None
    )

    if not contrato_obj:
        return pd.DataFrame()

    return obter_faturas_contrato_api(contrato_obj)

def formatar_data(valor):
    """
    Converte datas ISO / datetime / string para DD/MM/AAAA.
    Retorna '—' se inválido ou vazio.
    """
    if not valor:
        return "—"

    try:
        data = pd.to_datetime(valor, errors="coerce")
        if pd.isna(data):
            return "—"
        return data.strftime("%d/%m/%Y")
    except Exception:
        return "—"


def moeda_para_float(valor):
    """
    Converte string monetária brasileira para float.
    Ex: '73.895,79' -> 73895.79
    """
    if valor is None:
        return 0.0

    if isinstance(valor, (int, float)):
        return float(valor)

    return float(
        valor.replace(".", "").replace(",", ".")
    )


def obter_empenhos_contrato(contrato_id, empenhos_base):
    registros = empenhos_base.get(str(contrato_id), [])

    if not registros:
        return pd.DataFrame()

    df = pd.DataFrame(registros)

    for col in [
        "empenhado", "aliquidar", "liquidado", "pago",
        "rpinscrito", "rpaliquidado", "rppago"
    ]:
        if col in df.columns:
            df[col] = df[col].apply(moeda_para_float)

    return df

def card_empenho(e):
    with st.container(border=True):

        # =====================================================
        # 🔝 CABEÇALHO — IDENTIDADE
        # =====================================================
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(
                f"**🧾 NE {e.get('numero') or '—'}**"
            )
        st.caption(e.get("credor") or "—")

        with col2:
            if e.get("data_emissao"):
                st.caption(f"📅 **Data de Emissão: {formatar_data(e['data_emissao'])}**")

        # =====================================================
        # 💰 FINANCEIRO — LINHA 1
        # =====================================================
        empenhado = moeda_para_float(e.get("empenhado", 0))
        liquidado = moeda_para_float(e.get("liquidado", 0))
        pago = moeda_para_float(e.get("pago", 0))
        aliquidar = moeda_para_float(e.get("aliquidar", 0))

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Empenhado:** {formatar(empenhado)}")
            st.markdown(f"**A liquidar:** {formatar(aliquidar)}")
            st.markdown(f"**Liquidado:** {formatar(liquidado)}")
            st.markdown(f"**Pago:** {formatar(pago)}")
            

        with col2:
            # =====================================================
            # 💰 RESTOS A PAGAR — SEMPRE VISÍVEL (SE EXISTIR)
            # =====================================================
            rp_inscrito = moeda_para_float(e.get("rpinscrito", 0))
            rp_aliquidar = moeda_para_float(e.get("rpaliquidar", 0))
            rp_liquidado = moeda_para_float(e.get("rpliquidado", 0))
            rp_pago = moeda_para_float(e.get("rppago", 0))

            if rp_inscrito > 0 or rp_pago > 0:
                st.markdown(f"""**RP Inscrito:** {formatar(rp_inscrito)}""")
                st.markdown(f""" **RP A Liquidar:** {formatar(rp_aliquidar)}  """)
                st.markdown(f""" **RP Liquidado:** {formatar(rp_liquidado)}  """)
                st.markdown(f""" **RP pago:** {formatar(rp_pago)}  """)

        # =====================================================
        # 🚦 STATUS SIMPLES
        # =====================================================
        if empenhado == 0:
            st.error("Sem valor empenhado")
        elif aliquidar > 0:
            st.warning("Saldo pendente de liquidação")
        else:
            st.success("Empenho executado")

        # =====================================================
        # 🔽 DETALHES ORÇAMENTÁRIOS (SOB DEMANDA)
        # =====================================================
        with st.expander("Detalhes orçamentários"):

            st.markdown(
                f"""
                **Fonte de recurso:** {e.get("fonte_recurso") or "—"}  
                **Programa de trabalho:** {e.get("programa_trabalho") or "—"}  
                **Natureza da despesa:** {e.get("naturezadespesa") or "—"}  
                **Plano interno:** {e.get("planointerno") or "—"}  
                """
            )

            link = e.get("links", {}).get("documento_pagamento")
            if link:
                st.link_button("🔗 Ver ordem bancária", link)

def card_impacto_orcamentario_md(valor_exercicio, empenhado):
    diferenca = valor_exercicio - empenhado

    # ============================
    # 🔴 REFORÇO NECESSÁRIO
    # ============================
    if diferenca > 0:
        st.markdown(
            f"""
            <div style="
                background-color:#fde2e2;
                padding:16px;
                border-radius:8px;
                border-left:6px solid #dc2626;
            ">
                <div style="font-size:18px; font-weight:600; color:#7f1d1d;">
                    🚨 Reforço necessário
                </div>
                <div style="font-size:28px; font-weight:700; margin-top:8px; color:#7f1d1d;">
                    {formatar(diferenca)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # ============================
    # 🟢 ANULAÇÃO POSSÍVEL
    # ============================
    elif diferenca < 0:
        st.markdown(
            f"""
            <div style="
                background-color:#dcfce7;
                padding:16px;
                border-radius:8px;
                border-left:6px solid #16a34a;
            ">
                <div style="font-size:18px; font-weight:600; color:#065f46;">
                    🟢 Anulação possível
                </div>
                <div style="font-size:28px; font-weight:700; margin-top:8px; color:#065f46;">
                    {formatar(abs(diferenca))}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


    # ============================
    # ⚪ EQUILÍBRIO
    # ============================
    else:
        st.markdown(
        """
        <div style="
            background-color:#f3f4f6;
            padding:16px;
            border-radius:8px;
            border-left:6px solid #6b7280;
        ">
            <div style="font-size:18px; font-weight:600;">
                ⚪ Execução equilibrada
            </div>
            <div style="font-size:24px; font-weight:700; margin-top:8px;">
                R$ 0,00
            </div>
        </div>
        """,
        unsafe_allow_html=True
        )


def fmt_data(data):
    if not data:
        return "—"
    return pd.to_datetime(data).strftime("%d/%m/%Y")


def to_float(valor):
    if not valor:
        return 0.0
    return float(valor.replace(".", "").replace(",", "."))

def badge(texto, cor="#e5e7eb", texto_cor="#111827"):
    return f"""
    <span style="
        background-color:{cor};
        color:{texto_cor};
        padding:4px 8px;
        border-radius:6px;
        font-size:0.75rem;
        font-weight:600;
        margin-left:6px;
        ">
        {texto}
    </span>
    """

def competencia_fatura(f):
    refs = f.get("dados_referencia", [])
    if refs:
        mes = refs[0].get("mesref")
        ano = refs[0].get("anoref")
        if mes and ano:
            return f"{mes}/{ano}"
    # fallback
    if f.get("emissao"):
        dt = pd.to_datetime(f["emissao"], errors="coerce")
        if not pd.isna(dt):
            return dt.strftime("%m/%Y")
    return "—"


@st.dialog("📄 Contrato — Visão detalhada", width="large")
def modal_contrato(contrato_row):
    """
    contrato_row: Series ou dict com os dados do contrato selecionado
    """

    # ================= HEADER =================
    st.markdown(f"### 📄 Dados do contrato - {contrato_row['Contrato']}")

    grid1, grid2= st.columns(2)

    with grid1:
        st.caption(f"Contrato: {contrato_row['Contrato']}")
        st.caption(f"Processo: {contrato_row.get('Processo', '—')}")
        st.caption(f"Categoria: {contrato_row.get('Categoria', '—')}")
        st.caption(f"Objeto: {contrato_row.get('Objeto', '—')}")
        st.caption(
            f"Vigência: {formatar_data(contrato_row.get('Vigência inicio', '—'))} "
            f"a {formatar_data(contrato_row.get('Vigência fim', '—'))}"
        )

    with grid2:
        st.caption(f"Fornecedor: {contrato_row['Fornecedor']}")
        st.caption(f"CNPJ: {contrato_row.get('Cnpj', '—')}")
        st.caption(f"Modalidade: {contrato_row.get('modalidade', '—')}")
        st.caption(f"Valor global: {contrato_row.get('Valor global', 0)}")
        st.caption(f"Valor da parcela: {contrato_row.get('valor_parcela', 0)}")

    if contrato_row.get("Repactuação/Reajuste") == "Sim":
        st.warning(
            f"🔁 Repactuação/Reajuste no exercício "
            f"({contrato_row.get('Qtd. repactuações', 1)}x)"
        )
    else:
        st.info("Sem repactuação no exercício")

    st.divider()

    # ================= ABAS =================
    tab_resumo, tab_faturas, tab_evolucao, tab_historico = st.tabs(
        ["📌 Resumo", "📄 Faturas", "📈 Evolução", "🕓 Histórico"]
    )

    # =========================================================
    # 📌 ABA 1 — RESUMO
    # =========================================================
    with tab_resumo:
        # =====================================================
        # 🔹 EMPENHOS FILTRADOS
        # =====================================================
        df_empenhos = obter_empenhos_contrato(
            contrato_row["ID"],
            empenhos_base
        )

        df_empenhos["ano"] = pd.to_datetime(
            df_empenhos["data_emissao"],
            errors="coerce"
        ).dt.year

        # fallback: ano pela própria NE (ex: 2019NE800152)
        df_empenhos["ano"] = df_empenhos["ano"].fillna(
            df_empenhos["numero"].str[:4].astype("float")
        )

        # =====================================================
        # 🔹 CONTEXTO TEMPORAL
        # =====================================================
        st.markdown("### 🗓️ Exercício")

        anos_disponiveis = sorted(
            df_empenhos["ano"].dropna().unique().astype(int)
        )

        anos_selecionados = st.multiselect(
            "Exercício",
            anos_disponiveis,
            default=[ano_referencia] if ano_referencia in anos_disponiveis else anos_disponiveis
        )

        if anos_selecionados:
            df_empenhos = df_empenhos[df_empenhos["ano"].isin(anos_selecionados)]

        
        # =====================================================
        # 🔹 CARDS — VISÃO FINANCEIRA
        # =====================================================
        st.markdown("### 💰 Visão financeira consolidada")

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            st.metric("Valor do Exercício", formatar(contrato_row["Valor exercício"]))

        with c2:
            st.metric("Empenhado", formatar(contrato_row["Empenhado"]))

        with c3:
            st.metric("A Liquidar", formatar(contrato_row["A liquidar"]))

        with c4:
            st.metric("Pago", formatar(contrato_row["Liquidado + Pago"]))
        
        with c5:
            card_impacto_orcamentario_md(
                contrato_row["Valor exercício"],
                contrato_row["Empenhado"]
            )



            

        st.markdown("### 📄 Notas de empenho")

        if df_empenhos.empty:
            st.info("Nenhuma nota de empenho encontrada para o período selecionado.")
        else:
            # Cards em grid (2 por linha)
            cols = st.columns(2)

            for i, (_, row) in enumerate(df_empenhos.iterrows()):
                with cols[i % 2]:
                    card_empenho(row)





    # =========================================================
    # 📄 ABA 2 — FATURAS
    # =========================================================
    with tab_faturas:
        
        st.markdown("### 📄 Faturas do contrato")

        with st.spinner("Buscando faturas..."):
            df_faturas = carregar_faturas_contrato_cache(
                contrato_row["Contrato"],
                contratos
            )

        if df_faturas.empty:
            st.info("Nenhuma fatura encontrada para este contrato.")
            st.stop()

        # ==============================
        # NORMALIZAÇÃO
        # ==============================
        df_faturas["valor_float"] = df_faturas["valor"].apply(to_float)
        df_faturas["valor_liquido_float"] = df_faturas["valorliquido"].apply(to_float)
        df_faturas["juros_float"] = df_faturas["juros"].apply(to_float)
        df_faturas["multa_float"] = df_faturas["multa"].apply(to_float)
        df_faturas["glosa_float"] = df_faturas["glosa"].apply(to_float)

        df_faturas["ano"] = pd.to_datetime(df_faturas["emissao"], errors="coerce").dt.year
        df_faturas["mes"] = pd.to_datetime(df_faturas["emissao"], errors="coerce").dt.month

        # ==============================
        # FILTROS
        # ==============================
        colf1, colf2 = st.columns(2)

        anos = sorted(df_faturas["ano"].dropna().unique().astype(int).tolist())
        anos_sel = colf1.multiselect(
            "Ano de emissão",
            anos,
            default=anos
        )

        if anos_sel:
            df_faturas = df_faturas[df_faturas["ano"].isin(anos_sel)]

        # ==============================
        # KPIs
        # ==============================
        total_faturas = len(df_faturas)
        total_liquido = df_faturas["valor_liquido_float"].sum()
        total_glosa = df_faturas["glosa_float"].sum()
        qtd_repact = (df_faturas["repactuacao"] == "Sim").sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Qtd. faturas", total_faturas)
        c2.metric("Valor líquido", formatar(total_liquido))
        c3.metric("Glosas", formatar(total_glosa))
        c4.metric("Repactuadas", qtd_repact)

        st.markdown("---")

        # ==============================
        # SUB-ABAS
        # ==============================
        tab_lista, tab_graficos = st.tabs(["📋 Lista", "📊 Gráficos"])

        # =========================================================
        # 📋 LISTA DE FATURAS
        # =========================================================
        with tab_lista:
            for _, f in df_faturas.sort_values("emissao", ascending=False).iterrows():

                valor = formatar(f["valor_liquido_float"])
                liquidada = "🟢 Liquidada" if f["data_liquidacao"] else "🟡 Pendente"

                empenhos = f.get("dados_empenho", [])
                empenhos_str = " / ".join(
                    e["numero_empenho"] for e in empenhos
                ) if empenhos else "—"

                badge_rep = ""
                if f.get("repactuacao") == "Sim":
                    badge_rep = """<span style="
                        background-color:#fde68a;
                            color:#92400e;
                            padding:4px 8px;
                            border-radius:6px;
                            font-size:0.75rem;
                            font-weight:600;
                            vertical-align:middle;
                        ">Repactuação</span>
                    """


                with st.container(border=True):
                    competencia = competencia_fatura(f)
                    st.markdown(f"""<div style="
                            display:flex;
                            align-items:center;
                            gap:8px;
                            margin-bottom:6px;
                        "><strong>Competência:</strong>
                            <span>{competencia}</span>
                            {badge_rep}</div>
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        f"""   
                        **Valor líquido:** **{valor}**  
                        **Situação:** {liquidada}  
                        **Empenho:** {empenhos_str}
                        """,
                        unsafe_allow_html=True
                    )

                    # ALERTAS FORA DO EXPANDER
                    if f["glosa_float"] > 0:
                        st.error(f"Glosa aplicada: {formatar(f['glosa_float'])}")

                    if f["juros_float"] > 0 or f["multa_float"] > 0:
                        st.warning(
                            f"Encargos — Juros: {formatar(f['juros_float'])} | "
                            f"Multa: {formatar(f['multa_float'])}"
                        )

                    with st.expander("🔍 Detalhes da fatura"):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown(f"""
                            **Nota Fiscal:** {f["numero"]} / Série {f["numero_serie"]}  
                            **Emissão:** {fmt_data(f["emissao"])}  
                            **Vencimento:** {fmt_data(f["vencimento"])}  
                            **Liquidação:** {fmt_data(f["data_liquidacao"])}  
                            **Processo:** {f.get("processo", "—")}
                            """)

                        with col2:
                            st.markdown(f"""
                            **Fonte:** {f.get("fonte_recurso", "—")}  
                            **Plano interno:** {f.get("planointerno", "—")}  
                            **Natureza:** {f.get("naturezadespesa", "—")}  
                            **Ateste:** {fmt_data(f.get("ateste"))}
                            """)

        # =========================================================
        # 📊 GRÁFICOS
        # =========================================================
        with tab_graficos:
            st.markdown("### 📊 Evolução do faturamento")

            df_chart = (
                df_faturas
                .groupby(["ano", "mes"], as_index=False)
                .agg(valor=("valor_liquido_float", "sum"))
            )

            if not df_chart.empty:
                st.line_chart(
                    df_chart.pivot(index="mes", columns="ano", values="valor")
                )
            else:
                st.info("Sem dados suficientes para gráfico.")


    # =========================================================
    # 📈 ABA 3 — EVOLUÇÃO
    # =========================================================
    with tab_evolucao:
        st.markdown("### Evolução financeira no exercício")

        st.info(
            "Esta aba exibirá a evolução mensal do contrato "
            "comparando empenho, liquidação e pagamento."
        )

        # Exemplo futuro:
        # st.line_chart(df_evolucao)

    # =========================================================
    # 🕓 ABA 4 — HISTÓRICO
    # =========================================================
    with tab_historico:
        df_hist = obter_historico_local(
        contrato_row["ID"],
        historicos
        )

        if df_hist.empty:
            st.info("Nenhum histórico registrado para este contrato.")
        else:
            st.dataframe(df_hist, use_container_width=True)

    # ================= FOOTER =================
    st.divider()



@st.cache_data(show_spinner=False)
def carregar_df_base():
    return montar_tabela_contratos(
        contratos,
        historicos,
        empenhos_base,
        ano_referencia
    )

df_base = carregar_df_base()


st.subheader("📑 Visão financeira dos contratos")

col_f1, col_f2 = st.columns(2)

filtro_risco = col_f1.selectbox(
    "Filtro rápido",
    ["Todos", "Com Gap negativo", "Sem empenho"]
)

filtro_fornecedor = col_f2.text_input(
    "Buscar por fornecedor",
    placeholder="Digite parte do nome"
)



df_filtrado = df_base.copy()

faixa_gap = col_f1.selectbox(
    "Faixa de Gap",
    [
        "Todos",
        "Gap negativo",
        "Gap até R$ 10 mil",
        "Gap acima de R$ 50 mil"
    ]
)

if faixa_gap == "Gap negativo":
    df_filtrado = df_filtrado[df_filtrado["Gap"] < 0]

elif faixa_gap == "Gap até R$ 10 mil":
    df_filtrado = df_filtrado[
        (df_filtrado["Gap"] < 0) &
        (df_filtrado["Gap"] >= -10_000)
    ]

elif faixa_gap == "Gap acima de R$ 50 mil":
    df_filtrado = df_filtrado[df_filtrado["Gap"] < -50_000]

valor_min, valor_max = col_f2.slider(
    "Valor do exercício (R$)",
    min_value=0,
    max_value=int(df_base["Valor exercício"].max()),
    value=(0, int(df_base["Valor exercício"].max()))
)

df_filtrado = df_filtrado[
    (df_filtrado["Valor exercício"] >= valor_min) &
    (df_filtrado["Valor exercício"] <= valor_max)
]

tipo_execucao = st.multiselect(
    "Situação financeira",
    ["Empenhado < Exercício", "Sem pagamento", "Totalmente pago"]
)

if "Empenhado < Exercício" in tipo_execucao:
    df_filtrado = df_filtrado[df_filtrado["Empenhado"] < df_filtrado["Valor exercício"]]

if "Sem pagamento" in tipo_execucao:
    df_filtrado = df_filtrado[df_filtrado["Liquidado + Pago"] == 0]

if "Totalmente pago" in tipo_execucao:
    df_filtrado = df_filtrado[
        df_filtrado["Liquidado + Pago"] >= df_filtrado["Valor exercício"]
    ]


if filtro_risco == "Com Gap negativo":
    df_filtrado = df_filtrado[df_filtrado["Gap"] < 0]

elif filtro_risco == "Sem empenho":
    df_filtrado = df_filtrado[df_filtrado["Empenhado"] == 0]

if filtro_fornecedor:
    df_filtrado = df_filtrado[
        df_filtrado["Fornecedor"]
        .str.contains(filtro_fornecedor, case=False, na=False)
    ]

if df_filtrado.empty:
    st.warning("Nenhum contrato encontrado com os filtros aplicados.")

COLUNAS_TABELA_PRINCIPAL = [
    "ID",
    "Contrato",
    "Fornecedor",
    "Categoria",
    "Nota(s) de empenho",
    "Valor anual",
    "Valor exercício",
    "Empenhado",
    "Liquidado + Pago",
    "Gap",
    "Situação",
    "Repactuação/Reajuste",
]

df_exibicao = df_filtrado[COLUNAS_TABELA_PRINCIPAL].copy()


for col in [
    "Valor anual",
    "Valor exercício",
    "Empenhado",
    "Liquidado + Pago",
    "Gap"
]:
    df_exibicao[col] = df_exibicao[col].apply(formatar)

gb = GridOptionsBuilder.from_dataframe(df_exibicao)

gb.configure_default_column(
    sortable=True,
    filter=True,
    resizable=True
)
gb.configure_column("Contrato", pinned="left", width=150)
gb.configure_column("Fornecedor", pinned="left", width=260)
gb.configure_column("Categoria", width=160)
gb.configure_column("Nota(s) de empenho", width=220, autoHeight=True)
gb.configure_column("Valor exercício", width=150)
gb.configure_column("Valor exercício", width=150)
gb.configure_column("Empenhado", width=140)
gb.configure_column("Liquidado + Pago", width=160)
gb.configure_column("Situação", width=160)
gb.configure_column("Gap", width=120)
gb.configure_column("Repactuação/Reajuste", width=160)
gb.configure_column("ID", hide=True)


gb.configure_selection(
    selection_mode="single",
    use_checkbox=False
)

gb.configure_grid_options(
    rowHeight=42,
    headerHeight=45
)
# Destaque visual sutil para risco
gb.configure_column(
    "Gap",
    cellStyle=JsCode("""
        function(params) {
            if (params.value && params.value.startsWith("R$ -")) {
                return { 'backgroundColor': '#fee2e2' };
            }
        }
    """)
)

# Ordenação automática por risco (Gap)
gb.configure_grid_options(
    sortModel=[
        {"colId": "Gap", "sort": "asc"}
    ],
    rowHeight=42,
    headerHeight=45
)


grid_options = gb.build()



grid_response = AgGrid(
    df_exibicao,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    theme="alpine",
    height=520,
    fit_columns_on_grid_load=True,
    allow_unsafe_jscode=True   # 👈 ESSENCIAL
)

selected = grid_response.get("selected_rows")



if selected is not None and not selected.empty:
    st.caption(
        f"Contrato selecionado: {selected.iloc[0]['Contrato']}"
    )
    contrato_num = selected.iloc[0]["Contrato"]
    contrato_row = df_base[df_base["Contrato"] == contrato_num].iloc[0]
    if st.session_state.get("contrato_modal_aberto") != contrato_row["Contrato"]:
        st.session_state["contrato_modal_aberto"] = contrato_row["Contrato"]
        st.session_state["abrir_modal"] = True
        st.session_state["contrato_row"] = contrato_row

if st.session_state.get("abrir_modal"):
    modal_contrato(st.session_state["contrato_row"])
    st.session_state["abrir_modal"] = False




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

