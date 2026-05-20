from __future__ import annotations

import os
import csv
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

from src.lnc_agent.agent import analyze_campaign
from src.lnc_agent.campaigns import (
    aggregate_campaigns,
    load_campaign_meta,
    save_campaign_meta,
)
from src.lnc_agent.io import read_events, read_prospects
from src.lnc_agent.local_event_store import LocalEventStoreConfig, store_sendgrid_events_locally
from src.lnc_agent.db import MySQLConfig
from src.lnc_agent.repository import MySQLStores
from src.lnc_agent.report_sendgrid import write_sendgrid_agent_report
from src.lnc_agent.sendgrid_kpis import compute_sendgrid_kpis, compute_sendgrid_trend_by_day, load_sendgrid_raw_events
from src.lnc_agent.sendgrid_sender import SendGridConfig, SendGridSendError, send_dynamic_template_email
from src.lnc_agent.send_cli import read_email_drafts_csv
from src.lnc_agent.models import EmailDraft


class RunRequest(BaseModel):
    prospects_csv: str = "data/prospects.csv"
    events_csv: str = "data/events_webhook.csv"
    sendgrid_raw_jsonl: str | None = "data/sendgrid_events.jsonl"
    out_dir: str = "output_platform"


class SendRequest(BaseModel):
    prospects_csv: str = "data/prospects.csv"
    drafts_csv: str = "output_platform/email_drafts.csv"
    prospect_id: str | None = None
    limit: int = 1
    sendgrid_api_key: str | None = None
    campaign_id: str = "acquisition"
    send_batch_id: str | None = None


class CampaignMetaPatch(BaseModel):
    assignee: str | None = None
    blocker: str | None = None
    status: str | None = None


class DecisionPatch(BaseModel):
    next_action: str | None = None
    approved: bool | None = None
    send_weekday: int | None = None
    send_hour: int | None = None


class DecisionsValidateRequest(BaseModel):
    prospect_ids: list[str]
    execute: bool = True
    campaign_id: str = "acquisition"


def _project_root() -> Path:
    # backend/app/main.py -> backend/app -> backend -> repo root
    return Path(__file__).resolve().parents[2]


def _abs(p: str) -> Path:
    pth = Path(p)
    return pth if pth.is_absolute() else (_project_root() / pth)


# Load repo-root .env automatically (so keys don't need terminal paste)
if load_dotenv is not None:
    load_dotenv(dotenv_path=_project_root() / ".env", override=False)


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


def _local_store_cfg() -> LocalEventStoreConfig:
    return LocalEventStoreConfig(
        raw_jsonl_path=_abs("data/sendgrid_events.jsonl"),
        normalized_events_csv_path=_abs("data/events_webhook.csv"),
        prospects_csv_path=_abs("data/prospects.csv"),
    )


def _event_store_mode() -> str:
    return _env("LNC_EVENT_STORE", "local").lower()


def _load_raw_sendgrid_events(path_hint: str = "data/sendgrid_events.jsonl") -> list[dict[str, Any]]:
    """
    Source of truth for raw events:
    - if LNC_EVENT_STORE=mysql -> load from MySQL (payload_json)
    - else -> load from JSONL file
    """
    if _event_store_mode() == "mysql":
        cfg = _mysql_cfg_from_env()
        if not cfg.database:
            raise HTTPException(status_code=400, detail="LNC_MYSQL_DATABASE is required for mysql event store")
        return MySQLStores(cfg).list_sendgrid_raw_events()
    return load_sendgrid_raw_events(_abs(path_hint))

def _write_prospects_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


app = FastAPI(title="L&C Emailing API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("LNC_CORS_ORIGINS", "http://localhost:3000").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "L&C Emailing — Lead & Connect platform running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/debug/config")
def debug_config() -> dict[str, Any]:
    """
    Safe config check endpoint (does NOT return secrets).
    """
    api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
    template_id = os.environ.get("LNC_SENDGRID_TEMPLATE_ID", "").strip()
    from_email = os.environ.get("LNC_SENDGRID_FROM_EMAIL", "").strip()
    return {
        "ok": True,
        "sendgrid_api_key_set": bool(api_key),
        "sendgrid_api_key_prefix": (api_key[:3] + "…") if api_key else "",
        "template_id_set": bool(template_id),
        "template_id": template_id,
        "from_email_set": bool(from_email),
        "from_email": from_email,
    }


@app.post("/api/run")
def run_agent(req: RunRequest) -> dict[str, Any]:
    out = _run_pipeline(
        prospects_csv=req.prospects_csv,
        events_csv=req.events_csv,
        sendgrid_raw_jsonl=req.sendgrid_raw_jsonl,
        out_dir=req.out_dir,
    )
    return {"ok": True, **out}


def _load_prospects(prospects_csv: str) -> list[Any]:
    # Auto-source prospects from MySQL if configured; otherwise use CSV
    if _env("LNC_PROSPECT_SOURCE", "csv").lower() == "mysql":
        cfg = _mysql_cfg_from_env()
        if not cfg.database:
            raise HTTPException(status_code=400, detail="LNC_MYSQL_DATABASE is required for mysql prospect source")
        return MySQLStores(cfg).list_prospects()
    return read_prospects(_abs(prospects_csv))


def _run_pipeline(
    *,
    prospects_csv: str,
    events_csv: str,
    sendgrid_raw_jsonl: str | None,
    out_dir: str,
    raw_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Single source of truth for generating platform artifacts:
    - recommendations.csv / email_drafts.csv / dashboard.csv
    Dashboard includes live SendGrid KPIs when raw events are available.
    """
    prospects = _load_prospects(prospects_csv)
    events = read_events(_abs(events_csv))
    recommendations, drafts, dashboard = analyze_campaign(prospects, events)

    if raw_events is not None:
        dashboard.update(compute_sendgrid_kpis(prospects=prospects, recommendations=recommendations, raw_events=raw_events))
    elif sendgrid_raw_jsonl:
        raw = load_sendgrid_raw_events(_abs(sendgrid_raw_jsonl))
        dashboard.update(compute_sendgrid_kpis(prospects=prospects, recommendations=recommendations, raw_events=raw))

    out_path = _abs(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    from src.lnc_agent.io import write_dashboard, write_email_drafts, write_recommendations

    write_recommendations(out_path / "recommendations.csv", recommendations)
    write_email_drafts(out_path / "email_drafts.csv", drafts)
    write_dashboard(out_path / "dashboard.csv", dashboard)
    return {
        "out_dir": str(out_path),
        "prospects": len(prospects),
        "recommendations": len(recommendations),
    }


@app.post("/api/report/sendgrid")
def report_sendgrid(
    prospects_csv: str = "data/prospects.csv",
    sendgrid_raw_jsonl: str = "data/sendgrid_events.jsonl",
    out_csv: str = "output_platform/sendgrid_agent_report.csv",
    scope: str = "all",
) -> dict[str, Any]:
    prospects = _load_prospects(prospects_csv)
    known_emails = {getattr(p, "email", "").strip().lower() for p in prospects if getattr(p, "email", "")}
    raw_all = _load_raw_sendgrid_events(sendgrid_raw_jsonl)
    raw, scope_info = _filter_raw_events(raw_all, known_emails=known_emails, scope=scope)

    # Rebuild normalized webhook events from the same filtered scope (weekday/hour preserved)
    cfg = LocalEventStoreConfig(
        raw_jsonl_path=_abs(sendgrid_raw_jsonl),
        normalized_events_csv_path=_abs("data/events_webhook.csv"),
        prospects_csv_path=_abs(prospects_csv),
    )
    if cfg.normalized_events_csv_path.exists():
        cfg.normalized_events_csv_path.unlink()
    store_sendgrid_events_locally(cfg, raw, write_raw_jsonl=False, dedupe_against_existing_raw=False)

    # Refresh platform artifacts using the same filtered raw events.
    _run_pipeline(
        prospects_csv=prospects_csv,
        events_csv="data/events_webhook.csv",
        sendgrid_raw_jsonl=None,
        out_dir="output_platform",
        raw_events=raw,
    )
    out_path = _abs(out_csv)
    write_sendgrid_agent_report(
        prospects_csv=_abs(prospects_csv),
        sendgrid_jsonl=_abs(sendgrid_raw_jsonl),
        out_csv=out_path,
        recommendations_csv=_abs("output_platform/recommendations.csv"),
        raw_events=raw,
        scope_mode=scope,
    )
    return {"ok": True, "out_csv": str(out_path), "scope": scope_info}


@app.get("/api/dashboard")
def get_dashboard(dashboard_csv: str = "output_platform/dashboard.csv") -> dict[str, Any]:
    path = _abs(dashboard_csv)
    if not path.exists():
        raise HTTPException(status_code=404, detail="dashboard.csv not found; run /api/run first")
    import csv

    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {"ok": True, "metrics": rows}


@app.get("/api/recommendations")
def get_recommendations(recommendations_csv: str = "output_platform/recommendations.csv") -> dict[str, Any]:
    path = _abs(recommendations_csv)
    if not path.exists():
        raise HTTPException(status_code=404, detail="recommendations.csv not found; run /api/run first")
    import csv

    with path.open(newline="", encoding="utf-8") as f:
        return {"ok": True, "rows": list(csv.DictReader(f))}


def _decisions_path() -> Path:
    return _abs("output_platform/decisions.json")


def _load_decisions() -> dict[str, Any]:
    path = _decisions_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_decisions(data: dict[str, Any]) -> None:
    path = _decisions_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/decisions")
def get_decisions(recommendations_csv: str = "output_platform/recommendations.csv") -> dict[str, Any]:
    """
    Returns agent suggestions + user overrides/approval state.
    """
    path = _abs(recommendations_csv)
    if not path.exists():
        raise HTTPException(status_code=404, detail="recommendations.csv not found; run /api/run first")
    import csv

    overrides = _load_decisions()
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    out_rows: list[dict[str, Any]] = []
    for r in rows:
        pid = str(r.get("prospect_id") or "").strip()
        o = overrides.get(pid, {}) if pid else {}
        suggested = str(r.get("next_action") or "")
        final = str(o.get("next_action") or "").strip() or suggested
        approved = bool(o.get("approved")) if "approved" in o else False
        suggested_wd = int(r.get("best_send_weekday") or -1) if str(r.get("best_send_weekday") or "").strip() else -1
        suggested_hr = int(r.get("best_send_hour") or 9) if str(r.get("best_send_hour") or "").strip() else 9
        final_wd = int(o.get("send_weekday")) if "send_weekday" in o and o.get("send_weekday") is not None else suggested_wd
        final_hr = int(o.get("send_hour")) if "send_hour" in o and o.get("send_hour") is not None else suggested_hr
        out_rows.append(
            {
                **r,
                "suggested_next_action": suggested,
                "final_next_action": final,
                "approved": approved,
                "suggested_send_weekday": suggested_wd,
                "suggested_send_hour": suggested_hr,
                "final_send_weekday": final_wd,
                "final_send_hour": final_hr,
            }
        )
    return {"ok": True, "rows": out_rows}


@app.patch("/api/decisions/{prospect_id}")
def patch_decision(prospect_id: str, patch: DecisionPatch) -> dict[str, Any]:
    pid = prospect_id.strip()
    if not pid:
        raise HTTPException(status_code=400, detail="prospect_id required")
    data = _load_decisions()
    cur = data.get(pid, {})
    if patch.next_action is not None:
        cur["next_action"] = patch.next_action
    if patch.approved is not None:
        cur["approved"] = bool(patch.approved)
    if patch.send_weekday is not None:
        cur["send_weekday"] = int(patch.send_weekday)
    if patch.send_hour is not None:
        cur["send_hour"] = int(patch.send_hour)
    data[pid] = cur
    _save_decisions(data)
    return {"ok": True, "prospect_id": pid, "decision": cur}


@app.post("/api/decisions/validate")
def validate_decisions(req: DecisionsValidateRequest) -> dict[str, Any]:
    data = _load_decisions()
    updated = 0
    to_execute: list[str] = []
    for pid in req.prospect_ids:
        k = str(pid or "").strip()
        if not k:
            continue
        cur = data.get(k, {})
        cur["approved"] = True
        data[k] = cur
        updated += 1
        to_execute.append(k)
    _save_decisions(data)

    sent = 0
    skipped = 0
    batch_id = ""
    if req.execute and to_execute:
        # Execute means: send emails immediately via SendGrid for approved decisions.
        api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="Missing SENDGRID_API_KEY env var (cannot execute)")
        cfg = SendGridConfig(api_key=api_key)
        batch_id = _next_send_batch_id(campaign_id=req.campaign_id)

        prospects = read_prospects(_abs("data/prospects.csv"))
        by_id = {p.id: p for p in prospects}
        drafts = read_email_drafts_csv(_abs("output_platform/email_drafts.csv"))
        draft_by_pid = {d.prospect_id: d for d in drafts}

        for pid in to_execute:
            p = by_id.get(pid)
            d0 = draft_by_pid.get(pid)
            cur = data.get(pid, {})
            action = str(cur.get("next_action") or "").strip() or ""
            if not p or not d0 or action == "do_not_contact":
                skipped += 1
                continue

            dd = dict(d0.dynamic_template_data or {})
            dd["campaign_id"] = req.campaign_id
            dd["send_batch_id"] = batch_id
            if cur.get("send_weekday") is not None:
                dd["send_weekday"] = int(cur["send_weekday"])
            if cur.get("send_hour") is not None:
                dd["send_hour"] = int(cur["send_hour"])

            d2 = EmailDraft(
                prospect_id=d0.prospect_id,
                from_email=d0.from_email,
                template_id=d0.template_id,
                dynamic_template_data=dd,
            )
            try:
                send_dynamic_template_email(cfg=cfg, draft=d2, prospect=p)
                sent += 1
            except SendGridSendError:
                skipped += 1
                continue

            # persist execution metadata
            cur["last_send_batch_id"] = batch_id
            cur["last_executed_ts"] = int(__import__("time").time())
            data[pid] = cur

        _save_decisions(data)

    return {"ok": True, "approved_n": updated, "executed": bool(req.execute), "sent": sent, "skipped": skipped, "send_batch_id": batch_id}


@app.get("/api/tracking")
def get_tracking(report_csv: str = "output_platform/sendgrid_agent_report.csv") -> dict[str, Any]:
    path = _abs(report_csv)
    if not path.exists():
        raise HTTPException(status_code=404, detail="sendgrid_agent_report.csv not found; run /api/report/sendgrid first")
    import csv

    with path.open(newline="", encoding="utf-8") as f:
        return {"ok": True, "rows": list(csv.DictReader(f))}


@app.get("/api/campaigns")
def get_campaigns(
    sendgrid_raw_jsonl: str = "data/sendgrid_events.jsonl",
    meta_json: str = "output_platform/campaign_meta.json",
    prospects_csv: str = "data/prospects.csv",
    scope: str = "all",
) -> dict[str, Any]:
    # Restrict audience metrics to known prospects
    prospects = _load_prospects(prospects_csv)
    known_emails = {getattr(p, "email", "").strip().lower() for p in prospects if getattr(p, "email", "")}
    raw_all = _load_raw_sendgrid_events(sendgrid_raw_jsonl)
    raw, scope_info = _filter_raw_events(raw_all, known_emails=known_emails, scope=scope)
    campaigns = aggregate_campaigns(_abs(sendgrid_raw_jsonl), known_emails=known_emails, raw_events=raw)
    meta = load_campaign_meta(_abs(meta_json))
    # attach metadata at phase level: key = "{campaign_id}:{phase_id}"
    for c in campaigns:
        for p in c.get("phases", []):
            k = f"{c['campaign_id']}:{p['phase_id']}"
            m = meta.get(k, {})
            p["assignee"] = m.get("assignee", "")
            p["blocker_owner"] = m.get("blocker", "")
            p["status"] = m.get("status", "")
    return {"ok": True, "campaigns": campaigns, "scope": scope_info}


@app.get("/api/trend")
def get_trend(
    sendgrid_raw_jsonl: str = "data/sendgrid_events.jsonl",
    prospects_csv: str = "data/prospects.csv",
    scope: str = "all",
) -> dict[str, Any]:
    prospects = _load_prospects(prospects_csv)
    known_emails = {getattr(p, "email", "").strip().lower() for p in prospects if getattr(p, "email", "")}
    raw_all = _load_raw_sendgrid_events(sendgrid_raw_jsonl)
    raw, scope_info = _filter_raw_events(raw_all, known_emails=known_emails, scope=scope)
    points = compute_sendgrid_trend_by_day(raw_events=raw)
    return {"ok": True, "points": points, "scope": scope_info}


@app.get("/api/trend/phases")
def get_trend_phases(
    sendgrid_raw_jsonl: str = "data/sendgrid_events.jsonl",
    prospects_csv: str = "data/prospects.csv",
    scope: str = "all",
) -> dict[str, Any]:
    prospects = _load_prospects(prospects_csv)
    known_emails = {getattr(p, "email", "").strip().lower() for p in prospects if getattr(p, "email", "")}
    raw_all = _load_raw_sendgrid_events(sendgrid_raw_jsonl)
    raw, scope_info = _filter_raw_events(raw_all, known_emails=known_emails, scope=scope)
    from src.lnc_agent.sendgrid_kpis import compute_sendgrid_trend_by_phase

    points = compute_sendgrid_trend_by_phase(raw_events=raw)
    return {"ok": True, "points": points, "scope": scope_info}


def _filter_raw_events(
    raw: list[dict[str, Any]],
    *,
    known_emails: set[str],
    scope: str = "latest",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    scope:
    - "all": all known events (from beginning)
    - "latest": latest batch if present, otherwise last 24h
    - "latest_batch": latest send_batch_id only
    - "last_24h": last 24 hours only
    Always filters to known prospects emails (removes test traffic).
    """
    def ts(ev: dict[str, Any]) -> int:
        try:
            return int(ev.get("timestamp") or ev.get("ts") or 0)
        except Exception:
            return 0

    def email(ev: dict[str, Any]) -> str:
        return str(ev.get("email") or "").strip().lower()

    def batch_id(ev: dict[str, Any]) -> str:
        ca = ev.get("custom_args") or ev.get("unique_args") or {}
        if isinstance(ca, dict):
            return str(ca.get("send_batch_id") or ca.get("campaign_send_id") or ca.get("batch_id") or "").strip()
        return ""

    raw_known = [e for e in raw if email(e) in known_emails]
    if not raw_known:
        return [], {"mode": "empty"}

    max_ts = max(ts(e) for e in raw_known)
    scope_norm = (scope or "latest").strip().lower()
    if scope_norm in ("all", "all_time", "alltime"):
        return raw_known, {"mode": "all", "max_ts": max_ts, "events": len(raw_known)}
    batches: dict[str, int] = {}
    for e in raw_known:
        bid = batch_id(e)
        if not bid:
            continue
        batches[bid] = max(batches.get(bid, 0), ts(e))

    if batches:
        latest_bid = max(batches.items(), key=lambda kv: kv[1])[0]
        if scope_norm in ("latest_batch", "batch", "phase"):
            out = [e for e in raw_known if batch_id(e) == latest_bid]
            return out, {"mode": "latest_batch", "send_batch_id": latest_bid, "max_ts": max_ts, "events": len(out)}
        if scope_norm in ("last_24h", "24h"):
            cutoff = max_ts - 86400
            out = [e for e in raw_known if ts(e) >= cutoff]
            return out, {"mode": "last_24h", "cutoff_ts": cutoff, "max_ts": max_ts, "events": len(out)}
        # default "latest": prefer latest batch when available
        out = [e for e in raw_known if batch_id(e) == latest_bid]
        return out, {"mode": "latest_batch", "send_batch_id": latest_bid, "max_ts": max_ts, "events": len(out)}

    cutoff = max_ts - 86400
    out = [e for e in raw_known if ts(e) >= cutoff]
    return out, {"mode": "last_24h", "cutoff_ts": cutoff, "max_ts": max_ts, "events": len(out)}


@app.patch("/api/campaigns/{campaign_id}/{phase_id}")
def patch_campaign_meta(
    campaign_id: str,
    phase_id: str,
    patch: CampaignMetaPatch,
    meta_json: str = "output_platform/campaign_meta.json",
) -> dict[str, Any]:
    path = _abs(meta_json)
    meta = load_campaign_meta(path)
    key = f"{campaign_id}:{phase_id}"
    cur = meta.get(key, {})
    if patch.assignee is not None:
        cur["assignee"] = patch.assignee
    if patch.blocker is not None:
        cur["blocker"] = patch.blocker
    if patch.status is not None:
        cur["status"] = patch.status
    meta[key] = cur
    save_campaign_meta(path, meta)
    return {"ok": True, "campaign_id": campaign_id, "phase_id": phase_id, "meta": cur}


@app.post("/api/send")
def send_via_sendgrid(req: SendRequest) -> dict[str, Any]:
    api_key = (req.sendgrid_api_key or os.environ.get("SENDGRID_API_KEY", "")).strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing SENDGRID_API_KEY env var")

    prospects = read_prospects(_abs(req.prospects_csv))
    by_id = {p.id: p for p in prospects}
    drafts = read_email_drafts_csv(_abs(req.drafts_csv))

    cfg = SendGridConfig(api_key=api_key)
    results: list[dict[str, Any]] = []
    sent = 0

    send_batch_id = (req.send_batch_id or "").strip() or _next_send_batch_id(campaign_id=req.campaign_id)
    for d in drafts:
        if req.prospect_id and d.prospect_id != req.prospect_id:
            continue
        if sent >= req.limit:
            break
        if not d.from_email:
            continue
        p = by_id.get(d.prospect_id)
        if not p:
            continue
        try:
            dd = dict(d.dynamic_template_data or {})
            dd.setdefault("campaign_id", req.campaign_id)
            dd.setdefault("send_batch_id", send_batch_id)
            d2 = EmailDraft(
                prospect_id=d.prospect_id,
                from_email=d.from_email,
                template_id=d.template_id,
                dynamic_template_data=dd,
            )
            resp = send_dynamic_template_email(cfg=cfg, draft=d2, prospect=p)
        except SendGridSendError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        results.append({"prospect_id": d.prospect_id, "status_code": resp.get("status_code"), "headers": resp.get("headers")})
        sent += 1

    return {"ok": True, "sent": sent, "campaign_id": req.campaign_id, "send_batch_id": send_batch_id, "results": results}


def _send_batch_state_path() -> Path:
    return _abs("output_platform/send_batch_state.json")


def _next_send_batch_id(*, campaign_id: str) -> str:
    """
    Allocate a new "phase" id per send call.
    Example: phase-1, phase-2, ...
    Stored locally so subsequent sends increment.
    """
    path = _send_batch_state_path()
    try:
        if path.exists():
            state = json.loads(path.read_text(encoding="utf-8"))
        else:
            state = {}
    except Exception:
        state = {}

    key = (campaign_id or "acquisition").strip() or "acquisition"
    cur = int(state.get(key, 0) or 0)
    nxt = cur + 1
    state[key] = nxt
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return f"phase-{nxt}"


@app.post("/webhooks/sendgrid/events")
async def sendgrid_events(request: Request) -> dict[str, Any]:
    """
    SendGrid Event Webhook endpoint.
    Stores events locally into:
    - data/sendgrid_events.jsonl (raw)
    - data/events_webhook.csv (normalized)
    """
    payload = await request.json()
    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="expected a JSON array")
    mode = _event_store_mode()
    if mode == "mysql":
        cfg = _mysql_cfg_from_env()
        if not cfg.database:
            raise HTTPException(status_code=400, detail="LNC_MYSQL_DATABASE is required for mysql event store")
        try:
            inserted = MySQLStores(cfg).insert_sendgrid_events(payload)
            return {"ok": True, "inserted": inserted, "store": "mysql"}
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"mysql_unavailable: {e}") from e

    inserted = store_sendgrid_events_locally(_local_store_cfg(), payload)
    return {"ok": True, "inserted": inserted, "store": "local"}


@app.post("/api/rebuild/events-webhook")
def rebuild_events_webhook(
    prospects_csv: str = "data/prospects.csv",
    sendgrid_raw_jsonl: str = "data/sendgrid_events.jsonl",
    out_csv: str = "data/events_webhook.csv",
) -> dict[str, Any]:
    """
    Rebuild normalized webhook CSV (with weekday) from the raw SendGrid JSONL.
    This upgrades existing data so "best day/time" can be learned per prospect.
    """
    raw_path = _abs(sendgrid_raw_jsonl)
    out_path = _abs(out_csv)
    cfg = LocalEventStoreConfig(
        raw_jsonl_path=raw_path,
        normalized_events_csv_path=out_path,
        prospects_csv_path=_abs(prospects_csv),
    )
    raw_events = load_sendgrid_raw_events(raw_path)
    # Overwrite normalized CSV from scratch
    if out_path.exists():
        out_path.unlink()
    inserted = store_sendgrid_events_locally(cfg, raw_events)
    return {"ok": True, "out_csv": str(out_path), "rows": inserted}


@app.post("/api/sync/prospects/mysql")
def sync_prospects_from_mysql(out_csv: str = "data/prospects.csv", limit: int | None = None) -> dict[str, Any]:
    """
    One-click sync: pulls prospects from existing MySQL and writes to data/prospects.csv
    so the rest of the platform (local event store mapping, exports, etc.) works.
    """
    cfg = _mysql_cfg_from_env()
    if not cfg.database:
        raise HTTPException(status_code=400, detail="Missing LNC_MYSQL_DATABASE env var")
    stores = MySQLStores(cfg)
    prospects = stores.list_prospects(limit=limit)
    rows = [
        {
            "id": p.id,
            "email": p.email,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "company": p.company,
            "role": p.role,
            "industry": p.industry,
            "provider": p.provider,
            "status": p.status,
            "last_contacted_day": p.last_contacted_day,
        }
        for p in prospects
    ]
    out_path = _abs(out_csv)
    _write_prospects_csv(out_path, rows)
    return {"ok": True, "path": str(out_path), "prospects": len(prospects)}


@app.post("/api/import/prospects")
async def import_prospects(file: UploadFile = File(...)) -> dict[str, Any]:
    name = (file.filename or "").lower()
    if not name.endswith(".csv"):
        raise HTTPException(status_code=400, detail="prospects file must be a .csv")
    data_dir = _abs("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "prospects.csv"
    content = await file.read()
    out_path.write_bytes(content)
    # validate shape quickly by attempting to parse
    prospects = read_prospects(out_path)
    return {"ok": True, "path": str(out_path), "prospects": len(prospects)}


@app.post("/api/import/sendgrid-events")
async def import_sendgrid_events(file: UploadFile = File(...)) -> dict[str, Any]:
    name = (file.filename or "").lower()
    if not (name.endswith(".jsonl") or name.endswith(".txt")):
        raise HTTPException(status_code=400, detail="SendGrid events file must be .jsonl")
    data_dir = _abs("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path = data_dir / "sendgrid_events.jsonl"
    content = await file.read()
    out_path.write_bytes(content)
    raw = load_sendgrid_raw_events(out_path)
    return {"ok": True, "path": str(out_path), "events": len(raw)}


@app.post("/api/migrate/sendgrid-events/jsonl-to-mysql")
def migrate_sendgrid_events_jsonl_to_mysql(
    sendgrid_raw_jsonl: str = "data/sendgrid_events.jsonl",
    limit: int | None = None,
) -> dict[str, Any]:
    """
    One-off helper for when you previously stored webhook events locally in JSONL,
    then switched to LNC_EVENT_STORE=mysql.

    It loads the JSONL file and inserts raw payloads into MySQL (dedup is enforced
    by the unique sg_event_id constraint in the DB schema).
    """
    cfg = _mysql_cfg_from_env()
    if not cfg.database:
        raise HTTPException(status_code=400, detail="LNC_MYSQL_DATABASE is required")

    raw = load_sendgrid_raw_events(_abs(sendgrid_raw_jsonl))
    if limit is not None:
        raw = raw[: max(0, int(limit))]

    inserted = MySQLStores(cfg).insert_sendgrid_events(raw)
    return {"ok": True, "source": sendgrid_raw_jsonl, "loaded": len(raw), "inserted": inserted}

