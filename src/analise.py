"""Regressão linear da taxa de abstenção (statsmodels).

Ajusta um modelo de mínimos quadrados com erros agrupados por UF (principal)
e HC3 (comparação), mede VIF, examina os resíduos e grava os resultados em
resultados/. É associação, não causa: o modelo descreve quais características
andam junto com a abstenção quando as outras ficam fixas.

Uso: python -m src.analise [--anos 2022 2018]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera

from src.bq import RAIZ
from src.features import ALVO, PROCESSADOS, VARIAVEIS

RESULTADOS = RAIZ / "resultados"
REGIAO_REFERENCIA = "Sudeste"
FORMULA = f"{ALVO} ~ " + " + ".join(VARIAVEIS) + \
    f' + C(regiao, Treatment("{REGIAO_REFERENCIA}"))'

NOMES = {
    "Intercept": "Intercepto",
    "pct_16_17": "% do eleitorado com 16 ou 17 anos",
    "pct_70_mais": "% do eleitorado com 70 anos ou mais",
    "pct_feminino": "% do eleitorado feminino",
    "pct_baixa_escolaridade": "% analfabeto ou lê e escreve",
    "pct_superior": "% com superior completo",
    "log2_aptos": "Eleitorado apto (cada vez que dobra)",
    "log2_pib_per_capita": "PIB per capita (cada vez que dobra)",
    "razao_aptos_populacao": "Eleitores aptos por habitante",
    "log2_densidade": "Densidade demográfica (cada vez que dobra)",
}


def termo_curto(termo: str) -> str:
    if termo.startswith("C(regiao"):
        return "regiao_" + termo.split("[T.")[1].rstrip("]")
    return termo


def nome_legivel(termo: str) -> str:
    if termo.startswith("C(regiao"):
        return "Região " + termo.split("[T.")[1].rstrip("]") + f" (vs. {REGIAO_REFERENCIA})"
    return NOMES.get(termo, termo)


def carregar(ano: int) -> pd.DataFrame:
    df = pd.read_parquet(PROCESSADOS / f"municipios_{ano}.parquet")
    for c in VARIAVEIS + [ALVO]:
        df[c] = df[c].astype(float)
    return df


def ajustar(df: pd.DataFrame):
    modelo = smf.ols(FORMULA, data=df)
    grupos = pd.factorize(df["sigla_uf"])[0]
    # Principal: erro agrupado por UF, com correção para poucos grupos e
    # distribuição t com (número de UFs - 1) graus de liberdade.
    cluster = modelo.fit(cov_type="cluster", cov_kwds={"groups": grupos}, use_t=True)
    hc3 = modelo.fit(cov_type="HC3")
    simples = modelo.fit()
    return cluster, hc3, simples


def tabela_vif(df: pd.DataFrame) -> pd.DataFrame:
    regioes = pd.get_dummies(df["regiao"], prefix="regiao", dtype=float).drop(
        columns=f"regiao_{REGIAO_REFERENCIA}")
    X = pd.concat([df[VARIAVEIS], regioes], axis=1)
    X.insert(0, "const", 1.0)
    linhas = [
        {"variavel": c, "vif": variance_inflation_factor(X.values, i)}
        for i, c in enumerate(X.columns) if c != "const"
    ]
    return pd.DataFrame(linhas)


def diagnostico_residuos(simples, df: pd.DataFrame) -> dict:
    resid = simples.resid
    bp_lm, bp_p, _, _ = het_breuschpagan(resid, simples.model.exog)
    jb, jb_p, assimetria, curtose = jarque_bera(resid)
    # Quanto da variação dos resíduos é explicada só pela UF. Se for alto,
    # municípios da mesma UF erram "juntos" e o erro padrão comum fica otimista.
    r2_uf = smf.ols("r ~ C(uf)", data=pd.DataFrame({"r": resid, "uf": df["sigla_uf"]})).fit().rsquared
    return {
        "breusch_pagan_estatistica": float(bp_lm),
        "breusch_pagan_p": float(bp_p),
        "jarque_bera_estatistica": float(jb),
        "jarque_bera_p": float(jb_p),
        "assimetria": float(assimetria),
        "curtose": float(curtose),
        "desvio_padrao_residuo_pp": float(np.std(resid, ddof=simples.df_model + 1)),
        "pct_residuos_alem_de_2dp": float(np.mean(np.abs(resid) > 2 * np.std(resid)) * 100),
        "r2_residuo_explicado_por_uf": float(r2_uf),
    }


def coeficientes(cluster, hc3, df: pd.DataFrame) -> pd.DataFrame:
    ic = cluster.conf_int()
    tab = pd.DataFrame({
        "termo": [termo_curto(t) for t in cluster.params.index],
        "descricao": [nome_legivel(t) for t in cluster.params.index],
        "coef_pp": cluster.params.values,
        "ep_cluster_uf": cluster.bse.values,
        "p_cluster_uf": cluster.pvalues.values,
        "ic95_inf": ic[0].values,
        "ic95_sup": ic[1].values,
        "ep_hc3": hc3.bse.values,
        "p_hc3": hc3.pvalues.values,
    })
    # Efeito de sair do 1º quartil para o 3º quartil de cada variável,
    # com as outras fixas. Põe as variáveis numa régua comum (p.p. de abstenção).
    iqr = {c: df[c].quantile(0.75) - df[c].quantile(0.25) for c in VARIAVEIS}
    tab["iqr_variavel"] = tab["termo"].map(iqr)
    tab["efeito_q1_q3_pp"] = tab["coef_pp"] * tab["iqr_variavel"]
    return tab


def robustez_efeito_fixo_uf(df: pd.DataFrame) -> dict:
    """Mesmo modelo trocando região por UF (efeito fixo de estado)."""
    formula = f"{ALVO} ~ " + " + ".join(VARIAVEIS) + " + C(sigla_uf)"
    grupos = pd.factorize(df["sigla_uf"])[0]
    m = smf.ols(formula, data=df).fit(cov_type="cluster", cov_kwds={"groups": grupos}, use_t=True)
    return {
        "r2": float(m.rsquared),
        "coeficientes": {
            v: {"coef_pp": float(m.params[v]), "p_cluster_uf": float(m.pvalues[v])}
            for v in VARIAVEIS
        },
    }


def analisar(ano: int) -> dict:
    df = carregar(ano)
    cluster, hc3, simples = ajustar(df)
    coef = coeficientes(cluster, hc3, df)
    vif = tabela_vif(df)
    diag = diagnostico_residuos(simples, df)
    so_uf = smf.ols(f"{ALVO} ~ C(sigla_uf)", data=df).fit().rsquared
    so_regiao = smf.ols(f"{ALVO} ~ C(regiao)", data=df).fit().rsquared

    RESULTADOS.mkdir(exist_ok=True)
    coef.to_csv(RESULTADOS / f"coeficientes_{ano}.csv", index=False, float_format="%.6g")
    vif.to_csv(RESULTADOS / f"vif_{ano}.csv", index=False, float_format="%.4g")
    pd.DataFrame({
        "id_municipio": df["id_municipio"],
        "ajustado_pp": simples.fittedvalues,
        "residuo_pp": simples.resid,
    }).to_parquet(RESULTADOS / f"residuos_ols_{ano}.parquet", index=False)

    resumo = {
        "ano": ano,
        "n_municipios": int(simples.nobs),
        "n_ufs": int(df["sigla_uf"].nunique()),
        "formula": FORMULA,
        "r2": float(simples.rsquared),
        "r2_ajustado": float(simples.rsquared_adj),
        "r2_so_uf": float(so_uf),
        "r2_so_regiao": float(so_regiao),
        "media_abstencao_pp": float(df[ALVO].mean()),
        "desvio_abstencao_pp": float(df[ALVO].std()),
        "vif_maximo": float(vif["vif"].max()),
        "residuos": diag,
        "robustez_efeito_fixo_uf": robustez_efeito_fixo_uf(df),
    }
    (RESULTADOS / f"inferencia_{ano}.json").write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[analise] {ano}: R² = {resumo['r2']:.3f}, VIF máximo = {resumo['vif_maximo']:.2f}")
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anos", type=int, nargs="+", default=[2022, 2018])
    for ano in parser.parse_args().anos:
        analisar(ano)


if __name__ == "__main__":
    main()
