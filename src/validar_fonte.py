"""Consultas que sustentam docs/validacao-fonte.md.

Não faz parte do pipeline principal. Grava evidencias/validacao_fonte.json.
Uso: python -m src.validar_fonte
"""
from __future__ import annotations

import json

from src.bq import RAIZ, consultar
from src.extracao import VOTACAO, VOTACAO_MUNICIPIO

CONSULTAS = {
    # Quantas linhas e quanto eleitorado cada combinação de cargo/tipo tem.
    # Mostra a repetição por cargo e as eleições que não são ordinárias.
    "grupos_cargo_tipo": f"""
SELECT ano, turno, cargo, tipo_eleicao,
  COUNT(*) AS linhas, COUNT(DISTINCT id_municipio) AS municipios,
  COUNT(DISTINCT sigla_uf) AS ufs, COUNTIF(sigla_uf = 'ZZ') AS linhas_exterior,
  SUM(aptos) AS aptos,
  COUNTIF(aptos != comparecimento + abstencoes) AS linhas_sem_conciliacao
FROM `{VOTACAO}`
WHERE ano IN (2018, 2022)
GROUP BY ALL
ORDER BY ano, turno, cargo, tipo_eleicao""",
    # Linhas de presidente, 1º turno, fora do exterior, em que aptos não fecha.
    "divergencias_presidente": f"""
SELECT ano, sigla_uf, id_municipio, zona, aptos, comparecimento, abstencoes,
  aptos - comparecimento - abstencoes AS diferenca
FROM `{VOTACAO}`
WHERE ano IN (2018, 2022) AND turno = 1 AND cargo = 'presidente'
  AND tipo_eleicao = 'eleicao ordinaria' AND sigla_uf != 'ZZ'
  AND aptos != comparecimento + abstencoes""",
    # Códigos do perfil do eleitorado.
    "dicionario_perfil": """
SELECT nome_coluna, chave, valor
FROM `basedosdados.br_tse_eleicoes.dicionario`
WHERE id_tabela = 'perfil_eleitorado_municipio_zona'
ORDER BY nome_coluna, chave""",
    # Aptos de presidente contra aptos de governador no mesmo município.
    "aptos_presidente_vs_governador": f"""
WITH m AS (
  SELECT ano, id_municipio,
    SUM(IF(cargo = 'presidente', aptos, 0)) AS presidente,
    SUM(IF(cargo = 'governador', aptos, 0)) AS governador
  FROM `{VOTACAO_MUNICIPIO}`
  WHERE ano IN (2018, 2022) AND turno = 1 AND tipo_eleicao = 'eleicao ordinaria'
    AND sigla_uf != 'ZZ' AND cargo IN ('presidente', 'governador')
  GROUP BY ano, id_municipio
)
SELECT ano, SUM(presidente - governador) AS diferenca_total,
  COUNTIF(presidente != governador) AS municipios_com_diferenca,
  COUNTIF(presidente < governador) AS municipios_presidente_menor
FROM m GROUP BY ano ORDER BY ano""",
}


def main() -> None:
    evidencia = {}
    for nome, sql in CONSULTAS.items():
        df = consultar(sql, f"validacao_{nome}")
        evidencia[nome] = json.loads(df.to_json(orient="records", force_ascii=False))
    destino = RAIZ / "evidencias" / "validacao_fonte.json"
    destino.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[validacao] gravado em {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
