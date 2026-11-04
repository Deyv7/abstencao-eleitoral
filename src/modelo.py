"""Modelo de ML (scikit-learn): baselines contra modelos de árvores.

Compara quatro modelos com duas formas de validação cruzada:
- KFold: 5 partes sorteadas entre todos os municípios;
- GroupKFold por UF: cada UF inteira fica só no treino ou só no teste.

Métricas: MAE (em pontos percentuais de abstenção) e R². A importância por
permutação é medida nas partes de teste do GroupKFold. Seed fixa em 42.

Uso: python -m src.modelo [--anos 2022 2018]
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.analise import NOMES, RESULTADOS, carregar
from src.features import ALVO, VARIAVEIS

SEED = 42
N_PARTES = 5
ENTRADAS = VARIAVEIS + ["regiao"]


def preprocessador(drop: str | None) -> ColumnTransformer:
    return ColumnTransformer(
        [("regiao", OneHotEncoder(drop=drop, handle_unknown="ignore"), ["regiao"])],
        remainder="passthrough",
    )


def modelos() -> dict[str, Pipeline]:
    return {
        "media": Pipeline([("prep", preprocessador(None)), ("m", DummyRegressor())]),
        "regressao_linear": Pipeline([("prep", preprocessador("first")),
                                      ("m", LinearRegression())]),
        "gradient_boosting": Pipeline([("prep", preprocessador(None)),
                                       ("m", HistGradientBoostingRegressor(random_state=SEED))]),
        "random_forest": Pipeline([("prep", preprocessador(None)),
                                   ("m", RandomForestRegressor(
                                       n_estimators=300, min_samples_leaf=5,
                                       random_state=SEED, n_jobs=-1))]),
    }


def divisores(df: pd.DataFrame) -> dict:
    grupos = df["sigla_uf"].to_numpy()
    kf = KFold(n_splits=N_PARTES, shuffle=True, random_state=SEED)
    gkf = GroupKFold(n_splits=N_PARTES, shuffle=True, random_state=SEED)
    return {
        "kfold": list(kf.split(df)),
        "groupkfold_uf": list(gkf.split(df, groups=grupos)),
    }


def avaliar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    X, y = df[ENTRADAS], df[ALVO].to_numpy()
    linhas, previsoes = [], {"id_municipio": df["id_municipio"].to_numpy()}
    for nome_cv, partes in divisores(df).items():
        for nome_modelo, modelo in modelos().items():
            oof = np.empty(len(df))
            for i, (tr, te) in enumerate(partes):
                modelo.fit(X.iloc[tr], y[tr])
                pred = modelo.predict(X.iloc[te])
                oof[te] = pred
                linhas.append({"validacao": nome_cv, "modelo": nome_modelo, "parte": i,
                               "n_teste": len(te),
                               "mae_pp": mean_absolute_error(y[te], pred),
                               "r2": r2_score(y[te], pred)})
            # Métrica "empilhada": junta as previsões fora da amostra de todas as
            # partes e calcula uma vez sobre os 5.570 municípios.
            linhas.append({"validacao": nome_cv, "modelo": nome_modelo, "parte": "todas",
                           "n_teste": len(df),
                           "mae_pp": mean_absolute_error(y, oof), "r2": r2_score(y, oof)})
            previsoes[f"{nome_modelo}__{nome_cv}"] = oof
    return pd.DataFrame(linhas), pd.DataFrame(previsoes)


def importancia_permutacao(df: pd.DataFrame, nome_modelo: str = "gradient_boosting"):
    """Importância por permutação nas partes de teste do GroupKFold por UF."""
    X, y = df[ENTRADAS], df[ALVO].to_numpy()
    resultados = []
    for i, (tr, te) in enumerate(divisores(df)["groupkfold_uf"]):
        modelo = modelos()[nome_modelo].fit(X.iloc[tr], y[tr])
        r = permutation_importance(modelo, X.iloc[te], y[te], n_repeats=10,
                                   random_state=SEED, scoring="neg_mean_absolute_error")
        for j, var in enumerate(ENTRADAS):
            resultados.append({"parte": i, "variavel": var,
                               "aumento_mae_pp": r.importances_mean[j]})
    tab = (pd.DataFrame(resultados).groupby("variavel")["aumento_mae_pp"]
           .agg(["mean", "std"]).reset_index()
           .rename(columns={"mean": "aumento_mae_pp_medio", "std": "desvio_entre_partes"})
           .sort_values("aumento_mae_pp_medio", ascending=False))
    tab["descricao"] = tab["variavel"].map({**NOMES, "regiao": "Região"})
    return tab


def rodar(ano: int) -> dict:
    df = carregar(ano)
    metricas, previsoes = avaliar(df)
    imp = importancia_permutacao(df)
    RESULTADOS.mkdir(exist_ok=True)
    metricas.to_csv(RESULTADOS / f"metricas_cv_{ano}.csv", index=False, float_format="%.6g")
    previsoes.to_parquet(RESULTADOS / f"previsoes_oof_{ano}.parquet", index=False)
    imp.to_csv(RESULTADOS / f"importancia_permutacao_{ano}.csv", index=False,
               float_format="%.6g")

    resumo_partes = (metricas[metricas["parte"] != "todas"]
                     .groupby(["validacao", "modelo"])[["mae_pp", "r2"]]
                     .agg(["mean", "std"]))
    empilhado = metricas[metricas["parte"] == "todas"].set_index(["validacao", "modelo"])
    resumo = {"ano": ano, "seed": SEED, "n_partes": N_PARTES, "validacoes": {}}
    for (cv, modelo), linha in empilhado.iterrows():
        resumo["validacoes"].setdefault(cv, {})[modelo] = {
            "mae_pp_empilhado": float(linha["mae_pp"]),
            "r2_empilhado": float(linha["r2"]),
            "mae_pp_media_partes": float(resumo_partes.loc[(cv, modelo), ("mae_pp", "mean")]),
            "r2_media_partes": float(resumo_partes.loc[(cv, modelo), ("r2", "mean")]),
            "r2_desvio_partes": float(resumo_partes.loc[(cv, modelo), ("r2", "std")]),
        }
    (RESULTADOS / f"modelo_{ano}.json").write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")
    for cv, ms in resumo["validacoes"].items():
        txt = ", ".join(f"{m}: MAE {v['mae_pp_empilhado']:.2f} R² {v['r2_empilhado']:.3f}"
                        for m, v in ms.items())
        print(f"[modelo] {ano} {cv}: {txt}")
    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anos", type=int, nargs="+", default=[2022, 2018])
    for ano in parser.parse_args().anos:
        rodar(ano)


if __name__ == "__main__":
    main()
