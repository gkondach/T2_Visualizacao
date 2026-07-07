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
    .insight-box {
        background: #e8f4fd; border-left: 4px solid #2e75b6; border-radius: 6px;
        padding: 10px 14px; margin: 10px 0; font-size: 0.92rem; color: #1f4e79;
    }
    .warn-box {
        background: #fff4e5; border-left: 4px solid #e6a23c; border-radius: 6px;
        padding: 10px 14px; margin: 10px 0; font-size: 0.92rem; color: #7a4a00;
    }
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

    area_top = vol_total.iloc[0]["area"]
    pct_top = 100 * vol_total.iloc[0]["valor"] / vol_total["valor"].sum()
    st.markdown(
        f'<div class="insight-box">💡 <b>Resposta:</b> a área de <b>{area_top}</b> concentra a maior '
        f'fatia do volume de atividades ({pct_top:.0f}% do total de eventos), puxada pelos atendimentos '
        f'individuais e familiares — coerente com o fato de o atendimento ser a porta de entrada de '
        f'praticamente todos os demais serviços (saúde, profissionalização, educação e interfaces).</div>',
        unsafe_allow_html=True)

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

    r_as = corr.loc["atend_individual", "saude_mental"]
    r_is = corr.loc["novos_ingressos", "saude_mental"]

    # ── Defasagem (lag) com série contínua ──
    st.markdown("#### Novos ingressos × Saúde mental — com defasagem (lag)")
    st.caption("Testa se um aumento de ingressos antecede um aumento de demandas de "
               "saúde mental nos meses seguintes (série contínua 2021–2025).")
    s_ing = serie_temporal(df, "novos_ingressos")
    s_sm = serie_temporal(df, "saude_mental")
    base_lag = pd.concat([s_ing.rename("ing"), s_sm.rename("sm")], axis=1).sort_index()
    lags = list(range(0, 4))
    lag_corrs = [base_lag["ing"].shift(l).corr(base_lag["sm"]) for l in lags]
    fig_lag = go.Figure(go.Bar(
        x=[f"+{l} mês(es)" for l in lags], y=lag_corrs, marker_color="#2E75B6",
        text=[f"{v:.2f}" if pd.notna(v) else "—" for v in lag_corrs], textposition="outside"))
    fig_lag.update_layout(height=300, yaxis_title="correlação", plot_bgcolor="white",
                          xaxis_title="defasagem aplicada aos ingressos")
    _show(fig_lag)

    st.markdown(
        f'<div class="insight-box">💡 <b>Resposta (dados disponíveis):</b> a correlação mensal entre '
        f'atendimentos individuais e saúde mental é <b>{r_as:.2f}</b> e entre novos ingressos e saúde '
        f'mental é <b>{r_is:.2f}</b> — ambas próximas de zero. E isso já é uma resposta: a demanda de saúde '
        f'mental <b>não</b> acompanha simplesmente o volume geral de atendimento nem o fluxo de novos '
        f'acolhimentos. Ela parece ter dinâmica própria, puxada mais por fatores sazonais/emocionais do que '
        f'por volume — o que motiva a análise das datas comemorativas abaixo.</div>', unsafe_allow_html=True)

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

    fam = list(MESES_FAMILIA)
    m_fam = sm_mes[sm_mes.index.isin(fam)].mean()
    m_resto = sm_mes[~sm_mes.index.isin(fam)].mean()
    acima = [MESES[m-1] for m in fam if sm_mes[m] > media_geral]
    abaixo = [MESES[m-1] for m in fam if sm_mes[m] <= media_geral]
    st.markdown(
        f'<div class="warn-box">🔎 <b>O que os dados mostram:</b> nos meses de datas familiares a média de '
        f'saúde mental é <b>{m_fam:.1f}</b>, contra <b>{m_resto:.1f}</b> nos demais meses. A hipótese tem '
        f'<b>suporte parcial</b>: {", ".join(acima) if acima else "nenhum mês"} ficam acima da média geral '
        f'(destaque para <b>Natal</b> e <b>Dia dos Pais</b>), enquanto {", ".join(abaixo) if abaixo else "—"} '
        f'não seguem o padrão. <br><br><b>Limitação:</b> a planilha LEM só registra o total mensal, sem a '
        f'data (dia) do atendimento nem o motivo — então não é possível <i>provar</i> estatisticamente a '
        f'ligação com uma data específica. <b>Recomendação (trabalho futuro):</b> passar a registrar a data '
        f'de cada atendimento de saúde mental para cruzar picos com datas comemorativas.</div>',
        unsafe_allow_html=True)

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

    conv_m = 100 * ins_merc / enc_merc if enc_merc else np.nan
    conv_c = 100 * ins_curso / enc_curso if enc_curso else np.nan
    st.markdown(
        f'<div class="insight-box">💡 <b>Resposta:</b> a conversão encaminhamento → inserção é de '
        f'<b>{conv_m:.0f}%</b> para o mercado de trabalho e <b>{conv_c:.0f}%</b> para cursos '
        f'profissionalizantes (2021–2025). Isso confirma o gargalo do pitch: boa parte dos encaminhados '
        f'não chega a se inserir de fato — por evasão, falta de vagas ou descontinuidade no acompanhamento. '
        f'A conversão para cursos, acima de 100% em alguns períodos, indica ainda inconsistência de registro '
        f'(inserções sem o encaminhamento correspondente lançado no mês).</div>', unsafe_allow_html=True)

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
    conv_final = 100 * inseridos / total_atend if total_atend else np.nan
    st.markdown(
        f'<div class="warn-box">⚠ <b>Gargalo central:</b> de <b>{br(total_atend)}</b> atendimentos '
        f'realizados no período, apenas <b>{br(inseridos)}</b> resultaram em inserção no mercado de '
        f'trabalho — conversão de <b>~{conv_final:.1f}%</b>. É o mesmo gargalo destacado no pitch, agora '
        f'reproduzido diretamente dos dados.</div>', unsafe_allow_html=True)

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

    st.markdown(
        '<div class="insight-box">💡 <b>Resposta:</b> o maior gargalo está na '
        '<b>profissionalização</b> (poucos encaminhados chegam à inserção). Um segundo gargalo aparece na '
        '<b>educação</b>, onde há vagas aguardando em vários níveis — sinal de limitação de vagas na rede '
        'pública, não de falha da Fundação. Vale ainda investigar, com a equipe técnica, os anos com picos '
        'de evasão/desligamento acima dos novos ingressos.</div>', unsafe_allow_html=True)

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

    mes_pico = MESES[int(media_mes.idxmax()) - 1] if media_mes.notna().any() else "—"
    mes_baixa = MESES[int(media_mes.idxmin()) - 1] if media_mes.notna().any() else "—"
    st.markdown(
        f'<div class="insight-box">💡 <b>Resposta:</b> o indicador selecionado tem pico médio em '
        f'<b>{mes_pico}</b> e vale em <b>{mes_baixa}</b>. Indicadores com alto coeficiente de variação '
        f'(painel à direita) exigem atenção redobrada no planejamento de equipe e recursos — seu volume '
        f'oscila muito de mês a mês, o que reforça a necessidade de um dashboard que monitore a série '
        f'continuamente, em vez de um planejamento baseado só em médias anuais.</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────  DOWNLOAD
st.divider()
st.markdown("### 💾 Dados consolidados")
csv = df[["ano", "mes", "mes_nome", "data", "area", "tipo", "indicador", "nome", "valor"]].to_csv(
    index=False).encode("utf-8-sig")
st.download_button("⬇️ Baixar CSV consolidado", data=csv,
                   file_name="lem_consolidado.csv", mime="text/csv")
st.caption("Fontes: LEM_2021, LEM_2022_1, LEM_2023, LEM_2024_1, LEM_2025_3 (versão mais completa de cada "
           "ano). Projeto de Visualização de Dados — PUCRS, 2026.")
