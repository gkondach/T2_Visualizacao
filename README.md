# Dashboard LEM — Fundação Pão dos Pobres (Parte II)

Dashboard interativo em Streamlit que responde às 5 **Perguntas de Negócio** do
pitch (Parte I), a partir do Levantamento Estatístico Mensal (LEM) 2021–2025.

## Como rodar

### Opção 1 — Windows, automático (recomendado)

Dê 2 cliques em **`rodar_dashboard.bat`**.

Na primeira vez, o script:
- verifica se o Python está instalado (e orienta a instalação caso não esteja);
- cria um ambiente virtual isolado (`.venv`) dentro da própria pasta do projeto;
- instala automaticamente todas as bibliotecas do `requirements.txt`;
- abre o dashboard no navegador.

Nas próximas vezes, basta dar 2 cliques de novo — ele pula direto para abrir o
dashboard. Não é necessário abrir terminal nem instalar nada manualmente (além
do Python em si, se ainda não estiver no computador).

### Opção 2 — manual (qualquer sistema operacional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

O app abre no navegador (geralmente http://localhost:8501).

## Estrutura

```
.
├── app.py                 # dashboard Streamlit — 1 aba por Pergunta de Negócio
├── pipeline.py             # lê as planilhas LEM_<ano>.xlsx e consolida em formato long
├── requirements.txt
├── rodar_dashboard.bat     # instala tudo e abre o dashboard automaticamente (Windows)
├── README.md
└── data/                  # fonte oficial: versão mais completa de cada ano (2021–2025)
    ├── LEM_2021.xlsx
    ├── LEM_2022_1.xlsx
    ├── LEM_2023.xlsx
    ├── LEM_2024_1.xlsx
    └── LEM_2025_3.xlsx
```

- **`pipeline.py`** lê as planilhas, corrige os nomes dos indicadores (a planilha
  original tem erros de digitação, ex.: *"Atendimentos indvidual"*), separa cada
  indicador em **fluxo** (evento contável no mês) ou **estoque** (contagem de um
  estado, ex.: nº de residentes, nº de matriculados) e devolve um único DataFrame
  no formato *long* (`ano, mes, indicador, valor, nome, area, tipo`).
- **`app.py`** monta o dashboard com uma aba por pergunta.

### Perguntas de Negócio (abas)

| # | Pergunta | Visualização principal |
|---|----------|------------------------|
| ① | Quais áreas concentram maior volume de atendimentos? | barras por área + rosca + ranking |
| ② | Existe relação entre atendimentos e saúde mental? | heatmap de correlação + dispersão + lag + sazonalidade |
| ③ | Encaminhamentos resultam em inserção efetiva? | funis de conversão + linha anual |
| ④ | Onde estão os gargalos? | funil geral + educação + fluxo da casa |
| ⑤ | Como a variação mensal impacta o planejamento? | heatmap mês×ano + sazonalidade + volatilidade |

## Escolha da fonte oficial de cada ano

Alguns anos vieram em mais de uma versão (2024 e 2025). Escolhemos a versão com
mais meses preenchidos, medido pela função `pipeline.diagnostico_arquivos()`:

| Ano | Versões recebidas | Escolhida | Motivo |
|-----|-------------------|-----------|--------|
| 2024 | `LEM_2024`, `LEM_2024_1` | **`LEM_2024_1`** | 393 valores vs. 217 (10 meses) |
| 2025 | `LEM_2025_1`, `LEM_2025__2_`, `LEM_2025_3` | **`LEM_2025_3`** | 384 valores (12 meses) — mais completa |

Os totais consolidados batem exatamente com o relatório da Parte I
(`atend_individual` = 3.106, `atend_familiar` = 1.703, `saude_mental` = 1.449,
`prof_inseridos_mercado` = 287; individuais + familiares + saúde mental = 6.258,
o número do funil do slide 8).

## Adicionar um novo período no futuro

1. Salve o novo arquivo em `data/` no padrão `LEM_<ano>.xlsx` (mesmo layout:
   coluna 0 = indicador, colunas 1–12 = JAN…DEZ).
2. Adicione a entrada em `FILE_MAP` no `pipeline.py` **ou** use o campo de upload
   na barra lateral do próprio dashboard.
3. Nada mais precisa ser alterado — pipeline e gráficos se atualizam sozinhos.

## Sobre a Pergunta 2 (atendimento × saúde mental) e as datas comemorativas

A equipe levantou a hipótese de que **datas comemorativas voltadas à família**
(Dia das Mães, Dia dos Pais, Dia das Crianças, Natal) intensificam a demanda de
saúde mental — pois é quando crianças e adolescentes acolhidos mais sentem a
ausência de um vínculo familiar, ao contrário da imagem de "época feliz".

O dashboard testa isso na sazonalidade dos dados existentes. Resultado: a
hipótese tem **suporte parcial** — Natal (dezembro) e Dia dos Pais (agosto) ficam
acima da média de saúde mental, mas Dia das Mães (maio) não segue o padrão.

**Limitação:** a planilha LEM só tem o total mensal, sem a data (dia) nem o motivo
do atendimento, então não dá para *provar* a ligação com uma data específica.
Fica como recomendação de melhoria de coleta (registrar a data de cada
atendimento de saúde mental) para o relatório da Parte II.

## Dado adicional não integrado

O arquivo `LEM_anual_2025_completo.xlsx` traz abas qualitativas (atividades
culturais, capacitações de equipes/coordenações, participação em espaços de
controle social) em texto livre. Por ter estrutura diferente das planilhas
mensais, ficou fora do escopo numérico deste dashboard, documentado como fonte
de integração futura.
