import os
from datetime import datetime, timedelta

from database import SessionLocal
import models


def cleanup_old_logs(
    retention_days_operacional: int | None = None,
    retention_days_seguranca: int | None = None,
):
    retention_days_operacional = retention_days_operacional or int(
        os.getenv("LOG_RETENTION_DAYS_OPERACIONAL", "365")
    )
    retention_days_seguranca = retention_days_seguranca or int(
        os.getenv("LOG_RETENTION_DAYS_SEGURANCA", "730")
    )

    cutoff_operacional = datetime.utcnow() - timedelta(days=retention_days_operacional)
    cutoff_seguranca = datetime.utcnow() - timedelta(days=retention_days_seguranca)

    db = SessionLocal()
    try:
        deleted_operacional = (
            db.query(models.Log)
            .filter(
                models.Log.tipo == "operacional",
                models.Log.data_hora < cutoff_operacional,
            )
            .delete(synchronize_session=False)
        )
        deleted_seguranca = (
            db.query(models.Log)
            .filter(
                models.Log.tipo == "seguranca",
                models.Log.data_hora < cutoff_seguranca,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        deleted = deleted_operacional + deleted_seguranca
        print(
            f"Limpeza concluida: {deleted} logs removidos "
            f"(operacional={retention_days_operacional} dias, "
            f"seguranca={retention_days_seguranca} dias)."
        )
        return {
            "deleted_total": deleted,
            "deleted_operacional": deleted_operacional,
            "deleted_seguranca": deleted_seguranca,
            "retention_days_operacional": retention_days_operacional,
            "retention_days_seguranca": retention_days_seguranca,
        }
    finally:
        db.close()

def estimate_old_logs(
    retention_days_operacional: int | None = None,
    retention_days_seguranca: int | None = None,
):
    retention_days_operacional = retention_days_operacional or int(
        os.getenv("LOG_RETENTION_DAYS_OPERACIONAL", "365")
    )
    retention_days_seguranca = retention_days_seguranca or int(
        os.getenv("LOG_RETENTION_DAYS_SEGURANCA", "730")
    )

    cutoff_operacional = datetime.utcnow() - timedelta(days=retention_days_operacional)
    cutoff_seguranca = datetime.utcnow() - timedelta(days=retention_days_seguranca)

    db = SessionLocal()
    try:
        estimate_operacional = (
            db.query(models.Log)
            .filter(
                models.Log.tipo == "operacional",
                models.Log.data_hora < cutoff_operacional,
            )
            .count()
        )
        estimate_seguranca = (
            db.query(models.Log)
            .filter(
                models.Log.tipo == "seguranca",
                models.Log.data_hora < cutoff_seguranca,
            )
            .count()
        )
        return {
            "estimate_total": estimate_operacional + estimate_seguranca,
            "estimate_operacional": estimate_operacional,
            "estimate_seguranca": estimate_seguranca,
            "retention_days_operacional": retention_days_operacional,
            "retention_days_seguranca": retention_days_seguranca,
        }
    finally:
        db.close()


if __name__ == "__main__":
    cleanup_old_logs()
