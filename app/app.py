"""App Streamlit: lê só os arquivos locais em data/processados/ e resultados/.

Uso: streamlit run app/app.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
PROCESSADOS = RAIZ / "data" / "processados"
RESULTADOS = RAIZ / "resultados"

VARIAVEIS = {
    "pct_16_17": "% com 16 ou 17 anos",
    "pct_70_mais": "% com 70 anos ou mais",
    "pct_feminino": "% feminino",
    "pct_baixa_escolaridade": "% analfabeto ou lê e escreve",
    "pct_superior": "% com superior completo",
    "aptos": "Eleitorado apto",
    "pib_per_capita": "PIB per capita (R$)",
    "razao_aptos_populacao": "Eleitores aptos por habitante",
    "densidade": "Habitantes por km²",
}

def br(valor: float, casas: int = 2, sinal: bool = False) -> str:
    """Número no formato brasileiro (vírgula decimal)."""
    texto = f"{valor:+.{casas}f}" if sinal else f"{valor:.{casas}f}"
    return texto.replace(".", ",")


st.set_page_config(page_title="O que explica a abstenção", layout="wide")


@st.cache_data
def carregar(ano: int):
    mun = pd.read_parquet(PROCESSADOS / f"municipios_{ano}.parquet")
    oof = pd.read_parquet(RESULTADOS / f"previsoes_oof_{ano}.parquet")
    mun = mun.merge(
        oof[["id_municipio", "gradient_boosting__groupkfold_uf"]].rename(
            columns={"gradient_boosting__groupkfold_uf": "previsto_pp"}),
        on="id_municipio", how="left")
    coef = pd.read_csv(RESULTADOS / f"coeficientes_{ano}.csv")
    imp = pd.read_csv(RESULTADOS / f"importancia_permutacao_{ano}.csv")
    inferencia = json.loads((RESULTADOS / f"inferencia_{ano}.json").read_text(encoding="utf-8"))
    modelo = json.loads((RESULTADOS / f"modelo_{ano}.json").read_text(encoding="utf-8"))
    return mun, coef, imp, inferencia, modelo


st.title("O que explica a abstenção")
st.caption("Abstenção no 1º turno da eleição para presidente, por município. "
           "Dados do TSE e do IBGE via Base dos Dados. Autor: Deyvid Prado.")

ano = st.sidebar.radio("Eleição", [2022, 2018], index=0)
mun, coef, imp, inferencia, modelo = carregar(ano)
mun = mun.copy()
mun["abstencao_pct"] = mun["abstencao_pct"].astype(float)

nacional = 100 * mun["abstencoes"].sum() / mun["aptos"].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Municípios", f"{len(mun):,}".replace(",", "."))
c2.metric("Abstenção no país", br(nacional) + "%")
c3.metric("Mediana entre municípios", br(mun["abstencao_pct"].median()) + "%")
c4.metric("R² da regressão", br(inferencia["r2"]))

aba_uf, aba_dist, aba_efeitos, aba_busca = st.tabs(
    ["Por UF", "Distribuição", "Efeitos do modelo", "Buscar município"])

with aba_uf:
    st.subheader("Abstenção por município")
    mapa = px.scatter_geo(
        mun, lat="latitude", lon="longitude", color="abstencao_pct",
        hover_name="nome", hover_data={"sigla_uf": True, "abstencao_pct": ":.1f",
                                       "latitude": False, "longitude": False},
        color_continuous_scale="Viridis", labels={"abstencao_pct": "Abstenção (%)"})
    mapa.update_traces(marker={"size": 3})
    mapa.update_geos(fitbounds="locations", showcountries=True, showland=True)
    mapa.update_layout(height=600, margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(mapa, width="stretch")

    por_uf = (mun.groupby(["sigla_uf", "regiao"], as_index=False)
              .agg(municipios=("id_municipio", "count"), aptos=("aptos", "sum"),
                   abstencoes=("abstencoes", "sum"),
                   mediana_municipal=("abstencao_pct", "median")))
    por_uf["abstencao_uf_pct"] = 100 * por_uf["abstencoes"] / por_uf["aptos"]
    por_uf = por_uf.sort_values("abstencao_uf_pct", ascending=False)
    barras = px.bar(por_uf, x="sigla_uf", y="abstencao_uf_pct", color="regiao",
                    labels={"sigla_uf": "UF", "abstencao_uf_pct": "Abstenção na UF (%)",
                            "regiao": "Região"})
    st.plotly_chart(barras, width="stretch")
    st.dataframe(
        por_uf[["sigla_uf", "regiao", "municipios", "aptos", "abstencao_uf_pct",
                "mediana_municipal"]].rename(columns={
                    "sigla_uf": "UF", "regiao": "Região", "municipios": "Municípios",
                    "aptos": "Aptos", "abstencao_uf_pct": "Abstenção na UF (%)",
                    "mediana_municipal": "Mediana municipal (%)"}),
        hide_index=True, width="stretch")

with aba_dist:
    st.subheader("Distribuição da taxa de abstenção entre municípios")
    hist = px.histogram(mun, x="abstencao_pct", nbins=60, color="regiao",
                        labels={"abstencao_pct": "Abstenção (%)", "regiao": "Região"})
    st.plotly_chart(hist, width="stretch")
    st.write(mun["abstencao_pct"].describe().rename({
        "count": "municípios", "mean": "média", "std": "desvio padrão", "min": "mínimo",
        "25%": "1º quartil", "50%": "mediana", "75%": "3º quartil", "max": "máximo"}).round(2))

with aba_efeitos:
    st.subheader("Regressão linear (erros agrupados por UF)")
    st.write("Cada barra mostra quanto a abstenção muda, em pontos percentuais, quando a "
             "variável sai do 1º para o 3º quartil e as outras ficam iguais. A linha é o "
             "intervalo de 95%. É associação, não causa.")
    vars_coef = coef[coef["iqr_variavel"].notna()].copy()
    vars_coef["ic_inf_q"] = vars_coef["ic95_inf"] * vars_coef["iqr_variavel"]
    vars_coef["ic_sup_q"] = vars_coef["ic95_sup"] * vars_coef["iqr_variavel"]
    vars_coef["erro_menos"] = vars_coef["efeito_q1_q3_pp"] - vars_coef["ic_inf_q"]
    vars_coef["erro_mais"] = vars_coef["ic_sup_q"] - vars_coef["efeito_q1_q3_pp"]
    vars_coef = vars_coef.sort_values("efeito_q1_q3_pp")
    graf = px.bar(vars_coef, x="efeito_q1_q3_pp", y="descricao", orientation="h",
                  error_x="erro_mais", error_x_minus="erro_menos",
                  labels={"efeito_q1_q3_pp": "Efeito do 1º ao 3º quartil (p.p.)",
                          "descricao": ""})
    st.plotly_chart(graf, width="stretch")
    st.dataframe(coef[["descricao", "coef_pp", "ic95_inf", "ic95_sup", "p_cluster_uf",
                       "p_hc3"]].rename(columns={
                           "descricao": "Termo", "coef_pp": "Coeficiente (p.p.)",
                           "ic95_inf": "IC 95% inf.", "ic95_sup": "IC 95% sup.",
                           "p_cluster_uf": "p (cluster UF)", "p_hc3": "p (HC3)"}).round(4),
                 hide_index=True, width="stretch")

    st.subheader("Modelo de árvores: importância por permutação")
    st.write("Quanto o erro médio (MAE) do gradient boosting aumenta quando a coluna é "
             "embaralhada, medido em UFs que o modelo não viu no treino.")
    graf_imp = px.bar(imp.sort_values("aumento_mae_pp_medio"), x="aumento_mae_pp_medio",
                      y="descricao", orientation="h", error_x="desvio_entre_partes",
                      labels={"aumento_mae_pp_medio": "Aumento do MAE (p.p.)",
                              "descricao": ""})
    st.plotly_chart(graf_imp, width="stretch")

    linhas = []
    for cv, ms in modelo["validacoes"].items():
        for nome, v in ms.items():
            linhas.append({"Validação": cv, "Modelo": nome,
                           "MAE (p.p.)": round(v["mae_pp_empilhado"], 2),
                           "R²": round(v["r2_empilhado"], 3)})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

with aba_busca:
    st.subheader("Buscar município")
    mun["rotulo"] = mun["nome"] + " (" + mun["sigla_uf"] + ")"
    escolha = st.selectbox("Município", sorted(mun["rotulo"]), index=None,
                           placeholder="Digite o nome")
    if escolha:
        linha = mun[mun["rotulo"] == escolha].iloc[0]
        a, b, c = st.columns(3)
        a.metric("Abstenção observada", br(linha["abstencao_pct"]) + "%")
        b.metric("Prevista pelo modelo", br(linha["previsto_pp"]) + "%",
                 help="Gradient boosting treinado sem a UF deste município (GroupKFold).")
        c.metric("Diferença", br(linha["abstencao_pct"] - linha["previsto_pp"], sinal=True) + " p.p.")
        comparacao = pd.DataFrame({
            "Variável": list(VARIAVEIS.values()),
            "Município": [float(linha[v]) for v in VARIAVEIS],
            "Mediana nacional": [float(mun[v].astype(float).median()) for v in VARIAVEIS],
        })
        st.dataframe(comparacao.round(3), hide_index=True, width="stretch")
        st.caption(f"Aptos: {int(linha['aptos']):,} · zonas eleitorais: {int(linha['n_zonas'])}"
                   .replace(",", "."))
