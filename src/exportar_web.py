"""Exporta os dados e os resultados de 2022 para a página de storytelling em web/.

Todo número que a página mostra sai daqui, lido dos arquivos que o pipeline gravou
(data/processados/ e resultados/). A página não tem número escrito à mão.

Uso:
  python -m src.exportar_web
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "web" / "public" / "dados"
ANO = 2022

# Ordem norte -> sul, usada nas colunas por região da página.
REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]


def _r(x: float, casas: int = 2) -> float:
    return round(float(x), casas)


def _municipios() -> pd.DataFrame:
    mun = pd.read_parquet(RAIZ / "data" / "processados" / f"municipios_{ANO}.parquet")
    res = pd.read_parquet(RAIZ / "resultados" / f"residuos_ols_{ANO}.parquet")
    prev = pd.read_parquet(RAIZ / "resultados" / f"previsoes_oof_{ANO}.parquet")
    mun = mun.merge(res, on="id_municipio", how="left", validate="1:1")
    mun = mun.merge(prev[["id_municipio", "random_forest__groupkfold_uf"]],
                    on="id_municipio", how="left", validate="1:1")
    esp = pd.read_parquet(RAIZ / "resultados" / f"residuos_espaciais_{ANO}.parquet")
    mun = mun.merge(esp[["id_municipio", "residuo_vizinhos_pp"]], on="id_municipio",
                    how="left", validate="1:1")
    assert len(mun) == mun["id_municipio"].nunique()
    return mun.sort_values("id_municipio").reset_index(drop=True)


def _arquivo_municipios(mun: pd.DataFrame) -> dict:
    """Formato colunar: uma lista por variável, na mesma ordem de municípios."""
    return {
        "ano": ANO,
        "regioes": REGIOES,
        "id": mun["id_municipio"].tolist(),
        "nome": mun["nome"].tolist(),
        "uf": mun["sigla_uf"].tolist(),
        "regiao": [REGIOES.index(r) for r in mun["regiao"]],
        "lon": [_r(v, 4) for v in mun["longitude"]],
        "lat": [_r(v, 4) for v in mun["latitude"]],
        "abst": [_r(v) for v in mun["abstencao_pct"]],
        "aptos": [int(v) for v in mun["aptos"]],
        "abstencoes": [int(v) for v in mun["abstencoes"]],
        "baixa_esc": [_r(v) for v in mun["pct_baixa_escolaridade"]],
        "p70": [_r(v) for v in mun["pct_70_mais"]],
        "log2_aptos": [_r(v, 3) for v in mun["log2_aptos"]],
        "residuo": [_r(v) for v in mun["residuo_pp"]],
        "residuo_vizinhos": [_r(v) for v in mun["residuo_vizinhos_pp"]],
        "previsto_rf": [_r(v) for v in mun["random_forest__groupkfold_uf"]],
    }


def _armadilha() -> dict:
    """Soma dos aptos sem filtrar cargo, a partir da validação da fonte."""
    val = json.loads((RAIZ / "evidencias" / "validacao_fonte.json").read_text(encoding="utf-8"))
    grupos = [g for g in val["grupos_cargo_tipo"] if g["ano"] == ANO and g["turno"] == 1]
    return {"aptos_sem_filtro": int(sum(g["aptos"] for g in grupos)),
            "cargos_tipos": len(grupos)}


def _picos(mun: pd.DataFrame, por_uf: pd.DataFrame) -> dict:
    """Os picos do mapa são municípios; a taxa de um estado soma todos os eleitores dele.

    `exemplo` é o município com a maior abstenção entre os estados do terço com as
    menores taxas totais: um pico alto num estado que, somado, ficou baixo. `idx` é a
    posição do município em municipios.json.
    """
    a = mun["abstencao_pct"].astype(float)
    picos = [{"idx": int(i), "nome": mun.at[i, "nome"], "uf": mun.at[i, "sigla_uf"], "pct": _r(a[i])}
             for i in a.nlargest(3).index]
    ordem = list(por_uf.index)  # do estado com menor taxa para o de maior
    baixos = ordem[: len(ordem) // 3]
    cand = a[mun["sigla_uf"].isin(baixos)]
    i = cand.idxmax()
    uf = mun.at[i, "sigla_uf"]
    est = mun[mun["sigla_uf"] == uf]
    grandes = est.nlargest(10, "aptos")
    resto = est.drop(grandes.index)
    pct = lambda d: 100 * d["abstencoes"].sum() / d["aptos"].sum()
    taxas = est["abstencao_pct"].astype(float)
    return {
        "maiores": picos,
        "municipios_30_ou_mais": int((a >= 30).sum()),
        "exemplo": {
            "idx": int(i), "nome": mun.at[i, "nome"], "uf": uf, "pct": _r(a[i]),
            "uf_pct": _r(por_uf.at[uf, "pct"]), "uf_posicao_menor": ordem.index(uf) + 1,
            "uf_municipios": len(est),
            # Posição do município entre os do próprio estado (1 = maior taxa) e as
            # médias sem pesar o eleitorado: separam o "pico é exceção" do "o estado
            # pesa pelo eleitorado".
            "posicao_no_uf": int((taxas > a[i]).sum()) + 1,
            "uf_media_simples": _r(taxas.mean()), "uf_mediana": _r(taxas.median()),
            "grandes_n": len(grandes), "grandes_parcela_eleitorado": _r(grandes["aptos"].sum() / est["aptos"].sum(), 3),
            "grandes_pct": _r(pct(grandes)), "resto_n": len(resto), "resto_pct": _r(pct(resto)),
        },
    }


def _ufs(mun: pd.DataFrame, por_uf: pd.DataFrame) -> dict:
    """Dados de cada estado para o painel que abre ao clicar num município.

    `metade` são os maiores municípios que, juntos, somam pelo menos metade do
    eleitorado do estado; `resto` são os outros. É a conta que mostra por que um
    município pequeno com abstenção alta quase não move a taxa do estado.
    """
    ordem = list(por_uf.index)  # do estado com menor taxa para o de maior
    pct = lambda d: 100 * d["abstencoes"].sum() / d["aptos"].sum()
    saida = {}
    for uf in ordem:
        est = mun[mun["sigla_uf"] == uf].sort_values("aptos", ascending=False)
        acum = est["aptos"].cumsum() / est["aptos"].sum()
        k = int((acum < 0.5).sum()) + 1
        metade, resto = est.iloc[:k], est.iloc[k:]
        saida[uf] = {
            "regiao": est["regiao"].iloc[0],
            "pct": _r(por_uf.at[uf, "pct"]),
            "abstencoes": int(est["abstencoes"].sum()),
            "media_simples": _r(est["abstencao_pct"].astype(float).mean()),
            "posicao_menor": ordem.index(uf) + 1,
            "aptos": int(est["aptos"].sum()),
            "municipios": len(est),
            "metade": {"n": k, "pct": _r(pct(metade)), "parcela": _r(metade["aptos"].sum() / est["aptos"].sum(), 3),
                       "nomes": metade["nome"].head(3).tolist()},
            "resto": {"n": len(resto), "pct": _r(pct(resto)) if len(resto) else None},
        }
    return saida


def _espacial() -> dict:
    e = json.loads((RAIZ / "resultados" / f"espacial_{ANO}.json").read_text(encoding="utf-8"))
    vc = e["validacao_cruzada"]
    return {
        "k": e["k_vizinhos"], "permutacoes": e["permutacoes"],
        "distancia_mediana_km": _r(e["distancia_mediana_vizinho_km"], 0),
        "distancia_media_km": _r(e["distancia_media_vizinho_km"], 0),
        "moran_residuo": _r(e["moran_residuo"]["i"], 3), "p": e["moran_residuo"]["p_permutacao"],
        "maior_sorteio": _r(e["moran_residuo"]["maior_i_entre_permutacoes"], 3),
        "r2_vizinhos": _r(e["r2_residuo_explicado_pela_media_dos_vizinhos"], 3),
        "moran_sem_uf": _r(e["moran_residuo_sem_media_da_uf"]["i"], 3),
        "outra_uf_n": e["vizinhos_de_outra_uf"]["municipios_com_vizinho_de_outra_uf"],
        "outra_uf_corr": _r(e["vizinhos_de_outra_uf"]["correlacao"], 2),
        "outra_uf_corr_sem_uf": _r(e["vizinhos_de_outra_uf"]["correlacao_sem_media_da_uf"], 2),
        "rf_r2_uf": _r(vc["uf"]["random_forest"]["r2"], 3),
        "rf_r2_clusters_27": _r(vc["clusters_27"]["random_forest"]["r2"], 3),
        "rf_r2_clusters_60": _r(vc["clusters_60"]["random_forest"]["r2"], 3),
    }


def _resumo(mun: pd.DataFrame) -> dict:
    inf = json.loads((RAIZ / "resultados" / f"inferencia_{ANO}.json").read_text(encoding="utf-8"))
    modelo = json.loads((RAIZ / "resultados" / f"modelo_{ANO}.json").read_text(encoding="utf-8"))
    coef = pd.read_csv(RAIZ / "resultados" / f"coeficientes_{ANO}.csv")
    imp = pd.read_csv(RAIZ / "resultados" / f"importancia_permutacao_{ANO}.csv")

    aptos = int(mun["aptos"].sum())
    abst = int(mun["abstencoes"].sum())
    a = mun["abstencao_pct"].astype(float)
    i_min, i_max = a.idxmin(), a.idxmax()

    por_uf = (mun.groupby("sigla_uf").agg(aptos=("aptos", "sum"), abst=("abstencoes", "sum"))
              .assign(pct=lambda d: 100 * d["abst"] / d["aptos"]).sort_values("pct"))
    por_reg = (mun.groupby("regiao").agg(aptos=("aptos", "sum"), abst=("abstencoes", "sum"),
                                         mediana=("abstencao_pct", "median"),
                                         municipios=("id_municipio", "count"))
               .assign(pct=lambda d: 100 * d["abst"] / d["aptos"]))

    variaveis, regioes = [], []
    for _, l in coef.iterrows():
        if l["termo"] == "Intercept":
            continue
        base = {"termo": l["termo"], "descricao": l["descricao"],
                "coef": _r(l["coef_pp"], 3), "ic": [_r(l["ic95_inf"], 3), _r(l["ic95_sup"], 3)],
                "p": float(f"{l['p_cluster_uf']:.3g}")}
        if l["termo"].startswith("regiao_"):
            regioes.append(base)
        else:
            iqr = float(l["iqr_variavel"])
            base.update({"iqr": _r(iqr, 3), "q13": _r(l["efeito_q1_q3_pp"], 3),
                         "q13_ic": [_r(l["ic95_inf"] * iqr, 3), _r(l["ic95_sup"] * iqr, 3)]})
            variaveis.append(base)

    def met(validacao: str) -> dict:
        return {m: {"mae": _r(v["mae_pp_empilhado"], 3), "r2": _r(v["r2_empilhado"], 3)}
                for m, v in modelo["validacoes"][validacao].items()}

    q1, q3 = a.quantile([0.25, 0.75])
    return {
        "ano": ANO,
        # Comparecimento somado da fonte, não aptos - abstenções: os dois diferem em 84
        # eleitores de uma zona de Manaus (ver docs/validacao-fonte.md).
        "nacional": {"aptos": aptos, "abstencoes": abst, "comparecimento": int(mun["comparecimento"].sum()),
                     "abst_pct": _r(100 * abst / aptos, 2), "municipios": len(mun),
                     "ufs": int(mun["sigla_uf"].nunique())},
        "distribuicao": {
            "min": {"pct": _r(a[i_min]), "nome": mun.at[i_min, "nome"], "uf": mun.at[i_min, "sigla_uf"]},
            "max": {"pct": _r(a[i_max]), "nome": mun.at[i_max, "nome"], "uf": mun.at[i_max, "sigla_uf"]},
            "mediana": _r(a.median()), "q1": _r(q1), "q3": _r(q3),
        },
        "picos": _picos(mun, por_uf),
        "ufs": _ufs(mun, por_uf),
        "espacial": _espacial(),
        "ufs_maior": [{"uf": u, "pct": _r(p)} for u, p in por_uf["pct"].iloc[::-1].head(3).items()],
        "ufs_menor": [{"uf": u, "pct": _r(p)} for u, p in por_uf["pct"].head(3).items()],
        "regioes": [{"regiao": r, "pct": _r(por_reg.at[r, "pct"]), "mediana": _r(por_reg.at[r, "mediana"]),
                     "municipios": int(por_reg.at[r, "municipios"])} for r in REGIOES],
        "armadilha": {**_armadilha(), "aptos_com_filtro": aptos},
        "regressao": {
            "r2": _r(inf["r2"], 3), "r2_so_uf": _r(inf["r2_so_uf"], 3),
            "r2_so_regiao": _r(inf["r2_so_regiao"], 3), "vif_maximo": _r(inf["vif_maximo"], 2),
            "r2_residuo_uf": _r(inf["residuos"]["r2_residuo_explicado_por_uf"], 3),
            "desvio_residuo_pp": _r(inf["residuos"]["desvio_padrao_residuo_pp"], 2),
            "variaveis": variaveis, "regioes": regioes,
        },
        "modelos": {"kfold": met("kfold"), "groupkfold_uf": met("groupkfold_uf")},
        "correlacoes": {
            "log2_aptos__log2_densidade": _r(mun["log2_aptos"].astype(float).corr(
                mun["log2_densidade"].astype(float)), 3),
        },
        "importancia": [{"variavel": l["variavel"], "descricao": l["descricao"],
                         "aumento_mae": _r(l["aumento_mae_pp_medio"], 3)} for _, l in imp.iterrows()],
        "fonte": "Base dos Dados (dados do TSE e do IBGE), BigQuery",
    }


def main() -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    mun = _municipios()
    resumo = _resumo(mun)
    arm = resumo["armadilha"]
    # A soma sem filtro tem que ser a mesma que docs/validacao-fonte.md registra.
    assert arm["aptos_sem_filtro"] == 778_687_320, arm
    assert arm["aptos_com_filtro"] == 155_758_656, arm
    for nome, conteudo in (("municipios.json", _arquivo_municipios(mun)), ("resumo.json", resumo)):
        caminho = DESTINO / nome
        caminho.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[web] {caminho.relative_to(RAIZ)} ({caminho.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
