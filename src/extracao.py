"""Extração do BigQuery (Base dos Dados) para Parquet local.

Cada consulta passa pelo dry run e pelo teto de bytes de src/bq.py.
Saída: data/brutos/*.parquet. Nada aqui é lido pelo app ou pela análise
direto do BigQuery; depois desta etapa tudo roda em cima dos arquivos.

Uso: python -m src.extracao [--anos 2022 2018]
"""
from __future__ import annotations

import argparse

from src.bq import RAIZ, consultar

BRUTOS = RAIZ / "data" / "brutos"

VOTACAO = "basedosdados.br_tse_eleicoes.detalhes_votacao_municipio_zona"
VOTACAO_MUNICIPIO = "basedosdados.br_tse_eleicoes.detalhes_votacao_municipio"
PERFIL = "basedosdados.br_tse_eleicoes.perfil_eleitorado_municipio_zona"
PIB = "basedosdados.br_ibge_pib.municipio"
POPULACAO = "basedosdados.br_ibge_populacao.municipio"
CENSO_2022 = "basedosdados.br_ibge_censo_2022.municipio"
DIRETORIO = "basedosdados.br_bd_diretorios_brasil.municipio"

# O perfil do eleitorado é uma tabela larga (cerca de 3 GB). Mesmo lendo só
# id_municipio e eleitores, uma partição anual passa de 100 MB (dry run de
# 108.729.810 bytes em 2022). Com as três dimensões usadas aqui a leitura fica
# perto de 160 MB. Por isso este job tem teto de 250 MB, registrado no README.
TETO_PERFIL = 250_000_000
MOTIVO_PERFIL = (
    "perfil_eleitorado_municipio_zona: a menor leitura possível de um ano "
    "(id_municipio, grupo_idade, instrucao, genero, eleitores) passa de 100 MB"
)


def sql_votacao(ano: int) -> str:
    # Cargo e tipo de eleição fixados ANTES de qualquer soma: a fonte repete
    # aptos/comparecimento para cada cargo e inclui eleições suplementares.
    # sigla_uf = 'ZZ' é o voto no exterior, que não pertence a município.
    return f"""
SELECT ano, turno, cargo, tipo_eleicao, sigla_uf, id_municipio, id_municipio_tse,
       zona, aptos, comparecimento, abstencoes
FROM `{VOTACAO}`
WHERE ano = {ano}
  AND turno = 1
  AND cargo = 'presidente'
  AND tipo_eleicao = 'eleicao ordinaria'
  AND sigla_uf != 'ZZ'
"""


def sql_votacao_municipio(ano: int) -> str:
    # Tabela municipal da própria Base dos Dados. Serve só para conferir a
    # nossa soma de zonas (teste de conciliação); não entra no modelo.
    return f"""
SELECT ano, sigla_uf, id_municipio, aptos, comparecimento, abstencoes
FROM `{VOTACAO_MUNICIPIO}`
WHERE ano = {ano}
  AND turno = 1
  AND cargo = 'presidente'
  AND tipo_eleicao = 'eleicao ordinaria'
  AND sigla_uf != 'ZZ'
"""


def sql_perfil(ano: int) -> str:
    # Códigos conferidos na tabela br_tse_eleicoes.dicionario:
    # grupo_idade: '1600' = 16 anos, '1700' = 17 anos, '7074'...'9999' = 70 anos ou mais,
    #              '-3' = inválido
    # instrucao: '0' não informado, '1' analfabeto, '2' lê e escreve,
    #            '3' fundamental incompleto, '4' fundamental completo,
    #            '5' médio incompleto, '6' médio completo,
    #            '7' superior incompleto, '8' superior completo
    # genero: '0' não informado, '2' masculino, '4' feminino
    instrucao = ",\n  ".join(
        f"SUM(IF(instrucao = '{c}', eleitores, 0)) AS instrucao_{c}" for c in range(9)
    )
    return f"""
SELECT
  id_municipio,
  SUM(eleitores) AS eleitores_perfil,
  SUM(IF(grupo_idade IN ('1600', '1700'), eleitores, 0)) AS idade_16_17,
  SUM(IF(grupo_idade IN ('7074', '7579', '8084', '8589', '9094', '9599', '9999'),
         eleitores, 0)) AS idade_70_mais,
  SUM(IF(grupo_idade = '-3', eleitores, 0)) AS idade_invalida,
  {instrucao},
  SUM(IF(genero = '4', eleitores, 0)) AS genero_feminino,
  SUM(IF(genero = '2', eleitores, 0)) AS genero_masculino,
  SUM(IF(genero = '0', eleitores, 0)) AS genero_nao_informado
FROM `{PERFIL}`
WHERE ano = {ano}
GROUP BY id_municipio
"""


def sql_pib_populacao(ano: int) -> str:
    return f"""
SELECT p.id_municipio, p.ano, p.pib, pop.populacao
FROM `{PIB}` AS p
LEFT JOIN `{POPULACAO}` AS pop
  ON pop.id_municipio = p.id_municipio AND pop.ano = p.ano
WHERE p.ano = {ano}
"""


def sql_censo_2022() -> str:
    return f"""
SELECT id_municipio, sigla_uf, populacao, area
FROM `{CENSO_2022}`
"""


def sql_diretorio() -> str:
    # Nome, região e centroide (longitude/latitude) de cada município, para o
    # app. O centroide é convertido em dois números para não depender de
    # biblioteca de geometria.
    return f"""
SELECT id_municipio, nome, sigla_uf, nome_regiao, capital_uf,
       ST_X(centroide) AS longitude, ST_Y(centroide) AS latitude
FROM `{DIRETORIO}`
"""


def extrair(anos: list[int]) -> None:
    BRUTOS.mkdir(parents=True, exist_ok=True)
    for ano in anos:
        consultar(sql_votacao(ano), f"votacao_zona_{ano}").to_parquet(
            BRUTOS / f"votacao_zona_{ano}.parquet", index=False)
        consultar(sql_votacao_municipio(ano), f"votacao_municipio_{ano}").to_parquet(
            BRUTOS / f"votacao_municipio_{ano}.parquet", index=False)
        consultar(sql_perfil(ano), f"perfil_eleitorado_{ano}", teto=TETO_PERFIL,
                  motivo=MOTIVO_PERFIL).to_parquet(
            BRUTOS / f"perfil_eleitorado_{ano}.parquet", index=False)
        consultar(sql_pib_populacao(ano), f"pib_populacao_{ano}").to_parquet(
            BRUTOS / f"pib_populacao_{ano}.parquet", index=False)
    consultar(sql_censo_2022(), "censo_2022_municipio").to_parquet(
        BRUTOS / "censo_2022_municipio.parquet", index=False)
    consultar(sql_diretorio(), "diretorio_municipios").to_parquet(
        BRUTOS / "diretorio_municipios.parquet", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anos", type=int, nargs="+", default=[2022, 2018])
    args = parser.parse_args()
    extrair(args.anos)


if __name__ == "__main__":
    main()
