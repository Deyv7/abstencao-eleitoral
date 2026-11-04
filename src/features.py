"""Transforma os Parquet brutos em uma tabela com uma linha por município.

Entrada: data/brutos/*.parquet (gerados por src.extracao).
Saída: data/processados/municipios_{ano}.parquet.

Uso: python -m src.features [--anos 2022 2018]
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.bq import RAIZ

BRUTOS = RAIZ / "data" / "brutos"
PROCESSADOS = RAIZ / "data" / "processados"

# Variáveis explicativas usadas na regressão e no modelo de ML.
# Todas as proporções estão em pontos percentuais (0 a 100).
VARIAVEIS = [
    "pct_16_17",
    "pct_70_mais",
    "pct_feminino",
    "pct_baixa_escolaridade",
    "pct_superior",
    "log2_aptos",
    "log2_pib_per_capita",
    "razao_aptos_populacao",
    "log2_densidade",
]
REGIOES = ["Centro-Oeste", "Nordeste", "Norte", "Sudeste", "Sul"]
ALVO = "abstencao_pct"


def agregar_votacao(zonas: pd.DataFrame) -> pd.DataFrame:
    """Soma as zonas de cada município.

    A extração já fixou cargo = presidente, turno 1 e eleição ordinária, então
    cada zona aparece uma vez. Isso é conferido aqui antes de somar.
    """
    assert zonas["cargo"].nunique() == 1 and zonas["tipo_eleicao"].nunique() == 1
    assert zonas["turno"].nunique() == 1
    duplicadas = zonas.duplicated(["id_municipio", "zona"]).sum()
    if duplicadas:
        raise ValueError(f"{duplicadas} pares município/zona repetidos na votação")
    return (
        zonas.groupby(["ano", "sigla_uf", "id_municipio"], as_index=False)
        .agg(
            n_zonas=("zona", "nunique"),
            aptos=("aptos", "sum"),
            comparecimento=("comparecimento", "sum"),
            abstencoes=("abstencoes", "sum"),
        )
    )


def montar(ano: int) -> pd.DataFrame:
    votos = agregar_votacao(pd.read_parquet(BRUTOS / f"votacao_zona_{ano}.parquet"))
    perfil = pd.read_parquet(BRUTOS / f"perfil_eleitorado_{ano}.parquet")
    perfil = perfil[perfil["id_municipio"].notna()]  # linha sem município = exterior
    pib = pd.read_parquet(BRUTOS / f"pib_populacao_{ano}.parquet")
    censo = pd.read_parquet(BRUTOS / "censo_2022_municipio.parquet")
    diretorio = pd.read_parquet(BRUTOS / "diretorio_municipios.parquet")

    df = (
        votos.merge(perfil, on="id_municipio", how="left", validate="1:1")
        .merge(pib[["id_municipio", "pib", "populacao"]], on="id_municipio", how="left",
               validate="1:1")
        .merge(censo[["id_municipio", "area"]].rename(columns={"area": "area_km2"}),
               on="id_municipio", how="left", validate="1:1")
        .merge(diretorio[["id_municipio", "nome", "nome_regiao", "capital_uf",
                          "longitude", "latitude"]],
               on="id_municipio", how="left", validate="1:1")
    )
    if ano == 2022:
        # Para 2022 a população vem do Censo 2022, a contagem mais próxima da eleição.
        censo_pop = censo.set_index("id_municipio")["populacao"]
        df["populacao"] = df["id_municipio"].map(censo_pop)

    total = df["eleitores_perfil"]
    df["taxa_abstencao"] = df["abstencoes"] / df["aptos"]
    df[ALVO] = 100 * df["taxa_abstencao"]
    df["pct_16_17"] = 100 * df["idade_16_17"] / total
    df["pct_70_mais"] = 100 * df["idade_70_mais"] / total
    df["pct_feminino"] = 100 * df["genero_feminino"] / total
    df["pct_baixa_escolaridade"] = 100 * (df["instrucao_1"] + df["instrucao_2"]) / total
    df["pct_superior"] = 100 * df["instrucao_8"] / total
    df["log2_aptos"] = np.log2(df["aptos"])
    df["pib_per_capita"] = df["pib"] / df["populacao"]
    df["log2_pib_per_capita"] = np.log2(df["pib_per_capita"])
    df["razao_aptos_populacao"] = df["aptos"] / df["populacao"]
    df["densidade"] = df["populacao"] / df["area_km2"]
    df["log2_densidade"] = np.log2(df["densidade"])
    df["capital_uf"] = df["capital_uf"].fillna(0).astype(int)
    df["regiao"] = df["nome_regiao"]

    colunas = (
        ["ano", "id_municipio", "nome", "sigla_uf", "regiao", "capital_uf", "longitude",
         "latitude", "n_zonas", "aptos", "comparecimento", "abstencoes", "taxa_abstencao",
         ALVO, "eleitores_perfil", "pib", "populacao", "area_km2", "pib_per_capita",
         "densidade"]
        + VARIAVEIS
    )
    return df[colunas].sort_values("id_municipio").reset_index(drop=True)


def gerar(anos: list[int]) -> None:
    PROCESSADOS.mkdir(parents=True, exist_ok=True)
    for ano in anos:
        df = montar(ano)
        df.to_parquet(PROCESSADOS / f"municipios_{ano}.parquet", index=False)
        print(f"[features] {ano}: {len(df)} municípios -> municipios_{ano}.parquet")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anos", type=int, nargs="+", default=[2022, 2018])
    gerar(parser.parse_args().anos)


if __name__ == "__main__":
    main()
