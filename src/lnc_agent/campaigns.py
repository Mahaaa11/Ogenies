from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sendgrid_kpis import load_sendgrid_raw_events


@dataclass(frozen=True)
class CampaignPhaseRow:
    campaign_id: str
    phase_id: str  # send_batch_id preferred else "phase-1"
    template_id: str
    date: str
    recipients_known: int
    recipients_total: int
    processed: int
    delivered: int
    opens: int
    clicks: int
    bounces: int
    dropped: int
    spam: int
    unsub: int
    rapid_click_1h: int
    open_rate_pct: float
    ctr_unique_pct: float
    ctor_unique_pct: float
    delta_open_rate_pct: float | None
    delta_ctr_unique_pct: float | None
    likely_blocker: str


def aggregate_campaign_phases(
    sendgrid_jsonl: Path,
    *,
    known_emails: set[str] | None = None,
    raw_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    raw = raw_events if raw_events is not None else load_sendgrid_raw_events(sendgrid_jsonl)
    norm = [_norm(e) for e in raw]

    # Group into campaigns + phases (mass sends).
    # If send_batch_id isn't present yet, we treat everything as phase-1.
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in norm:
        campaign_id = e.get("campaign_id") or "acquisition"
        phase_id = e.get("send_batch_id") or "phase-1"
        by_group.setdefault((campaign_id, phase_id), []).append(e)

    rows: list[CampaignPhaseRow] = []
    for (campaign_id, phase_id), items in by_group.items():
        template_id = _first(items, "template_id")
        date = _date_from_ts(_min_ts(items))

        processed = sum(1 for i in items if i["event"] in ("processed", "sent"))
        delivered = sum(1 for i in items if i["event"] == "delivered")
        opens = sum(1 for i in items if i["event"] == "open")
        clicks = sum(1 for i in items if i["event"] == "click")
        bounces = sum(1 for i in items if i["event"] == "bounce")
        dropped = sum(1 for i in items if i["event"] == "dropped")
        spam = sum(1 for i in items if i["event"] in ("spamreport", "spam"))
        unsub = sum(1 for i in items if i["event"] in ("unsubscribe", "unsubscribed", "group_unsubscribe"))

        # Audience = unique recipients that were processed/sent (mass send to N prospects)
        audience_total = {
            i.get("email") or ""
            for i in items
            if (i.get("email") or "") and i["event"] in ("processed", "sent", "delivered")
        }
        audience_total = {e for e in audience_total if e}
        recipients_total = len(audience_total)
        if known_emails is None:
            recipients_known = recipients_total
        else:
            recipients_known = len({e for e in audience_total if e in known_emails})
        # Align with dashboard KPIs: count uniques by (email, message_id) to avoid inflation.
        delivered_keys = {
            (i.get("email") or "", i.get("sg_message_id") or "")
            for i in items
            if i["event"] == "delivered" and (i.get("email") or "")
        }
        open_keys = {
            (i.get("email") or "", i.get("sg_message_id") or "")
            for i in items
            if i["event"] == "open" and (i.get("email") or "")
        }
        click_keys = {
            (i.get("email") or "", i.get("sg_message_id") or "", i.get("url") or "")
            for i in items
            if i["event"] == "click" and (i.get("email") or "")
        }
        delivered_u = len(delivered_keys)
        opened_u = len(open_keys)
        clicked_u = len({(k[0], k[1]) for k in click_keys})

        open_rate = _pct(opened_u, delivered_u)
        ctr_unique = _pct(clicked_u, delivered_u)
        ctor_unique = _pct(clicked_u, opened_u)

        rapid = int(_rapid_click_1h_by_email(items))
        likely_blocker = _likely_blocker(processed, delivered, dropped, bounces, spam, unsub)

        rows.append(
            CampaignPhaseRow(
                campaign_id=campaign_id,
                phase_id=phase_id,
                template_id=template_id,
                date=date,
                recipients_known=recipients_known,
                recipients_total=recipients_total,
                processed=processed,
                delivered=delivered,
                opens=opens,
                clicks=clicks,
                bounces=bounces,
                dropped=dropped,
                spam=spam,
                unsub=unsub,
                rapid_click_1h=rapid,
                open_rate_pct=open_rate,
                ctr_unique_pct=ctr_unique,
                ctor_unique_pct=ctor_unique,
                delta_open_rate_pct=None,
                delta_ctr_unique_pct=None,
                likely_blocker=likely_blocker,
            )
        )

    # Sort by campaign, date, phase_id
    rows.sort(key=lambda r: (r.campaign_id, r.date, r.phase_id))

    # Add deltas vs previous phase within same campaign + template_id
    prev_by_template: dict[tuple[str, str], CampaignPhaseRow] = {}
    out: list[dict[str, Any]] = []
    for r in rows:
        prev = prev_by_template.get((r.campaign_id, r.template_id))
        delta_open = round(r.open_rate_pct - prev.open_rate_pct, 2) if prev else None
        delta_ctr = round(r.ctr_unique_pct - prev.ctr_unique_pct, 2) if prev else None
        prev_by_template[(r.campaign_id, r.template_id)] = r

        out.append(
            {
                **r.__dict__,
                "delta_open_rate_pct": delta_open,
                "delta_ctr_unique_pct": delta_ctr,
            }
        )
    return out


def aggregate_campaigns(
    sendgrid_jsonl: Path,
    *,
    known_emails: set[str] | None = None,
    raw_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Returns campaigns, each containing phases (mass sends).
    """
    phases = aggregate_campaign_phases(sendgrid_jsonl, known_emails=known_emails, raw_events=raw_events)
    by_campaign: dict[str, list[dict[str, Any]]] = {}
    for p in phases:
        by_campaign.setdefault(p["campaign_id"], []).append(p)

    out: list[dict[str, Any]] = []
    for cid, items in sorted(by_campaign.items(), key=lambda kv: kv[0]):
        # Campaign-level totals (across phases)
        total_recipients_known = sum(int(i.get("recipients_known") or 0) for i in items)
        total_recipients_total = sum(int(i.get("recipients_total") or 0) for i in items)
        delivered_u = sum(int(i.get("delivered") or 0) for i in items)
        out.append(
            {
                "campaign_id": cid,
                "name": cid.replace("_", " ").title(),
                "phases_count": len(items),
                "total_recipients": total_recipients_known,
                "total_recipients_total": total_recipients_total,
                "total_delivered": delivered_u,
                "phases": items,
            }
        )
    return out


def load_campaign_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_campaign_meta(path: Path, meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm(ev: dict[str, Any]) -> dict[str, Any]:
    ca = ev.get("custom_args") or ev.get("unique_args") or {}
    send_batch_id = ""
    campaign_id = ""
    if isinstance(ca, dict):
        send_batch_id = str(ca.get("send_batch_id") or ca.get("campaign_send_id") or ca.get("batch_id") or "").strip()
        campaign_id = str(ca.get("campaign_id") or ca.get("campaign") or "").strip()
    return {
        "event": str(ev.get("event") or ev.get("event_type") or "").strip().lower(),
        "timestamp": _as_int(ev.get("timestamp") or ev.get("ts"), 0),
        "email": str(ev.get("email") or "").strip().lower(),
        "sg_message_id": str(ev.get("sg_message_id") or ev.get("smtp-id") or ev.get("message_id") or "").strip(),
        "template_id": str(ev.get("sg_template_id") or ev.get("template_id") or "").strip(),
        "send_batch_id": send_batch_id,
        "campaign_id": campaign_id,
    }


def _min_ts(items: list[dict[str, Any]]) -> int:
    ts = [i["timestamp"] for i in items if i.get("timestamp")]
    return min(ts) if ts else 0


def _date_from_ts(ts: int) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def _pct(num: int, den: int) -> float:
    return round((num / den) * 100, 2) if den else 0.0


def _rapid_click_1h_by_email(items: list[dict[str, Any]]) -> bool:
    # A "rapid click" exists if ANY recipient clicked within 1h of their delivery.
    delivered_by_email: dict[str, int] = {}
    click_by_email: dict[str, int] = {}
    for i in items:
        em = str(i.get("email") or "").strip().lower()
        ts = int(i.get("timestamp") or 0)
        if not em or not ts:
            continue
        if i["event"] == "delivered":
            delivered_by_email[em] = min(delivered_by_email.get(em, ts), ts)
        if i["event"] == "click":
            click_by_email[em] = min(click_by_email.get(em, ts), ts)
    for em, dts in delivered_by_email.items():
        cts = click_by_email.get(em, 0)
        if cts and 0 <= (cts - dts) <= 3600:
            return True
    return False


def _likely_blocker(processed: int, delivered: int, dropped: int, bounces: int, spam: int, unsub: int) -> str:
    if dropped:
        return "Dropped (invalid/blocked address)"
    if bounces:
        return "Bounce (deliverability issue)"
    if processed and delivered == 0:
        return "Not delivered (check SendGrid activity)"
    if spam:
        return "Spam complaints"
    if unsub:
        return "Unsubscribes"
    return ""


def _first(items: list[dict[str, Any]], key: str) -> str:
    for it in items:
        v = str(it.get(key) or "").strip()
        if v:
            return v
    return ""


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default

