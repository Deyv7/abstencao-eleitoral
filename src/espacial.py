"""Dependência espacial: municípios vizinhos erram juntos?

A regressão trata cada município como independente, e o erro agrupado por UF
corrige isso só dentro de cada estado. Este módulo mede se os resíduos de
municípios vizinhos se parecem mesmo quando a divisa entre estados está no meio.

- Vizinhança: os K municípios mais próximos pelo centroide (distância na esfera).
  Cada vizinho tem o mesmo peso, então a "média dos vizinhos" é uma média simples.
- I de Moran: correlação entre o valor de cada município e a média dos vizinhos,
  na escala de -1 a 1. O valor esperado sem dependência espacial é -1/(n-1),
  quase zero. O valor-p sai de 999 permutações: sorteia os valores entre os
  municípios e conta quantas vezes o acaso chega ao I observado.
- Validação cruzada espacial: o random forest e a regressão linear do
  src/modelo.py, com grupos formados por agrupamento das coordenadas em vez da UF.

Uso: python -m src.espacial [--anos 2022 2018]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import BallTree
import statsmodels.formula.api as smf

from src.analise import FORMULA, RESULTADOS, carregar
from src.features import ALVO
from src.modelo import ENTRADAS, N_PARTES, SEED, modelos

K = 8
K_SENSIBILIDADE = (5, 10)
N_PERMUTACOES = 999
RAIO_TERRA_KM = 6371.0
# Número de grupos espaciais: o mesmo das UFs, para comparar com o GroupKFold por UF
# com grupos de tamanho parecido, e um número maior, com grupos menores.
GRUPOS_ESPACIAIS = (27, 60)


def vizinhos(lat: np.ndarray, lon: np.ndarray, k: int = K) -> tuple[np.ndarray, np.ndarray]:
    """Índices e distâncias (km) dos k vizinhos mais próximos de cada município."""
    coords = np.radians(np.column_stack([lat, lon]))
    dist, idx = BallTree(coords, metric="haversine").query(coords, k=k + 1)
    return idx[:, 1:], dist[:, 1:] * RAIO_TERRA_KM  # a coluna 0 é o próprio município


def media_vizinhos(x: np.ndarray, idx: np.ndarray) -> np.ndarray:
    return x[idx].mean(axis=1)


def moran(x: np.ndarray, idx: np.ndarray) -> float:
    """I de Moran com pesos iguais por vizinho (matriz padronizada por linha)."""
    z = x - x.mean()
    return float((z * media_vizinhos(z, idx)).sum() / (z * z).sum())


def moran_com_teste(x: np.ndarray, idx: np.ndarray, n_perm: int = N_PERMUTACOES,
                    seed: int = SEED) -> dict:
    observado = moran(x, idx)
    rng = np.random.default_rng(seed)
    sorteios = np.array([moran(rng.permutation(x), idx) for _ in range(n_perm)])
    return {
        "i": observado,
        "esperado_sem_dependencia": -1 / (len(x) - 1),
        "p_permutacao": float((1 + (sorteios >= observado).sum()) / (n_perm + 1)),
        "z": float((observado - sorteios.mean()) / sorteios.std()),
        "maior_i_entre_permutacoes": float(sorteios.max()),
    }


def correlacao_com_vizinhos_de_outra_uf(resid: np.ndarray, uf: np.ndarray,
                                        idx: np.ndarray) -> dict:
    """Só os vizinhos do outro lado da divisa: a UF não explica essa semelhança."""
    outra = uf[idx] != uf[:, None]
    tem = outra.any(axis=1)
    somas = np.where(outra, resid[idx], 0.0).sum(axis=1)
    media_outra = somas[tem] / outra[tem].sum(axis=1)
    return {
        "municipios_com_vizinho_de_outra_uf": int(tem.sum()),
        "correlacao": float(np.corrcoef(resid[tem], media_outra)[0, 1]),
    }


def validacao_espacial(df: pd.DataFrame) -> dict:
    """R² e MAE fora da amostra com grupos espaciais, comparados aos grupos por UF."""
    X, y = df[ENTRADAS], df[ALVO].to_numpy()
    esquemas = {"uf": df["sigla_uf"].to_numpy()}
    for n in GRUPOS_ESPACIAIS:
        esquemas[f"clusters_{n}"] = grupos_espaciais(df, n)
    saida = {}
    for nome, grupos in esquemas.items():
        partes = list(GroupKFold(n_splits=N_PARTES, shuffle=True, random_state=SEED).split(df, groups=grupos))
        saida[nome] = {}
        for nome_modelo in ("regressao_linear", "random_forest"):
            modelo = modelos()[nome_modelo]
            oof = np.empty(len(df))
            for tr, te in partes:
                oof[te] = modelo.fit(X.iloc[tr], y[tr]).predict(X.iloc[te])
            saida[nome][nome_modelo] = {"r2": float(r2_score(y, oof)),
                                        "mae_pp": float(mean_absolute_error(y, oof))}
    return saida


def grupos_espaciais(df: pd.DataFrame, n: int) -> np.ndarray:
    coords = np.column_stack([df["latitude"], df["longitude"] * np.cos(np.radians(df["latitude"]))])
    return KMeans(n_clusters=n, n_init=10, random_state=SEED).fit_predict(coords)


def erro_agrupado_espacial(df: pd.DataFrame) -> dict:
    """A mesma regressão, com o erro agrupado por grupos de municípios próximos.

    Os grupos atravessam as divisas entre estados. Se um coeficiente só é
    significativo com o agrupamento por UF, a significância dele depende de ignorar
    a semelhança entre vizinhos de estados diferentes.
    """
    saida = {}
    for n in GRUPOS_ESPACIAIS:
        ajuste = smf.ols(FORMULA, data=df).fit(cov_type="cluster",
                                               cov_kwds={"groups": grupos_espaciais(df, n)})
        saida[f"clusters_{n}"] = {t: {"coef_pp": float(ajuste.params[t]), "p": float(ajuste.pvalues[t])}
                                  for t in ajuste.params.index if t != "Intercept"}
    return saida


def analisar(ano: int) -> dict:
    df = carregar(ano)
    res = pd.read_parquet(RESULTADOS / f"residuos_ols_{ano}.parquet")
    df = df.merge(res, on="id_municipio", how="inner", validate="1:1")
    assert len(df) == len(res), "resíduos sem município correspondente"

    idx, dist = vizinhos(df["latitude"].to_numpy(), df["longitude"].to_numpy())
    resid = df["residuo_pp"].to_numpy()
    uf = df["sigla_uf"].to_numpy()
    lag = media_vizinhos(resid, idx)
    resid_sem_uf = resid - df.groupby("sigla_uf")["residuo_pp"].transform("mean").to_numpy()

    resumo = {
        "ano": ano,
        "k_vizinhos": K,
        "permutacoes": N_PERMUTACOES,
        "distancia_mediana_vizinho_km": float(np.median(dist)),
        "distancia_mediana_mais_proximo_km": float(np.median(dist[:, 0])),
        "pct_vizinhos_mesma_uf": float((uf[idx] == uf[:, None]).mean() * 100),
        "moran_abstencao": moran_com_teste(df[ALVO].to_numpy(), idx),
        "moran_residuo": moran_com_teste(resid, idx),
        "moran_residuo_sensibilidade_k": {
            str(k): moran(resid, vizinhos(df["latitude"].to_numpy(), df["longitude"].to_numpy(), k)[0])
            for k in K_SENSIBILIDADE},
        "moran_residuo_sem_media_da_uf": moran_com_teste(resid_sem_uf, idx),
        "r2_residuo_explicado_pela_media_dos_vizinhos": float(np.corrcoef(resid, lag)[0, 1] ** 2),
        "vizinhos_de_outra_uf": correlacao_com_vizinhos_de_outra_uf(resid, uf, idx),
        "erro_agrupado_espacial": erro_agrupado_espacial(df),
        "validacao_cruzada": validacao_espacial(df),
    }
    RESULTADOS.mkdir(exist_ok=True)
    (RESULTADOS / f"espacial_{ano}.json").write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame({"id_municipio": df["id_municipio"], "residuo_pp": resid,
                  "residuo_vizinhos_pp": lag}).to_parquet(
        RESULTADOS / f"residuos_espaciais_{ano}.parquet", index=False)

    m = resumo["moran_residuo"]
    vc = resumo["validacao_cruzada"]
    print(f"[espacial] {ano}: I de Moran dos resíduos {m['i']:.3f} (p {m['p_permutacao']:.3f}); "
          f"média dos vizinhos explica {resumo['r2_residuo_explicado_pela_media_dos_vizinhos']:.1%} "
          f"dos resíduos; RF R² por UF {vc['uf']['random_forest']['r2']:.3f}, "
          + ", ".join(f"{k} {v['random_forest']['r2']:.3f}" for k, v in vc.items() if k != "uf"))
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anos", type=int, nargs="+", default=[2022, 2018])
    for ano in parser.parse_args().anos:
        analisar(ano)


if __name__ == "__main__":
    main()
