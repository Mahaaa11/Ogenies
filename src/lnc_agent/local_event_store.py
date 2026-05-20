from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalEventStoreConfig:
    raw_jsonl_path: Path
    normalized_events_csv_path: Path
    prospects_csv_path: Path


def store_sendgrid_events_locally(
    cfg: LocalEventStoreConfig,
    events: list[dict[str, Any]],
    *,
    write_raw_jsonl: bool = True,
    dedupe_against_existing_raw: bool = True,
) -> int:
    """
    Stores SendGrid events locally:
    - append raw payloads to JSONL (one JSON per line)
    - append normalized events to a CSV compatible with this project (`read_events`)

    Normalized CSV columns:
      prospect_id,event_type,campaign_step,day,hour,weekday,ts,sg_event_id,url
    """
    if not events:
        return 0

    cfg.raw_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.normalized_events_csv_path.parent.mkdir(parents=True, exist_ok=True)

    email_to_prospect_id = _load_email_map(cfg.prospects_csv_path)

    # Ensure normalized CSV schema is upgraded when appending.
    _ensure_columns(
        cfg.normalized_events_csv_path,
        required=[
            "prospect_id",
            "event_type",
            "campaign_step",
            "day",
            "hour",
            "weekday",
            "ts",
            "sg_event_id",
            "url",
        ],
        defaults={"weekday": "-1", "ts": "0", "sg_event_id": "", "url": ""},
    )

    # Deduplicate incoming events (webhook retries + historical duplicates).
    # NOTE: during rebuilds we may disable dedupe-against-existing so we can regenerate
    # normalized CSV from an existing JSONL without dropping everything as "already seen".
    use_existing = bool(write_raw_jsonl and dedupe_against_existing_raw)
    seen_raw_ids = _load_seen_sg_event_ids(cfg.raw_jsonl_path) if use_existing else set()
    unique_events: list[dict[str, Any]] = []
    seen_fallback: set[tuple[str, str, int, str, str]] = _load_seen_fallback_keys(cfg.raw_jsonl_path) if use_existing else set()
    for ev in events:
        sg_event_id = _sg_event_id(ev)
        if sg_event_id and sg_event_id in seen_raw_ids:
            continue

        fb = _fallback_key(ev)
        if not sg_event_id and fb in seen_fallback:
            continue
        seen_fallback.add(fb)

        if sg_event_id:
            seen_raw_ids.add(sg_event_id)
        unique_events.append(ev)

    if not unique_events:
        return 0

    # Write raw JSONL (unique only)
    if write_raw_jsonl:
        with cfg.raw_jsonl_path.open("a", encoding="utf-8") as f:
            for ev in unique_events:
                f.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")

    # Append normalized events CSV
    rows: list[dict[str, Any]] = []
    # Also dedupe normalized rows within this ingestion call.
    # (We rely primarily on sg_event_id; fallback key prevents repeats in the same payload batch.)
    norm_seen: set[str] = set()
    for ev in unique_events:
        email = str(ev.get("email") or "").strip().lower()
        prospect_id = str(ev.get("prospect_id") or "") or email_to_prospect_id.get(email) or ""
        event_type = str(ev.get("event") or ev.get("event_type") or "").strip().lower()

        ts = ev.get("timestamp") or ev.get("ts") or 0
        try:
            ts_int = int(ts)
        except Exception:
            ts_int = 0
        hour = _hour_from_ts(ts_int)
        weekday = _weekday_from_ts(ts_int)

        campaign_step = str(ev.get("campaign_step") or ev.get("campaign") or "").strip()
        sg_event_id = _sg_event_id(ev)
        url = str(ev.get("url") or "").strip()

        # For local dev, keep `day` simple/stable.
        day = 0

        if not prospect_id or not event_type:
            continue

        key = sg_event_id
        if not key:
            key = f"{email}|{event_type}|{ts_int}|{url}"
        if key in norm_seen:
            continue
        norm_seen.add(key)

        rows.append(
            {
                "prospect_id": prospect_id,
                "event_type": event_type,
                "campaign_step": campaign_step or "webhook",
                "day": day,
                "hour": hour,
                "weekday": weekday,
                "ts": ts_int,
                "sg_event_id": sg_event_id,
                "url": url,
            }
        )

    if not rows:
        return 0

    fieldnames = [
        "prospect_id",
        "event_type",
        "campaign_step",
        "day",
        "hour",
        "weekday",
        "ts",
        "sg_event_id",
        "url",
    ]
    _append_csv(cfg.normalized_events_csv_path, rows, fieldnames=fieldnames)
    return len(rows)


def _load_email_map(prospects_csv_path: Path) -> dict[str, str]:
    if not prospects_csv_path.exists():
        return {}
    with prospects_csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        mapping: dict[str, str] = {}
        for row in reader:
            pid = str(row.get("id") or "").strip()
            email = str(row.get("email") or "").strip().lower()
            if pid and email:
                mapping[email] = pid
        return mapping


def _hour_from_ts(ts: Any) -> int:
    try:
        ts_int = int(ts)
        dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
        return int(dt.hour)
    except Exception:
        return 9


def _weekday_from_ts(ts: Any) -> int:
    try:
        ts_int = int(ts)
        dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
        return int(dt.weekday())  # 0=Mon..6=Sun
    except Exception:
        return -1


def _sg_event_id(ev: dict[str, Any]) -> str:
    # SendGrid uses sg_event_id (preferred); keep a few fallbacks just in case.
    for k in ("sg_event_id", "event_id", "sg_eventid"):
        v = ev.get(k)
        if v:
            s = str(v).strip()
            if s:
                return s
    return ""


def _fallback_key(ev: dict[str, Any]) -> tuple[str, str, int, str, str]:
    em = str(ev.get("email") or "").strip().lower()
    et = str(ev.get("event") or ev.get("event_type") or "").strip().lower()
    tsv = ev.get("timestamp") or ev.get("ts") or 0
    try:
        ts_int = int(tsv)
    except Exception:
        ts_int = 0
    sg_msg_id = str(ev.get("sg_message_id") or ev.get("message_id") or "").strip()
    url = str(ev.get("url") or "").strip()
    return (em, et, ts_int, sg_msg_id, url)


def _load_seen_sg_event_ids(raw_jsonl_path: Path) -> set[str]:
    if not raw_jsonl_path.exists():
        return set()
    seen: set[str] = set()
    try:
        with raw_jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                sid = _sg_event_id(ev) if isinstance(ev, dict) else ""
                if sid:
                    seen.add(sid)
    except Exception:
        return set()
    return seen


def _load_seen_fallback_keys(raw_jsonl_path: Path) -> set[tuple[str, str, int, str, str]]:
    if not raw_jsonl_path.exists():
        return set()
    seen: set[tuple[str, str, int, str, str]] = set()
    try:
        with raw_jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if not isinstance(ev, dict):
                    continue
                # Only needed when sg_event_id is missing.
                if _sg_event_id(ev):
                    continue
                seen.add(_fallback_key(ev))
    except Exception:
        return set()
    return seen


def _append_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def _ensure_columns(path: Path, *, required: list[str], defaults: dict[str, str]) -> None:
    """
    If the file exists but is missing any required columns, rewrite once with the upgraded header.
    Safe for append workflows.
    """
    if not path.exists():
        return
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            dr = csv.DictReader(f)
            fieldnames = list(dr.fieldnames or [])
            rows = list(dr)
        if not fieldnames:
            return
        if all(col in fieldnames for col in required):
            return

        new_fieldnames = [c for c in required]  # enforce stable order
        for r in rows:
            for col in new_fieldnames:
                if col not in r or r[col] is None:
                    r[col] = defaults.get(col, "")
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=new_fieldnames)
            w.writeheader()
            w.writerows(rows)
        tmp.replace(path)
    except Exception:
        return


def dedupe_sendgrid_jsonl_inplace(path: Path) -> dict[str, int]:
    """
    Rewrite a SendGrid JSONL file keeping only unique events.
    This prevents inflated KPIs when historical webhook retries exist.

    Dedup key:
    - primary: sg_event_id
    - fallback: (email, event/event_type, timestamp/ts, sg_message_id/message_id, url)
    """
    if not path.exists():
        return {"kept": 0, "dropped": 0, "total": 0}

    kept: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_fb: set[tuple[str, str, int, str, str]] = set()

    total = 0
    dropped = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                ev = json.loads(line)
            except Exception:
                dropped += 1
                continue
            if not isinstance(ev, dict):
                dropped += 1
                continue

            sid = _sg_event_id(ev)
            if sid:
                if sid in seen_ids:
                    dropped += 1
                    continue
                seen_ids.add(sid)
                kept.append(ev)
                continue

            em = str(ev.get("email") or "").strip().lower()
            et = str(ev.get("event") or ev.get("event_type") or "").strip().lower()
            tsv = ev.get("timestamp") or ev.get("ts") or 0
            try:
                ts_int = int(tsv)
            except Exception:
                ts_int = 0
            sg_msg_id = str(ev.get("sg_message_id") or ev.get("message_id") or "").strip()
            url = str(ev.get("url") or "").strip()
            fb = (em, et, ts_int, sg_msg_id, url)
            if fb in seen_fb:
                dropped += 1
                continue
            seen_fb.add(fb)
            kept.append(ev)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as out:
        for ev in kept:
            out.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)
    return {"kept": len(kept), "dropped": dropped, "total": total}

