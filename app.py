# -*- coding: utf-8 -*-
"""
Dashboard LEM — Fundação Pão dos Pobres
Visualização de Dados — Projeto Final, Parte II · Streamlit + Plotly

Uma aba por Pergunta de Negócio (slide 5 do pitch):
  ① Quais áreas concentram maior volume de atendimentos ao longo do tempo?
  ② Existe relação entre atendimentos realizados e demandas de saúde mental?
  ③ Os encaminhamentos para cursos e mercado resultam em inserção efetiva?
  ④ Onde estão os principais gargalos entre atendimento e resultados finais?
  ⑤ Como a variação mensal impacta o planejamento da instituição?

Rodar:
    pip install -r requirements.txt
    streamlit run app.py
"""

import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import plotly.io as pio

from pipeline import (
    carregar_dados, serie_temporal, MESES, FILE_MAP, ESTOQUES,
)

# ─── renderização com fundo/fonte fixos ──────────────────────────────
# Todo gráfico tem fundo branco. Sem isso, num Streamlit em tema escuro:
#  - o fundo da figura ficaria transparente (aparece o escuro do app) e
#  - o texto (legenda, eixos) herdaria cor clara/escura errada, sumindo.
# Em vez de depender de template, forçamos fundo branco + fonte escura
# EXPLICITAMENTE em cada figura e passamos theme=None para o Streamlit
# não sobrescrever. Assim funciona igual em tema claro ou escuro.
pio.templates.default = "plotly_white"


def _show(fig, **kwargs):
    fig.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(color="#222222", family="Segoe UI, Arial, sans-serif"),
        legend=dict(font_color="#222222", title_font_color="#222222"),
    )
    fig.update_xaxes(title_font_color="#222222", tickfont_color="#222222",
                     linecolor="#cccccc", gridcolor="#ebebeb")
    fig.update_yaxes(title_font_color="#222222", tickfont_color="#222222",
                     linecolor="#cccccc", gridcolor="#ebebeb")
    st.plotly_chart(fig, use_container_width=True, theme=None, **kwargs)

# ─── resolução robusta da pasta de dados ─────────────────────────────
# Procura os XLSX em `data/` e, como fallback, na própria pasta do app.
# (checa isdir ANTES de listdir para não quebrar quando `data/` não existe)
HERE = os.path.dirname(os.path.abspath(__file__))


def _find_data_dir():
    for p in (os.path.join(HERE, "data"), HERE):
        if os.path.isdir(p) and any(f in os.listdir(p) for f in FILE_MAP):
            return p
    return os.path.join(HERE, "data")


DATA_DIR = _find_data_dir()

st.set_page_config(page_title="LEM — Fundação Pão dos Pobres", page_icon="🏠",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    h1 { color: #1f4e79; }
    h2 { color: #2e75b6; }
    .metric-card {
        background: white; border-radius: 10px; padding: 14px 18px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); border-left: 5px solid #2e75b6;
    }
    .metric-card h3 { margin: 0; font-size: 0.82rem; color: #666; font-weight: 400; }
    .metric-card p  { margin: 4px 0 0 0; font-size: 1.7rem; font-weight: 700; color: #1f4e79; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

CORES = px.colors.qualitative.Set2


@st.cache_data(show_spinner="Carregando e consolidando planilhas LEM...")
def carregar():
    return carregar_dados(DATA_DIR)


# ─────────────────────────────────────────────  SIDEBAR
with st.sidebar:
    st.markdown("## 🏠 LEM — Pão dos Pobres")
    st.caption("Levantamento Estatístico Mensal · 2021–2025")
    st.divider()

    up = st.file_uploader(
        "Adicionar/atualizar um período (.xlsx no padrão LEM)",
        type=["xlsx"],
        help="Mesmo layout das planilhas LEM_<ano>.xlsx (coluna 0 = indicador, "
             "colunas JAN..DEZ). O arquivo é salvo na pasta de dados e integrado.",
    )
    if up is not None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, up.name), "wb") as f:
            f.write(up.getbuffer())
        novo_ano = st.number_input("Ano deste arquivo:", 2020, 2035, 2026)
        if st.button("Integrar ao dashboard"):
            FILE_MAP[up.name] = int(novo_ano)
            st.cache_data.clear()
            st.success(f"{up.name} integrado como {novo_ano}. Recarregando...")
            st.rerun()
    st.divider()

df_full, erros = carregar()
if df_full is None:
    st.error(f"Nenhum arquivo de dados encontrado em `{DATA_DIR}`. "
             "Confira se as planilhas LEM_<ano>.xlsx estão na pasta `data/`.")
    st.stop()
if erros:
    st.sidebar.warning("Arquivos configurados mas não encontrados:\n" + "\n".join(erros))

with st.sidebar:
    st.markdown("### 🔎 Filtros")
    anos_disp = sorted(df_full["ano"].unique())
    anos_sel = st.multiselect("Anos:", options=anos_disp, default=anos_disp)
    st.divider()
    st.caption("Fundação Pão dos Pobres · Visualização de Dados · 2026")

df = df_full[df_full["ano"].isin(anos_sel)].copy() if anos_sel else df_full.copy()
if df.empty:
    st.error("Nenhum dado para os anos selecionados.")
    st.stop()


# ─────────────────────────────────────────────  HELPERS
def soma(indicador, base=None):
    base = df if base is None else base
    return base.loc[base["indicador"] == indicador, "valor"].sum(min_count=1)


def media(indicador, base=None):
    base = df if base is None else base
    return base.loc[base["indicador"] == indicador, "valor"].mean()


def pivot_mes_ano(indicador, base=None):
    base = df if base is None else base
    p = base[base["indicador"] == indicador].pivot_table(
        index="mes", columns="ano", values="valor")
    return p.reindex(range(1, 13))


def trendline_xy(x, y):
    """Reta de tendência via numpy (dispensa statsmodels)."""
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 2:
        return None, None, np.nan
    a, b = np.polyfit(x[m], y[m], 1)
    xs = np.array([x[m].min(), x[m].max()])
    r = np.corrcoef(x[m], y[m])[0, 1]
    return xs, a * xs + b, r


# ─────────────────────────────────────────────  HEADER + KPIs
st.markdown("# 🏠 Dashboard LEM — Fundação Pão dos Pobres")
st.markdown("Acolhimento institucional · Aprendizagem profissional · Serviço de convivência — dados 2021–2025")

c1, c2, c3, c4 = st.columns(4)


def kpi(col, titulo, valor):
    col.markdown(f'<div class="metric-card"><h3>{titulo}</h3><p>{valor}</p></div>',
                 unsafe_allow_html=True)


def br(n):
    return f"{int(n):,}".replace(",", ".") if pd.notna(n) else "—"


kpi(c1, "Atendimentos Individuais (total)", br(soma("atend_individual")))
kpi(c2, "Atendimentos Familiares (total)", br(soma("atend_familiar")))
kpi(c3, "Inseridos no Mercado (total)", br(soma("prof_inseridos_mercado")))
_me = media("efetivos_casa")
kpi(c4, "Média de Residentes/Mês", f"{_me:.1f}" if pd.notna(_me) else "—")

st.divider()

tabs = st.tabs([
    "① Volume por Área",
    "② Atendimento × Saúde Mental",
    "③ Funil de Profissionalização",
    "④ Gargalos",
    "⑤ Sazonalidade & Planejamento",
])

# ══════════════════════════════════════════════════════════════════
# ① Quais áreas concentram maior volume de atendimentos ao longo do tempo?
# ══════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown("## ① Quais áreas concentram maior volume de atendimentos ao longo do tempo?")
    st.caption("Somamos apenas indicadores de **fluxo** (eventos contáveis no mês). "
               "Estoques como nº de residentes e matrículas ficam fora — somá-los ao "
               "longo de 60 meses não representaria volume de atividade.")

    base_fluxo = df[df["tipo"] == "fluxo"]
    vol_area = base_fluxo.groupby(["area", "ano"])["valor"].sum(min_count=1).reset_index()
    fig = px.bar(vol_area, x="ano", y="valor", color="area", barmode="group",
                 labels={"valor": "Volume total (eventos)", "ano": "Ano", "area": "Área"},
                 color_discrete_sequence=CORES, text_auto=True)
    fig.update_traces(textposition="outside", textfont_size=9)
    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", height=440,
                      xaxis=dict(tickmode="linear", dtick=1), legend_title_text="")
    _show(fig)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Participação de cada área (todo o período)")
        vol_total = (base_fluxo.groupby("area")["valor"].sum(min_count=1)
                     .sort_values(ascending=False).reset_index())
        fig_pie = px.pie(vol_total, names="area", values="valor", hole=0.45,
                         color_discrete_sequence=CORES)
        fig_pie.update_layout(height=380)
        _show(fig_pie)
    with col_b:
        st.markdown("#### Top 10 indicadores individuais (total 2021–2025)")
        rank = (base_fluxo.groupby(["indicador", "nome"])["valor"].sum(min_count=1)
                .reset_index().sort_values("valor", ascending=False).head(10))
        fig_rank = px.bar(rank, x="valor", y="nome", orientation="h",
                          color_discrete_sequence=["#2E75B6"], text_auto=True)
        fig_rank.update_layout(plot_bgcolor="white", paper_bgcolor="white", height=380,
                               yaxis=dict(autorange="reversed"), xaxis_title="Total", yaxis_title="")
        _show(fig_rank)

# ══════════════════════════════════════════════════════════════════
# ② Relação entre atendimentos e demandas de saúde mental
# ══════════════════════════════════════════════════════════════════
with tabs[1]:
    st.markdown("## ② Existe relação entre atendimentos realizados e demandas de saúde mental?")

    inds_corr = ["atend_individual", "atend_familiar", "saude_mental", "saude_clinica",
                 "novos_ingressos", "evasao", "desligamentos"]
    piv = df[df["indicador"].isin(inds_corr)].pivot_table(
        index=["ano", "mes"], columns="indicador", values="valor").sort_index()
    corr = piv.corr()

    col_a, col_b = st.columns([1.1, 1])
    with col_a:
        st.markdown("#### Correlação entre indicadores (nível mês)")
        fig_h = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                          zmin=-1, zmax=1, labels=dict(color="r"))
        fig_h.update_layout(height=430)
        _show(fig_h)
    with col_b:
        st.markdown("#### Atend. individuais × Saúde mental (mês a mês)")
        merge = piv.reset_index()
        fig_sc = go.Figure()
        fig_sc.add_trace(go.Scatter(
            x=merge["atend_individual"], y=merge["saude_mental"], mode="markers",
            marker=dict(size=8, color=merge["ano"], colorscale="Blues",
                        showscale=True, colorbar=dict(title="ano")),
            name="mês"))
        xs, ys, r_sc = trendline_xy(merge["atend_individual"].values, merge["saude_mental"].values)
        if xs is not None:
            fig_sc.add_trace(go.Scatter(x=xs, y=ys, mode="lines",
                                        line=dict(color="#ED7D31", dash="dash"),
                                        name=f"tendência (r={r_sc:.2f})"))
        fig_sc.update_layout(height=430, xaxis_title="Atendimentos individuais/mês",
                             yaxis_title="Saúde mental/mês", plot_bgcolor="white",
                             legend=dict(orientation="h", y=1.1))
        _show(fig_sc)

    # ── Hipótese das datas comemorativas (insight qualitativo do grupo) ──
    st.markdown("### 🎄 Hipótese do grupo: datas comemorativas de família e saúde mental")
    st.caption("Insight da equipe, a partir da vivência do acolhimento: em datas voltadas à família "
               "(Dia das Mães, Dia dos Pais, Dia das Crianças, Natal), crianças e adolescentes acolhidos "
               "sentem mais a ausência de um vínculo familiar — ao contrário da imagem de “época feliz”. "
               "Abaixo testamos se isso aparece na sazonalidade dos dados existentes.")

    MESES_FAMILIA = {5: "Dia das Mães", 8: "Dia dos Pais", 10: "Dia das Crianças", 12: "Natal"}
    sm_mes = df[df["indicador"] == "saude_mental"].groupby("mes")["valor"].mean().reindex(range(1, 13))
    media_geral = sm_mes.mean()
    cores_barras = ["#C0392B" if m in MESES_FAMILIA else "#2E75B6" for m in range(1, 13)]
    rotulos = [f"{MESES[m-1]}<br>{MESES_FAMILIA[m]}" if m in MESES_FAMILIA else MESES[m-1]
               for m in range(1, 13)]
    fig_saz = go.Figure()
    fig_saz.add_trace(go.Bar(x=rotulos, y=sm_mes.values, marker_color=cores_barras,
                             text=[f"{v:.0f}" for v in sm_mes.values], textposition="outside"))
    fig_saz.add_hline(y=media_geral, line_dash="dot", line_color="#555",
                      annotation_text=f"média geral ({media_geral:.0f})", annotation_position="top left")
    fig_saz.update_layout(height=380, yaxis_title="Saúde mental — média mensal (2021–2025)",
                          plot_bgcolor="white", paper_bgcolor="white",
                          title="Barras vermelhas = meses de datas familiares")
    _show(fig_saz)

# ══════════════════════════════════════════════════════════════════
# ③ Encaminhamentos resultam em inserção efetiva?
# ══════════════════════════════════════════════════════════════════
with tabs[2]:
    st.markdown("## ③ Os encaminhamentos para cursos e mercado resultam em inserção efetiva?")

    enc_curso, ins_curso = soma("prof_encaminhados_curso"), soma("prof_inseridos_curso")
    enc_merc, ins_merc = soma("prof_encaminhados_mercado"), soma("prof_inseridos_mercado")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Funil — Mercado de trabalho")
        fig_f1 = go.Figure(go.Funnel(
            y=["Encaminhados p/ mercado", "Inseridos no mercado"],
            x=[enc_merc, ins_merc], textinfo="value+percent initial",
            marker=dict(color=["#2E75B6", "#70AD47"])))
        fig_f1.update_layout(height=300)
        _show(fig_f1)
    with col_b:
        st.markdown("#### Funil — Cursos profissionalizantes")
        fig_f2 = go.Figure(go.Funnel(
            y=["Encaminhados p/ curso", "Inseridos em curso"],
            x=[enc_curso, ins_curso], textinfo="value+percent initial",
            marker=dict(color=["#ED7D31", "#FFC000"])))
        fig_f2.update_layout(height=300)
        _show(fig_f2)

    st.markdown("#### Evolução anual — encaminhamento vs. inserção")
    inds_prof = ["prof_encaminhados_mercado", "prof_inseridos_mercado",
                 "prof_encaminhados_curso", "prof_inseridos_curso"]
    anual = (df[df["indicador"].isin(inds_prof)]
             .groupby(["ano", "nome"])["valor"].sum(min_count=1).reset_index())
    fig_line = px.line(anual, x="ano", y="valor", color="nome", markers=True,
                       color_discrete_sequence=CORES,
                       labels={"valor": "Total anual", "ano": "Ano", "nome": ""})
    fig_line.update_layout(height=380, xaxis=dict(tickmode="linear", dtick=1))
    _show(fig_line)

# ══════════════════════════════════════════════════════════════════
# ④ Principais gargalos entre atendimento e resultados finais
# ══════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown("## ④ Onde estão os principais gargalos entre atendimento e resultados finais?")

    st.markdown("#### Funil geral — do atendimento à inserção no mercado")
    st.caption("Reproduz o funil do pitch: o topo (atendimentos totais = individuais + familiares + "
               "saúde mental) e a base (inseridos no mercado) são calculados ao vivo das planilhas.")
    total_atend = soma("atend_individual") + soma("atend_familiar") + soma("saude_mental")
    encaminhados = soma("prof_encaminhados_curso") + soma("prof_encaminhados_mercado")
    iniciaram = soma("prof_inseridos_curso")
    inseridos = soma("prof_inseridos_mercado")
    etapas = pd.DataFrame({
        "etapa": ["Atendimentos totais", "Encaminhados (curso/mercado)",
                  "Inseridos em curso", "Inseridos no mercado"],
        "valor": [total_atend, encaminhados, iniciaram, inseridos],
    })
    fig_funil = go.Figure(go.Funnel(
        y=etapas["etapa"], x=etapas["valor"], textinfo="value+percent initial",
        marker=dict(color=["#1F4E79", "#2E75B6", "#ED7D31", "#70AD47"])))
    fig_funil.update_layout(height=400)
    _show(fig_funil)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Educação — matriculados vs. aguardando vaga (média mensal)")
        st.caption("Matrícula é **estoque**: usamos a média mensal de vagas, não a soma dos 60 meses.")
        pares = [("educ_infantil_matriculados", "educ_infantil_aguardando", "Infantil"),
                 ("educ_regular_matriculados", "educ_regular_aguardando", "Regular"),
                 ("educ_eja_matriculados", "educ_eja_aguardando", "EJA"),
                 ("educ_scfv_matriculados", "educ_scfv_aguardando", "SCFV")]
        rows = []
        for mat, agu, label in pares:
            rows.append({"nível": label, "situação": "Matriculados", "valor": media(mat)})
            rows.append({"nível": label, "situação": "Aguardando vaga", "valor": media(agu)})
        educ_df = pd.DataFrame(rows)
        fig_educ = px.bar(educ_df, x="nível", y="valor", color="situação", barmode="group",
                          color_discrete_sequence=["#2E75B6", "#ED7D31"], text_auto=".1f")
        fig_educ.update_layout(height=380, yaxis_title="Média mensal", legend_title_text="")
        _show(fig_educ)
    with col_b:
        st.markdown("#### Fluxo da casa — ingressos vs. saídas (por ano)")
        inds_fluxo = ["novos_ingressos", "evasao", "desligamentos"]
        anual_fluxo = (df[df["indicador"].isin(inds_fluxo)]
                       .groupby(["ano", "nome"])["valor"].sum(min_count=1).reset_index())
        fig_fluxo = px.bar(anual_fluxo, x="ano", y="valor", color="nome", barmode="group",
                           color_discrete_sequence=["#70AD47", "#C0392B", "#7030A0"], text_auto=True)
        fig_fluxo.update_layout(height=380, xaxis=dict(tickmode="linear", dtick=1),
                                legend_title_text="")
        _show(fig_fluxo)

# ══════════════════════════════════════════════════════════════════
# ⑤ Variação mensal e planejamento
# ══════════════════════════════════════════════════════════════════
with tabs[4]:
    st.markdown("## ⑤ Como a variação mensal impacta o planejamento da instituição?")

    st.markdown("#### Heatmap mensal — Atendimentos Individuais")
    piv_h = pivot_mes_ano("atend_individual")
    piv_h.index = MESES
    fig_heat = px.imshow(piv_h, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                         labels=dict(x="Ano", y="Mês", color="Atendimentos"))
    fig_heat.update_layout(height=420)
    _show(fig_heat)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Sazonalidade média por mês")
        opcoes = ["atend_individual", "atend_familiar", "saude_mental", "evasao", "novos_ingressos"]
        indicador_sel = st.selectbox(
            "Indicador:", options=opcoes,
            format_func=lambda x: df.loc[df["indicador"] == x, "nome"].iloc[0]
            if (df["indicador"] == x).any() else x)
        media_mes = df[df["indicador"] == indicador_sel].groupby("mes")["valor"].mean().reindex(range(1, 13))
        fig_saz = go.Figure(go.Bar(x=MESES, y=media_mes.values, marker_color="#2E75B6",
                                   text=[f"{v:.0f}" for v in media_mes.values], textposition="outside"))
        fig_saz.update_layout(height=380, yaxis_title="Média mensal", plot_bgcolor="white")
        _show(fig_saz)
    with col_b:
        st.markdown("#### Volatilidade — coef. de variação por indicador")
        st.caption("CV = desvio-padrão / média. Quanto maior, mais o indicador oscila mês a mês.")
        cv = (df[df["tipo"] == "fluxo"].groupby("nome")["valor"].agg(["mean", "std"])
              .assign(cv=lambda d: 100 * d["std"] / d["mean"].replace(0, np.nan))
              .dropna().sort_values("cv", ascending=False).head(12).reset_index())
        fig_cv = px.bar(cv, x="cv", y="nome", orientation="h",
                        color_discrete_sequence=["#ED7D31"], text_auto=".0f")
        fig_cv.update_layout(height=380, yaxis=dict(autorange="reversed"),
                             xaxis_title="Coef. de variação (%)", yaxis_title="")
        _show(fig_cv)


# ─────────────────────────────────────────────  DOWNLOAD
st.divider()
st.markdown("### 💾 Dados consolidados")
csv = df[["ano", "mes", "mes_nome", "data", "area", "tipo", "indicador", "nome", "valor"]].to_csv(
    index=False).encode("utf-8-sig")
st.download_button("⬇️ Baixar CSV consolidado", data=csv,
                   file_name="lem_consolidado.csv", mime="text/csv")
st.caption("Fontes: LEM_2021, LEM_2022_1, LEM_2023, LEM_2024_1, LEM_2025_3 (versão mais completa de cada "
           "ano). Projeto de Visualização de Dados — PUCRS, 2026.")
