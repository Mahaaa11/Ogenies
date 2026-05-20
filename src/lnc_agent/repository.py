from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .db import MySQLConfig, _as_int, connect
from .models import Event, Prospect


class ProspectStore(Protocol):
    def list_prospects(self, limit: int | None = None) -> list[Prospect]: ...


class EventStore(Protocol):
    def list_events(self, limit: int | None = None) -> list[Event]: ...
    def insert_sendgrid_events(self, events: list[dict[str, Any]]) -> int: ...
    def list_sendgrid_raw_events(self, limit: int | None = None) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class MySQLStores:
    cfg: MySQLConfig

    def list_prospects(self, limit: int | None = None) -> list[Prospect]:
        sql = f"""
            SELECT
              id,
              COALESCE(first_name, '') AS first_name,
              COALESCE(last_name, '') AS last_name,
              email,
              COALESCE(company, '') AS company,
              COALESCE(role, '') AS role,
              COALESCE(industry, '') AS industry,
              COALESCE(provider, 'SendGrid') AS provider,
              COALESCE(status, 'active') AS status,
              COALESCE(last_contacted_day, 999) AS last_contacted_day
            FROM {self.cfg.prospects_table}
        """
        if limit is not None:
            sql += " LIMIT %s"

        with connect(self.cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,) if limit is not None else None)
                rows = cur.fetchall()

        prospects: list[Prospect] = []
        for row in rows:
            prospects.append(
                Prospect(
                    id=str(row["id"]),
                    first_name=str(row.get("first_name") or ""),
                    last_name=str(row.get("last_name") or ""),
                    email=str(row.get("email") or ""),
                    company=str(row.get("company") or ""),
                    role=str(row.get("role") or ""),
                    industry=str(row.get("industry") or ""),
                    provider=str(row.get("provider") or "SendGrid"),
                    status=str(row.get("status") or "active"),
                    last_contacted_day=_as_int(row.get("last_contacted_day"), 999),
                )
            )
        return prospects

    def list_events(self, limit: int | None = None) -> list[Event]:
        sql = f"""
            SELECT
              prospect_id,
              event_type,
              COALESCE(campaign_step, '') AS campaign_step,
              COALESCE(day, 0) AS day,
              COALESCE(hour, 0) AS hour
            FROM {self.cfg.events_table}
            ORDER BY day DESC, hour DESC
        """
        if limit is not None:
            sql += " LIMIT %s"

        with connect(self.cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,) if limit is not None else None)
                rows = cur.fetchall()

        return [
            Event(
                prospect_id=str(r.get("prospect_id") or ""),
                event_type=str(r.get("event_type") or ""),
                campaign_step=str(r.get("campaign_step") or ""),
                day=_as_int(r.get("day"), 0),
                hour=_as_int(r.get("hour"), 0),
            )
            for r in rows
        ]

    def insert_sendgrid_events(self, events: list[dict[str, Any]]) -> int:
        """
        Stores raw SendGrid events.

        Assumes an existing table with (at minimum) these columns:
        - sg_event_id (string, unique recommended)
        - email (string)
        - event_type (string)
        - ts (int)
        - payload_json (json/text)

        Also supports optional:
        - prospect_id (string)
        - campaign_step (string)
        - day (int)
        - hour (int)
        """
        if not events:
            return 0

        sql = f"""
            INSERT INTO {self.cfg.events_table}
              (sg_event_id, email, event_type, ts, payload_json, prospect_id, campaign_step, day, hour)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              ts = VALUES(ts),
              payload_json = VALUES(payload_json)
        """

        inserted = 0
        with connect(self.cfg) as conn:
            with conn.cursor() as cur:
                for ev in events:
                    sg_event_id = str(ev.get("sg_event_id") or ev.get("event_id") or "")
                    email = str(ev.get("email") or "")
                    event_type = str(ev.get("event") or ev.get("event_type") or "")
                    ts = _as_int(ev.get("timestamp") or ev.get("ts"), 0)

                    # Best-effort mapping. Your DB may already map email -> prospect_id.
                    prospect_id = str(ev.get("prospect_id") or "")

                    # Optional campaign fields (if you add them in SendGrid custom args).
                    campaign_step = str(ev.get("campaign_step") or ev.get("campaign") or "")
                    day = _as_int(ev.get("day"), 0)
                    hour = _as_int(ev.get("hour"), 0)

                    payload_json = _json_dumps(ev)
                    cur.execute(
                        sql,
                        (
                            sg_event_id,
                            email,
                            event_type,
                            ts,
                            payload_json,
                            prospect_id,
                            campaign_step,
                            day,
                            hour,
                        ),
                    )
                    inserted += 1
        return inserted

    def list_sendgrid_raw_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        """
        Returns the stored raw payloads (decoded from payload_json).
        Requires payload_json column in events_table.
        """
        sql = f"SELECT payload_json FROM {self.cfg.events_table} ORDER BY ts ASC"
        if limit is not None:
            sql += " LIMIT %s"
        with connect(self.cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (limit,) if limit is not None else None)
                rows = cur.fetchall()
        out: list[dict[str, Any]] = []
        import json

        for r in rows:
            try:
                payload = r.get("payload_json")
                if isinstance(payload, (bytes, bytearray)):
                    payload = payload.decode("utf-8", errors="replace")
                if isinstance(payload, str) and payload.strip():
                    v = json.loads(payload)
                    if isinstance(v, dict):
                        out.append(v)
            except Exception:
                continue
        return out


def _json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

