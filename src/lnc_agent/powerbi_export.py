from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import read_prospects
from .sendgrid_kpis import load_sendgrid_raw_events


@dataclass(frozen=True)
class PowerBIExportConfig:
    prospects_csv: Path
    recommendations_csv: Path
    agent_report_csv: Path
    sendgrid_events_jsonl: Path
    out_dir: Path


def export_powerbi_dataset(cfg: PowerBIExportConfig) -> None:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Dimensions
    _copy_csv(cfg.prospects_csv, cfg.out_dir / "dim_prospects.csv")
    _copy_csv(cfg.recommendations_csv, cfg.out_dir / "fact_recommendations.csv")
    _copy_csv(cfg.agent_report_csv, cfg.out_dir / "fact_agent_tracking.csv")

    # 2) SendGrid raw -> normalized fact table
    raw = load_sendgrid_raw_events(cfg.sendgrid_events_jsonl)
    events = [_norm_sendgrid(e) for e in raw]
    _write_csv(cfg.out_dir / "fact_sendgrid_events.csv", events)

    # 3) Daily aggregates for trending
    daily = _daily_kpis(events)
    _write_csv(cfg.out_dir / "kpi_daily.csv", daily)


def _copy_csv(src: Path, dst: Path) -> None:
    if not src.exists():
        dst.write_text("", encoding="utf-8")
        return
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _norm_sendgrid(ev: dict[str, Any]) -> dict[str, Any]:
    email = str(ev.get("email") or "").strip().lower()
    event = str(ev.get("event") or ev.get("event_type") or "").strip().lower()
    ts = _as_int(ev.get("timestamp") or ev.get("ts"), 0)
    dt = _dt(ts)
    date = dt.date().isoformat() if dt else ""
    hour = dt.hour if dt else ""

    msg_id = str(ev.get("sg_message_id") or ev.get("smtp-id") or ev.get("message_id") or "").strip()
    template_id = str(ev.get("sg_template_id") or ev.get("template_id") or "").strip()
    url = str(ev.get("url") or "").strip()
    useragent = str(ev.get("useragent") or ev.get("user_agent") or "").strip()
    ip = str(ev.get("ip") or "").strip()

    reason = str(ev.get("reason") or "").strip()
    response = str(ev.get("response") or "").strip()

    domain = email.split("@", 1)[1] if "@" in email else ""
    provider = _provider_from_domain(domain)

    variant = ""
    ca = ev.get("custom_args") or ev.get("unique_args") or {}
    if isinstance(ca, dict):
        v = ca.get("variant")
        if isinstance(v, str) and v.strip():
            variant = v.strip().upper()
    if not variant and url:
        if "v=A" in url or "v=a" in url:
            variant = "A"
        elif "v=B" in url or "v=b" in url:
            variant = "B"

    return {
        "email": email,
        "domain": domain,
        "provider": provider,
        "event": event,
        "timestamp": ts,
        "date": date,
        "hour": hour,
        "sg_message_id": msg_id,
        "template_id": template_id,
        "variant": variant,
        "url": url,
        "useragent": useragent,
        "ip": ip,
        "reason": reason,
        "response": response,
        # Keep raw JSON for debugging (Power BI can ignore it)
        "raw_json": json.dumps(ev, ensure_ascii=False, separators=(",", ":")),
    }


def _daily_kpis(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, int]] = {}
    for e in events:
        d = str(e.get("date") or "")
        if not d:
            continue
        m = by_date.setdefault(
            d,
            {
                "processed": 0,
                "delivered": 0,
                "open": 0,
                "click": 0,
                "bounce": 0,
                "dropped": 0,
                "unsubscribe": 0,
                "spamreport": 0,
            },
        )
        ev = str(e.get("event") or "")
        if ev in m:
            m[ev] += 1
        elif ev in ("sent",):
            m["processed"] += 1
        elif ev in ("spam",):
            m["spamreport"] += 1

    out: list[dict[str, Any]] = []
    for d in sorted(by_date.keys()):
        m = by_date[d]
        delivered = m["delivered"]
        open_unique = m["open"]
        click_unique = m["click"]
        out.append(
            {
                "date": d,
                "processed": m["processed"],
                "delivered": delivered,
                "opens": m["open"],
                "clicks": m["click"],
                "bounces": m["bounce"],
                "dropped": m["dropped"],
                "unsubscribes": m["unsubscribe"],
                "spamreports": m["spamreport"],
                "open_rate_pct": round((open_unique / delivered) * 100, 2) if delivered else 0.0,
                "ctr_unique_pct": round((click_unique / delivered) * 100, 2) if delivered else 0.0,
                "ctor_unique_pct": round((click_unique / open_unique) * 100, 2) if open_unique else 0.0,
            }
        )
    return out


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _dt(ts: int) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _provider_from_domain(d: str) -> str:
    d = (d or "").lower()
    if d.endswith("gmail.com") or d.endswith("googlemail.com"):
        return "Gmail"
    if d.endswith("outlook.com") or d.endswith("hotmail.com") or d.endswith("live.com") or d.endswith("msn.com"):
        return "Outlook"
    if d.endswith("yahoo.com") or d.endswith("yahoo.fr"):
        return "Yahoo"
    return d or "unknown"

