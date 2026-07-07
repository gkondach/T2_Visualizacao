# -*- coding: utf-8 -*-
"""
pipeline.py — Consolidação dos dados LEM (Fundação Pão dos Pobres)

Lê os arquivos anuais "LEM_<ano>.xlsx" (planilha padrão da instituição),
extrai os indicadores mês a mês e devolve um único dataframe no formato
"long" (uma linha por ano/mês/indicador), pronto para análise/visualização.

Decisões de projeto documentadas aqui (para defesa do trabalho):

  * Quando havia mais de uma versão do mesmo ano, escolhemos a versão com
    mais meses preenchidos como fonte oficial (ver FILE_MAP). A checagem de
    completude que embasou essa escolha está em `diagnostico_arquivos()`.

  * Marcamos cada indicador como FLUXO (evento contável no mês, ex.:
    atendimentos, encaminhamentos) ou ESTOQUE (contagem de um estado no mês,
    ex.: nº de residentes na casa, nº de matriculados). Somar um estoque ao
    longo de 60 meses NÃO representa "volume de atividade" — por isso o
    dashboard soma apenas fluxos nas perguntas de volume, e usa média/último
    valor para estoques.

Como adicionar um novo ano/período:
  1. Salve o arquivo em `data/` seguindo o padrão LEM_<ano>.xlsx.
  2. Inclua a entrada correspondente em FILE_MAP (arquivo -> ano) OU use o
     campo de upload na barra lateral do dashboard.
  3. Rode novamente — nada mais precisa ser alterado.
"""

import os
import glob
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────
# Arquivo -> ano. Fonte oficial de cada ano = versão mais completa.
# (2024 e 2025 tinham várias versões; escolhemos a de 12 meses preenchidos.)
# ─────────────────────────────────────────────────────────
FILE_MAP = {
    "LEM_2021.xlsx":   2021,
    "LEM_2022_1.xlsx": 2022,
    "LEM_2023.xlsx":   2023,
    "LEM_2024_1.xlsx": 2024,
    "LEM_2025_3.xlsx": 2025,
}

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
         "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]

# Cabeçalhos de seção da planilha — devem ser ignorados como indicadores.
SECOES_HEADER = {
    "DESDOBRAMENTOS TÉCNICOS", "PROFISSIONALIZAÇÃO", "SAÚDE", "EDUCAÇÃO",
    "dados gerencias de efetividade", "OBS.",
}
# Linhas "pai" da seção educação (a linha seguinte é 'matriculados'/'aguardando vaga').
PAIS_EDUC = {"Ensino infantil", "Ensino regular", "Ensino EJA", "SCFV"}

# Mapa de rótulo bruto (com os erros de digitação da planilha) -> nome técnico.
MAPA_INDICADOR = {
    "Atendimentos indvidual": "atend_individual",
    "Atendimento individual": "atend_individual",
    "Atedimento familiar": "atend_familiar",
    "Atendimento familiar": "atend_familiar",
    "Interface com rede socioassistencial": "interface_rede",
    "Interface com judiciário": "interface_judiciario",
    "Interface com saúde": "interface_saude",
    "Interface com educação": "interface_educacao",
    "PIAS / Relatórios": "pias_relatorios",
    "Visitas Domiciliares": "visitas_domiciliares",
    "Apadrinhamento afetivo": "apadrinhamento_afetivo",
    "Colocação em família substituta": "colocacao_familia_substituta",
    "Reunião de equipe (técnica, casa, coordenação, gerente)": "reuniao_equipe",
    "Desligamentos": "desligamentos",
    "Evasão": "evasao",
    "Novos ingressos": "novos_ingressos",
    "Transferências": "transferencias",
    "Efetivos na casa": "efetivos_casa",
    "Documentação civil (RG / CPF/ CTPS / Certidão de nascimento)": "documentacao_civil",
    "INSERIDOS em curso profissionalizante": "prof_inseridos_curso",
    "ENCAMINHADOS para curso profissionalizante": "prof_encaminhados_curso",
    "INSERIDO no mercado de trabalho": "prof_inseridos_mercado",
    "ENCAMINHADO para mercado de trabalho": "prof_encaminhados_mercado",
    "Saude mental": "saude_mental",
    "Saúde mental": "saude_mental",
    "Saúde Clínica": "saude_clinica",
    "Saude Clínica": "saude_clinica",
    "Internações": "saude_internacoes",
    "Ensino infantil_matriculados": "educ_infantil_matriculados",
    "Ensino infantil_aguardando": "educ_infantil_aguardando",
    "Ensino regular_matriculados": "educ_regular_matriculados",
    "Ensino regular_aguardando": "educ_regular_aguardando",
    "Ensino EJA_matriculados": "educ_eja_matriculados",
    "Ensino EJA_aguardando": "educ_eja_aguardando",
    "SCFV_matriculados": "educ_scfv_matriculados",
    "SCFV_aguardando": "educ_scfv_aguardando",
    "Outros: Reforço escolar, psicopedagoga, trabalho educativo": "educ_outros",
}

NOMES_BONITOS = {
    "atend_individual": "Atendimentos Individuais",
    "atend_familiar": "Atendimentos Familiares",
    "interface_rede": "Interface — Rede Socioassistencial",
    "interface_judiciario": "Interface — Judiciário",
    "interface_saude": "Interface — Saúde",
    "interface_educacao": "Interface — Educação",
    "pias_relatorios": "PIAS / Relatórios",
    "visitas_domiciliares": "Visitas Domiciliares",
    "apadrinhamento_afetivo": "Apadrinhamento Afetivo",
    "colocacao_familia_substituta": "Colocação em Família Substituta",
    "reuniao_equipe": "Reunião de Equipe",
    "desligamentos": "Desligamentos",
    "evasao": "Evasões",
    "novos_ingressos": "Novos Ingressos",
    "transferencias": "Transferências",
    "efetivos_casa": "Efetivos na Casa (residentes)",
    "documentacao_civil": "Documentação Civil",
    "prof_inseridos_curso": "Inseridos em Curso Profissionalizante",
    "prof_encaminhados_curso": "Encaminhados para Curso",
    "prof_inseridos_mercado": "Inseridos no Mercado de Trabalho",
    "prof_encaminhados_mercado": "Encaminhados para o Mercado",
    "saude_mental": "Atendimentos de Saúde Mental",
    "saude_clinica": "Atendimentos de Saúde Clínica",
    "saude_internacoes": "Internações",
    "educ_infantil_matriculados": "Ens. Infantil — Matriculados",
    "educ_infantil_aguardando": "Ens. Infantil — Aguardando Vaga",
    "educ_regular_matriculados": "Ens. Regular — Matriculados",
    "educ_regular_aguardando": "Ens. Regular — Aguardando Vaga",
    "educ_eja_matriculados": "EJA — Matriculados",
    "educ_eja_aguardando": "EJA — Aguardando Vaga",
    "educ_scfv_matriculados": "SCFV — Matriculados",
    "educ_scfv_aguardando": "SCFV — Aguardando Vaga",
    "educ_outros": "Outros (reforço escolar, psicopedagoga)",
}

# ─────────────────────────────────────────────────────────
# FLUXO vs ESTOQUE.
# ESTOQUE = contagem de um estado no mês (não deve ser somado no tempo).
# Tudo que não está aqui é tratado como FLUXO (evento contável no mês).
# ─────────────────────────────────────────────────────────
ESTOQUES = {
    "efetivos_casa",
    "educ_infantil_matriculados", "educ_infantil_aguardando",
    "educ_regular_matriculados", "educ_regular_aguardando",
    "educ_eja_matriculados", "educ_eja_aguardando",
    "educ_scfv_matriculados", "educ_scfv_aguardando",
}

# ─────────────────────────────────────────────────────────
# Áreas de atuação (usadas na Pergunta 1 — volume de atendimentos).
# Contém APENAS indicadores de FLUXO. Estoques ficam de fora do volume
# e são tratados separadamente (educação na P4, residentes na P5).
# ─────────────────────────────────────────────────────────
AREAS = {
    "Atendimento":         ["atend_individual", "atend_familiar"],
    "Saúde":               ["saude_mental", "saude_clinica", "saude_internacoes"],
    "Interfaces externas": ["interface_educacao", "interface_saude",
                            "interface_rede", "interface_judiciario"],
    "Profissionalização":  ["prof_encaminhados_curso", "prof_inseridos_curso",
                            "prof_encaminhados_mercado", "prof_inseridos_mercado"],
    "Gestão da casa":      ["novos_ingressos", "desligamentos", "evasao",
                            "transferencias", "colocacao_familia_substituta"],
    "Doc. & Apoio":        ["documentacao_civil", "pias_relatorios",
                            "visitas_domiciliares", "apadrinhamento_afetivo",
                            "reuniao_equipe"],
}
INDICADOR_AREA = {ind: area for area, inds in AREAS.items() for ind in inds}


def _parse_valor(v):
    if pd.isna(v) or str(v).strip() in ("", "nan"):
        return np.nan
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def _extrair_arquivo(path, ano):
    """Lê um LEM_<ano>.xlsx (primeira planilha) e devolve linhas
    (ano, mes, indicador, valor)."""
    df_raw = pd.read_excel(path, header=None, engine="openpyxl", sheet_name=0)
    rows, secao_pai = [], None
    for _, row in df_raw.iterrows():
        label = str(row[0]).strip() if not pd.isna(row[0]) else ""
        if not label or label == "nan":
            continue
        if label.startswith("LEM -") or label.startswith("LEM–") or label.startswith("LEM "):
            continue
        if label in SECOES_HEADER or label.lstrip() in SECOES_HEADER:
            continue

        label_r = label.rstrip()
        if label_r in PAIS_EDUC:
            secao_pai = label_r
            continue

        if label.lstrip() == "matriculados" and secao_pai:
            label = f"{secao_pai}_matriculados"
        elif label.lstrip() == "aguardando vaga" and secao_pai:
            label = f"{secao_pai}_aguardando"
        else:
            secao_pai = None

        indicador = MAPA_INDICADOR.get(label, None)
        if indicador is None:
            continue  # linha não reconhecida (obs., cabeçalhos residuais) — ignora

        for m in range(12):
            val = row[m + 1] if (m + 1) < len(row) else np.nan
            rows.append({
                "ano": ano,
                "mes": m + 1,
                "mes_nome": MESES[m],
                "data": pd.Timestamp(year=ano, month=m + 1, day=1),
                "indicador": indicador,
                "valor": _parse_valor(val),
            })
    return pd.DataFrame(rows)


def carregar_dados(data_dir, file_map=None):
    """Varre `data_dir` usando `file_map` (padrão FILE_MAP) e devolve
    (df, erros), com df no formato long e colunas auxiliares:
        nome (rótulo amigável), area, tipo (fluxo/estoque)."""
    file_map = file_map or FILE_MAP
    dfs, erros = [], []
    for fname, ano in file_map.items():
        path = os.path.join(data_dir, fname)
        if not os.path.exists(path):
            erros.append(fname)
            continue
        try:
            dfs.append(_extrair_arquivo(path, ano))
        except Exception as e:  # noqa: BLE001
            erros.append(f"{fname}: {e}")

    if not dfs:
        return None, erros

    df = pd.concat(dfs, ignore_index=True)
    df["nome"] = df["indicador"].map(NOMES_BONITOS).fillna(df["indicador"])
    df["area"] = df["indicador"].map(INDICADOR_AREA).fillna("Estoque/Educação")
    df["tipo"] = np.where(df["indicador"].isin(ESTOQUES), "estoque", "fluxo")
    df = df.sort_values(["ano", "mes", "indicador"]).reset_index(drop=True)
    return df, erros


def serie_temporal(df, indicador):
    """Devolve uma série contínua (índice datetime mensal, ordenado) de um
    indicador — útil para análises de defasagem/lag sem quebrar na virada
    de ano."""
    s = (df[df["indicador"] == indicador]
         .set_index("data")["valor"]
         .sort_index())
    return s


def diagnostico_arquivos(data_dir):
    """Relatório de completude por arquivo LEM_*.xlsx encontrado em data_dir.
    Foi o critério usado para escolher a fonte oficial de cada ano."""
    linhas = []
    for path in sorted(glob.glob(os.path.join(data_dir, "LEM_*.xlsx"))):
        fname = os.path.basename(path)
        if "anual" in fname or "completo" in fname:
            continue
        try:
            d = _extrair_arquivo(path, 2000)
            linhas.append({
                "arquivo": fname,
                "indicadores": d["indicador"].nunique(),
                "valores_preenchidos": int(d["valor"].notna().sum()),
                "valores_ausentes": int(d["valor"].isna().sum()),
            })
        except Exception as e:  # noqa: BLE001
            linhas.append({"arquivo": fname, "erro": str(e)})
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    ddir = os.path.join(here, "data")
    df, erros = carregar_dados(ddir)
    print("Erros:", erros)
    print("Shape:", df.shape)
    print(df.groupby("ano")["valor"].count())
    out = os.path.join(ddir, "lem_consolidado.csv")
    df.to_csv(out, index=False)
    print("CSV salvo em:", out)
