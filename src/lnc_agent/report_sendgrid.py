from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent import analyze_campaign
from .io import read_prospects
from .models import Event, Prospect
from .sendgrid_kpis import load_sendgrid_raw_events


@dataclass(frozen=True)
class SendGridRecipientSummary:
    prospect_id: str
    email: str
    sg_message_id: str
    send_batch_id: str
    processed: int
    delivered: int
    opens: int
    clicks: int
    opens_unique: int
    clicks_unique: int
    first_processed_ts: int
    first_delivered_ts: int
    first_open_ts: int
    first_click_ts: int
    time_spent_seconds: int
    top_click_url: str
    clicked_urls_json: str
    rapid_click_1h: bool


def write_sendgrid_agent_report(
    *,
    prospects_csv: str | Path,
    sendgrid_jsonl: str | Path,
    out_csv: str | Path,
    recommendations_csv: str | Path | None = None,
    raw_events: list[dict[str, Any]] | None = None,
    scope_mode: str = "latest",
) -> None:
    prospects = read_prospects(prospects_csv)
    email_to_prospect: dict[str, Prospect] = {p.email.strip().lower(): p for p in prospects if p.email}

    raw = raw_events if raw_events is not None else load_sendgrid_raw_events(Path(sendgrid_jsonl))
    norm = [_norm_min(e) for e in raw]

    summaries = _summarize_by_recipient(norm, email_to_prospect, scope_mode=scope_mode)
    # IMPORTANT: keep scores consistent with the platform "Prospects" view.
    # If we already have recommendations.csv from /api/run, reuse it instead of recomputing.
    by_pid = _load_recommendations_csv(Path(recommendations_csv)) if recommendations_csv else {}
    if not by_pid:
        # Fallback: compute from raw open/click events (best-effort)
        events: list[Event] = []
        scored_prospects: list[Prospect] = []
        for s in summaries:
            p = email_to_prospect.get(s.email)
            if not p:
                continue
            scored_prospects.append(p)
            for e in norm:
                if e["email"] != s.email:
                    continue
                if e["event"] not in ("open", "click"):
                    continue
                events.append(
                    Event(
                        prospect_id=p.id,
                        event_type=e["event"],
                        campaign_step="sendgrid",
                        day=0,
                        hour=_hour_from_ts(e["ts"]),
                        weekday=_weekday_from_ts(e["ts"]),
                    )
                )
        recommendations, _drafts, _dashboard = analyze_campaign(scored_prospects, events)
        by_pid = {r.prospect.id: r for r in recommendations}

    rows: list[dict[str, Any]] = []
    for s in summaries:
        p = email_to_prospect.get(s.email)
        if not p:
            continue
        rec = by_pid.get(p.id)
        if not rec:
            continue
        rows.append(
            {
                "prospect_id": p.id,
                "email": p.email,
                "sg_message_id": s.sg_message_id,
                "send_batch_id": s.send_batch_id,
                "processed": s.processed,
                "delivered": s.delivered,
                "opens": s.opens,
                "clicks": s.clicks,
                "opens_unique": s.opens_unique,
                "clicks_unique": s.clicks_unique,
                "first_processed_ts": s.first_processed_ts or "",
                "first_delivered_ts": s.first_delivered_ts or "",
                "first_open_ts": s.first_open_ts or "",
                "first_click_ts": s.first_click_ts or "",
                "time_spent_seconds": s.time_spent_seconds,
                "top_click_url": s.top_click_url,
                "clicked_urls_json": s.clicked_urls_json,
                "rapid_click_1h": int(s.rapid_click_1h),
                "score": rec.score,
                "segment": rec.segment,
                "next_action": rec.next_action,
                "campaign_step": rec.campaign_step,
                "best_send_weekday": getattr(rec, "best_send_weekday", ""),
                "best_send_hour": getattr(rec, "best_send_hour", ""),
                "reason": rec.reason,
            }
        )

    rows.sort(key=lambda r: _pid_sort_key(str(r.get("prospect_id") or "")))

    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(out_path, rows)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _norm_min(ev: dict[str, Any]) -> dict[str, Any]:
    email = str(ev.get("email") or "").strip().lower()
    event = str(ev.get("event") or ev.get("event_type") or "").strip().lower()
    ts = _as_int(ev.get("timestamp") or ev.get("ts"), 0)
    msg_id = str(ev.get("sg_message_id") or ev.get("smtp-id") or ev.get("message_id") or "").strip()
    sg_event_id = str(ev.get("sg_event_id") or ev.get("event_id") or "").strip()
    url = str(ev.get("url") or "").strip()
    ca = ev.get("custom_args") or ev.get("unique_args") or {}
    send_batch_id = ""
    if isinstance(ca, dict):
        send_batch_id = str(ca.get("send_batch_id") or ca.get("campaign_send_id") or ca.get("batch_id") or "").strip()
    return {
        "email": email,
        "event": event,
        "ts": ts,
        "msg_id": msg_id,
        "sg_event_id": sg_event_id,
        "url": url,
        "send_batch_id": send_batch_id,
    }


def _summarize_by_recipient(
    norm: list[dict[str, Any]],
    email_to_prospect: dict[str, Prospect],
    *,
    scope_mode: str,
) -> list[SendGridRecipientSummary]:
    # Restrict to known prospects and to emails that actually had activity
    emails = {e["email"] for e in norm if e["email"] in email_to_prospect}

    out: list[SendGridRecipientSummary] = []
    for em in sorted(emails):
        items = [e for e in norm if e["email"] == em]
        processed = [e for e in items if e["event"] in ("processed", "sent")]
        delivered = [e for e in items if e["event"] == "delivered"]
        opens = [e for e in items if e["event"] == "open"]
        clicks = [e for e in items if e["event"] == "click"]
        mode = (scope_mode or "latest").strip().lower()

        # Pick the "current send" as the most recent message id by timestamp.
        msg_ids = [(e.get("msg_id") or "", int(e.get("ts") or 0)) for e in items if (e.get("msg_id") or "")]
        sg_message_id = max(msg_ids, key=lambda t: t[1])[0] if msg_ids else ""
        batch_ids = [e.get("send_batch_id") or "" for e in items if e.get("send_batch_id")]
        send_batch_id = str(batch_ids[0]) if batch_ids else ""

        fp = min((e["ts"] for e in processed if e["ts"]), default=0)
        fd = min((e["ts"] for e in delivered if e["ts"]), default=0)
        fo = min((e["ts"] for e in opens if e["ts"]), default=0)
        fc = min((e["ts"] for e in clicks if e["ts"]), default=0)

        rapid = False
        if fd and fc:
            rapid = 0 <= (fc - fd) <= 3600

        p = email_to_prospect[em]

        # Tracking page is per-prospect; counts should be stable and represent the number of sends
        # (unique message ids) observed in the selected scope.
        processed_unique = len({e.get("msg_id") or "" for e in processed if (e.get("msg_id") or "")}) or (1 if processed else 0)
        delivered_unique = len({e.get("msg_id") or "" for e in delivered if (e.get("msg_id") or "")}) or (1 if delivered else 0)
        # For opens/clicks:
        # - scope=all/last_24h: aggregate within the scope (do NOT restrict to latest msg_id)
        # - scope=latest/latest_batch: restrict to the latest msg_id to represent the current send
        if mode in ("all", "all_time", "alltime", "last_24h", "24h"):
            opens_cur = opens
            clicks_cur = clicks
        else:
            opens_cur = [e for e in opens if not sg_message_id or (e.get("msg_id") == sg_message_id)]
            clicks_cur = [e for e in clicks if not sg_message_id or (e.get("msg_id") == sg_message_id)]
        # Deduplicate by SendGrid event id to avoid double-counting retries/duplicates.
        opens_total = len({e.get("sg_event_id") or f"{e.get('ts')}:{e.get('msg_id')}" for e in opens_cur})
        clicks_total = len({e.get("sg_event_id") or f"{e.get('ts')}:{e.get('msg_id')}" for e in clicks_cur})
        opens_unique = 1 if opens_total > 0 else 0
        clicks_unique = 1 if clicks_total > 0 else 0

        # Click locations (URLs) for the current send (dedup by sg_event_id)
        click_urls: list[str] = []
        seen_click_ids: set[str] = set()
        for c in clicks_cur:
            cid = str(c.get("sg_event_id") or f"{c.get('ts')}:{c.get('msg_id')}")
            if cid in seen_click_ids:
                continue
            seen_click_ids.add(cid)
            u = str(c.get("url") or "").strip()
            if u:
                click_urls.append(u)
        # Top URL = most frequent (preserving order for ties)
        top_click_url = ""
        if click_urls:
            counts: dict[str, int] = {}
            for u in click_urls:
                counts[u] = counts.get(u, 0) + 1
            top_click_url = max(counts.keys(), key=lambda k: (counts[k], -click_urls.index(k)))

        clicked_urls_json = json.dumps(click_urls, ensure_ascii=False)

        # Time spent (best-effort): approximate dwell time for the *latest send*.
        # Using "all time" opens/clicks can produce unrealistic durations (spanning days/weeks),
        # so we always compute this metric on the latest sg_message_id when available.
        time_spent_seconds = 0
        opens_for_time = opens_cur
        clicks_for_time = clicks_cur
        if sg_message_id:
            opens_for_time = [e for e in opens if (e.get("msg_id") == sg_message_id)]
            clicks_for_time = [e for e in clicks if (e.get("msg_id") == sg_message_id)]

        open_ts = [int(e.get("ts") or 0) for e in opens_for_time if int(e.get("ts") or 0) > 0]
        if open_ts:
            start = min(open_ts)
            event_ts = open_ts + [int(e.get("ts") or 0) for e in clicks_for_time if int(e.get("ts") or 0) > 0]
            end = max(event_ts) if event_ts else start
            # Cap to 6 hours to avoid outliers from delayed events/time skew.
            time_spent_seconds = min(6 * 3600, max(0, end - start))

        out.append(
            SendGridRecipientSummary(
                prospect_id=p.id,
                email=em,
                sg_message_id=("" if mode in ("all", "all_time", "alltime", "last_24h", "24h") else sg_message_id),
                send_batch_id=("" if mode in ("all", "all_time", "alltime", "last_24h", "24h") else send_batch_id),
                processed=processed_unique,
                delivered=delivered_unique,
                opens=opens_total,
                clicks=clicks_total,
                opens_unique=opens_unique,
                clicks_unique=clicks_unique,
                first_processed_ts=fp,
                first_delivered_ts=fd,
                first_open_ts=fo,
                first_click_ts=fc,
                time_spent_seconds=time_spent_seconds,
                top_click_url=top_click_url,
                clicked_urls_json=clicked_urls_json,
                rapid_click_1h=rapid,
            )
        )
    return out


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _pid_sort_key(pid: str) -> tuple[int, str]:
    # Sort P001..P100 naturally; fallback to string.
    p = pid.strip().upper()
    if p.startswith("P"):
        n = _as_int(p[1:], -1)
        if n >= 0:
            return (n, p)
    return (10**9, p)


def _hour_from_ts(ts: int) -> int:
    if not ts:
        return 0
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return int(dt.hour)


def _weekday_from_ts(ts: int) -> int:
    if not ts:
        return -1
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return int(dt.weekday())


@dataclass(frozen=True)
class _RecRow:
    prospect_id: str
    score: int
    segment: str
    next_action: str
    campaign_step: str
    best_send_weekday: int
    best_send_hour: int
    reason: str


def _load_recommendations_csv(path: Path) -> dict[str, _RecRow]:
    if not path.exists():
        return {}
    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            out: dict[str, _RecRow] = {}
            for r in reader:
                pid = str(r.get("prospect_id") or "").strip()
                if not pid:
                    continue
                out[pid] = _RecRow(
                    prospect_id=pid,
                    score=_as_int(r.get("score"), 0),
                    segment=str(r.get("segment") or ""),
                    next_action=str(r.get("next_action") or ""),
                    campaign_step=str(r.get("campaign_step") or ""),
                    best_send_weekday=_as_int(r.get("best_send_weekday"), -1),
                    best_send_hour=_as_int(r.get("best_send_hour"), 9),
                    reason=str(r.get("reason") or ""),
                )
            return out
    except Exception:
        return {}

