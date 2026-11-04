"""Roda o projeto inteiro em ordem: extração, variáveis, testes, análise, modelo e
dependência espacial.

Uso:
  python -m src.pipeline                 # do zero, consultando o BigQuery
  python -m src.pipeline --sem-extracao  # reaproveita data/brutos/
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from src import analise, espacial, features, modelo
from src.bq import REGISTRO


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sem-extracao", action="store_true",
                        help="não consulta o BigQuery; usa os Parquet de data/brutos/")
    parser.add_argument("--anos", type=int, nargs="+", default=[2022, 2018])
    args = parser.parse_args()

    linhas_antes = 0
    if REGISTRO.exists():
        linhas_antes = len(REGISTRO.read_text(encoding="utf-8").splitlines())

    if not args.sem_extracao:
        from src import extracao  # importa o cliente do BigQuery só se for usar
        print("== 1/6 extração (BigQuery) ==")
        extracao.extrair(args.anos)
    print("== 2/6 variáveis por município ==")
    features.gerar(args.anos)
    print("== 3/6 testes de dados ==")
    codigo = subprocess.call([sys.executable, "-m", "pytest", "-q"])
    if codigo != 0:
        sys.exit("testes de dados falharam; análise interrompida")
    print("== 4/6 regressão (statsmodels) ==")
    for ano in args.anos:
        analise.analisar(ano)
    print("== 5/6 modelo (scikit-learn) ==")
    for ano in args.anos:
        modelo.rodar(ano)
    print("== 6/6 dependência espacial ==")
    for ano in args.anos:
        espacial.analisar(ano)

    if not args.sem_extracao:
        novas = REGISTRO.read_text(encoding="utf-8").splitlines()[linhas_antes:]
        jobs = [json.loads(l) for l in novas]
        processados = sum(j["bytes_processados"] for j in jobs)
        faturados = sum(j["bytes_faturados"] for j in jobs)
        print(f"BigQuery nesta execução: {len(jobs)} jobs, {processados:,} bytes processados, "
              f"{faturados:,} bytes faturados")


if __name__ == "__main__":
    main()
