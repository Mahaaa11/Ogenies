from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from pathlib import Path

from .db import MySQLConfig
from .local_event_store import LocalEventStoreConfig, store_sendgrid_events_locally
from .repository import MySQLStores


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _mysql_cfg_from_env() -> MySQLConfig:
    return MySQLConfig(
        host=_env("LNC_MYSQL_HOST", "localhost"),
        port=int(_env("LNC_MYSQL_PORT", "3306")),
        user=_env("LNC_MYSQL_USER", "root"),
        password=_env("LNC_MYSQL_PASSWORD", ""),
        database=_env("LNC_MYSQL_DATABASE", ""),
        prospects_table=_env("LNC_MYSQL_PROSPECTS_TABLE", "prospects"),
        events_table=_env("LNC_MYSQL_EVENTS_TABLE", "email_events"),
    )

def _local_cfg_from_env() -> LocalEventStoreConfig:
    raw = _env("LNC_LOCAL_RAW_JSONL", "data/sendgrid_events.jsonl")
    normalized = _env("LNC_LOCAL_EVENTS_CSV", "data/events_webhook.csv")
    prospects = _env("LNC_LOCAL_PROSPECTS_CSV", "data/prospects.csv")
    return LocalEventStoreConfig(
        raw_jsonl_path=Path(raw),
        normalized_events_csv_path=Path(normalized),
        prospects_csv_path=Path(prospects),
    )


app = FastAPI(title="L&C Emailing Agent Webhooks")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhooks/sendgrid/events")
async def sendgrid_events(request: Request) -> dict[str, Any]:
    """
    Twilio SendGrid Event Webhook endpoint.

    Expected payload: a JSON array of event objects.
    """
    payload = await request.json()
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="expected a JSON array")

    store_mode = _env("LNC_EVENT_STORE", "mysql").lower()
    if store_mode == "local":
        inserted = store_sendgrid_events_locally(_local_cfg_from_env(), payload)
        return {"ok": True, "inserted": inserted, "store": "local"}

    stores = MySQLStores(_mysql_cfg_from_env())
    try:
        inserted = stores.insert_sendgrid_events(payload)
        return {"ok": True, "inserted": inserted, "store": "mysql"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"mysql_unavailable: {e}") from e

