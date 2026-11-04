"""Acesso ao BigQuery com controle de custo.

Toda consulta passa por um dry run antes de executar. A estimativa e os bytes
reais ficam registrados em evidencias/consultas.jsonl. Todo job leva
maximum_bytes_billed, então o BigQuery recusa a consulta se ela passar do teto.
"""
from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

RAIZ = Path(__file__).resolve().parents[1]
PROJETO_COBRANCA = "eleitorado"
TETO_PADRAO = 100_000_000  # 100 MB por job
TETO_MAXIMO = 2_000_000_000  # 2 GB, só com motivo registrado
REGISTRO = RAIZ / "evidencias" / "consultas.jsonl"

warnings.filterwarnings("ignore", message="BigQuery Storage module not found")

_cliente: bigquery.Client | None = None


def cliente() -> bigquery.Client:
    global _cliente
    if _cliente is None:
        _cliente = bigquery.Client(project=PROJETO_COBRANCA, location="US")
    return _cliente


def estimar(sql: str) -> int:
    """Dry run: devolve os bytes que a consulta leria, sem executá-la."""
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = cliente().query(sql, job_config=cfg)
    return int(job.total_bytes_processed or 0)


def consultar(sql: str, nome: str, teto: int = TETO_PADRAO, motivo: str | None = None):
    """Estima, confere o teto, executa e registra. Devolve um DataFrame."""
    if teto > TETO_PADRAO and not motivo:
        raise ValueError(f"{nome}: teto acima de 100 MB exige um motivo registrado")
    if teto > TETO_MAXIMO:
        raise ValueError(f"{nome}: teto acima de 2 GB não é permitido")
    estimativa = estimar(sql)
    if estimativa > teto:
        raise RuntimeError(f"{nome}: estimativa de {estimativa:,} bytes passa do teto de {teto:,}")
    cfg = bigquery.QueryJobConfig(use_query_cache=False, maximum_bytes_billed=teto)
    job = cliente().query(sql, job_config=cfg)
    df = job.result().to_dataframe()
    entrada = {
        "quando": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "nome": nome,
        "bytes_estimados": estimativa,
        "bytes_processados": int(job.total_bytes_processed or 0),
        "bytes_faturados": int(job.total_bytes_billed or 0),
        "teto": teto,
        "motivo_teto": motivo,
        "linhas": len(df),
        "job_id": job.job_id,
    }
    REGISTRO.parent.mkdir(exist_ok=True)
    with REGISTRO.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    print(f"[bq] {nome}: estimados={estimativa:,} processados={entrada['bytes_processados']:,} "
          f"faturados={entrada['bytes_faturados']:,} linhas={len(df)}")
    return df
