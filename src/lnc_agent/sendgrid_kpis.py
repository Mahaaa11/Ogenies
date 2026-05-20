from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Prospect, Recommendation


@dataclass(frozen=True)
class SendGridKPIConfig:
    raw_events_jsonl: Path


def compute_sendgrid_trend_by_day(*, raw_events: list[dict[str, Any]]) -> list[dict[str, int | str]]:
    """
    Build a simple time series grouped by UTC day.
    Intended for the dashboard trend chart.

    Output points (per UTC day):
      {
        "date": "YYYY-MM-DD",
        "delivered": <unique (email,msg_id) delivered>,
        "opens": <unique (email,msg_id) opens>,
        "clicks": <total click events>,
        "unsubscribes": <total unsubscribe-like events>,
        "spams": <total spamreport-like events>,
      }
    """
    norm = [_norm_event(e) for e in raw_events]
    by_day: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "delivered_keys": set(),
            "open_keys": set(),
            "clicks": 0,
            "unsubscribes": 0,
            "spams": 0,
        }
    )

    for e in norm:
        ts = int(e.get("ts") or 0)
        if ts <= 0:
            continue
        day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        ev = e["event"]
        if ev == "delivered":
            by_day[day]["delivered_keys"].add((e["email"], e["msg_id"] or ""))
        elif ev == "open":
            by_day[day]["open_keys"].add((e["email"], e["msg_id"] or ""))
        elif ev == "click":
            by_day[day]["clicks"] += 1
        elif ev in ("unsubscribe", "unsubscribed", "group_unsubscribe"):
            by_day[day]["unsubscribes"] += 1
        elif ev in ("spamreport", "spam"):
            by_day[day]["spams"] += 1

    out: list[dict[str, int | str]] = []
    for day in sorted(by_day.keys()):
        b = by_day[day]
        out.append(
            {
                "date": day,
                "delivered": len(b["delivered_keys"]),
                "opens": len(b["open_keys"]),
                "clicks": int(b["clicks"]),
                "unsubscribes": int(b["unsubscribes"]),
                "spams": int(b["spams"]),
            }
        )
    return out


def compute_sendgrid_trend_by_phase(*, raw_events: list[dict[str, Any]]) -> list[dict[str, int | str]]:
    """
    Group events by SendGrid custom_args.send_batch_id ("phase") and compute one
    point per phase with the same shape as `compute_sendgrid_trend_by_day`.

    If send_batch_id is missing, events fall into "phase-1".
    """
    norm = [_norm_event(e) for e in raw_events]

    def phase_id(ev_raw: dict[str, Any]) -> str:
        ca = ev_raw.get("custom_args") or ev_raw.get("unique_args") or {}
        if isinstance(ca, dict):
            v = str(ca.get("send_batch_id") or "").strip()
            if v:
                return v
        return "phase-1"

    by_phase: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "delivered_keys": set(),
            "open_keys": set(),
            "clicks": 0,
            "unsubscribes": 0,
            "spams": 0,
            "max_ts": 0,
        }
    )
    for raw, e in zip(raw_events, norm):
        pid = phase_id(raw)
        ts = int(e.get("ts") or 0)
        by_phase[pid]["max_ts"] = max(int(by_phase[pid]["max_ts"]), ts)
        ev = e["event"]
        if ev == "delivered":
            by_phase[pid]["delivered_keys"].add((e["email"], e["msg_id"] or ""))
        elif ev == "open":
            by_phase[pid]["open_keys"].add((e["email"], e["msg_id"] or ""))
        elif ev == "click":
            by_phase[pid]["clicks"] += 1
        elif ev in ("unsubscribe", "unsubscribed", "group_unsubscribe"):
            by_phase[pid]["unsubscribes"] += 1
        elif ev in ("spamreport", "spam"):
            by_phase[pid]["spams"] += 1

    rows = []
    for pid, v in by_phase.items():
        rows.append(
            (
                int(v["max_ts"]),
                {
                    "date": pid,
                    "delivered": len(v["delivered_keys"]),
                    "opens": len(v["open_keys"]),
                    "clicks": int(v["clicks"]),
                    "unsubscribes": int(v["unsubscribes"]),
                    "spams": int(v["spams"]),
                },
            )
        )
    rows.sort(key=lambda t: (t[0], t[1]["date"]))
    return [r for _ts, r in rows]


def load_sendgrid_raw_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


def compute_sendgrid_kpis(
    *,
    prospects: list[Prospect],
    recommendations: list[Recommendation],
    raw_events: list[dict[str, Any]],
) -> dict[str, int | float | str]:
    """
    Computes KPI set from Twilio SendGrid Event Webhook raw payloads.
    Best-effort: fields vary by configuration (geo/useragent/custom_args).
    """
    base_total = len(prospects)
    unsubscribed_in_base = sum(1 for p in prospects if p.status.lower() == "unsubscribed")

    # Normalize events
    norm = [_norm_event(e) for e in raw_events]

    processed = [e for e in norm if e["event"] in ("processed", "sent")]
    delivered = [e for e in norm if e["event"] == "delivered"]
    dropped = [e for e in norm if e["event"] == "dropped"]
    deferred = [e for e in norm if e["event"] == "deferred"]
    opens = [e for e in norm if e["event"] == "open"]
    clicks = [e for e in norm if e["event"] == "click"]
    unsub = [e for e in norm if e["event"] in ("unsubscribe", "unsubscribed", "group_unsubscribe")]
    spam = [e for e in norm if e["event"] in ("spamreport", "spam")]
    bounces = [e for e in norm if e["event"] == "bounce"]

    hard_bounce = [e for e in bounces if e.get("bounce_kind") == "hard"]
    soft_bounce = [e for e in bounces if e.get("bounce_kind") == "soft"]

    # IMPORTANT: count unique (email,msg_id) to avoid inflated totals from retries/history.
    processed_keys = {(e["email"], e["msg_id"] or "") for e in processed}
    delivered_keys = {(e["email"], e["msg_id"] or "") for e in delivered}
    processed_n = len(processed_keys)
    delivered_n = len(delivered_keys)

    # Unique opens/clicks: per email per message id (fallback to email only)
    unique_open_keys = {(e["email"], e["msg_id"] or "") for e in opens}
    unique_click_keys = {(e["email"], e["msg_id"] or "", e.get("url") or "") for e in clicks}
    unique_open_n = len(unique_open_keys)
    unique_click_n = len({(k[0], k[1]) for k in unique_click_keys})

    total_open_n = len(opens)
    total_click_n = len(clicks)

    def rate(num: int, den: int) -> float:
        return round((num / den) * 100, 2) if den else 0.0

    # KPI performance email
    deliverability_rate = rate(delivered_n, processed_n)
    # Per your definitions: use UNIQUE rates as the official ones.
    open_rate_unique = rate(unique_open_n, delivered_n)
    open_rate_total = rate(total_open_n, delivered_n)

    ctr_unique = rate(unique_click_n, delivered_n)
    ctr_total = rate(total_click_n, delivered_n)

    ctor_unique = rate(unique_click_n, unique_open_n)
    ctor_total = rate(total_click_n, total_open_n)

    # KPI qualité/risques
    unsubscribe_rate = rate(len(unsub), delivered_n)
    spam_rate = rate(len(spam), delivered_n)
    hard_bounce_n = len(hard_bounce)
    soft_bounce_n = len(soft_bounce)
    bounce_global_rate = rate(len(bounces), processed_n)
    dropped_rate = rate(len(dropped), processed_n)

    # KPI base / segments
    perf_by_segment = _segment_performance(recommendations, opens, clicks, delivered)

    # Technical KPI
    opens_by_hour = _by_hour(opens)
    clicks_by_hour = _by_hour(clicks)
    device_split = _device_split(opens)
    client_split = _client_split(opens)
    geo_top = _geo_top(opens, limit=10)

    # A/B testing
    ab_perf = _ab_performance(opens, clicks, delivered)

    # Advanced KPI
    engagement_by_contact = {f"engagement_score_{r.prospect.id}": r.score for r in recommendations}
    heatmap_clicks = _top_click_urls(clicks, limit=10)
    provider_perf = _provider_performance(opens, delivered, spam)
    rapid = _rapid_click_kpis(delivered, clicks, window_seconds=3600)
    quality_score = _quality_score(
        deliverability_rate=deliverability_rate,
        open_rate=open_rate_unique,
        spam_rate=spam_rate,
        bounce_global_rate=bounce_global_rate,
        unsubscribe_rate=unsubscribe_rate,
    )

    out: dict[str, int | float | str] = {
        # 1) Performance
        "kpi_emails_envoyes": processed_n,
        "kpi_emails_delivres": delivered_n,
        "kpi_taux_delivrabilite_pct": deliverability_rate,
        "kpi_taux_ouverture_pct": open_rate_unique,
        "kpi_taux_ouverture_total_pct": open_rate_total,
        "kpi_ouvertures_uniques": unique_open_n,
        "kpi_ouvertures_totales": total_open_n,
        "kpi_ctr_pct": ctr_unique,
        "kpi_ctr_total_pct": ctr_total,
        "kpi_ctr_unique_pct": ctr_unique,
        "kpi_clics_totaux": total_click_n,
        "kpi_ctor_pct": ctor_unique,
        "kpi_ctor_total_pct": ctor_total,
        # 2) Qualité / risques
        "kpi_taux_desinscription_pct": unsubscribe_rate,
        "kpi_taux_plaintes_spam_pct": spam_rate,
        "kpi_hard_bounce": hard_bounce_n,
        "kpi_soft_bounce": soft_bounce_n,
        "kpi_taux_bounce_global_pct": bounce_global_rate,
        "kpi_dropped": len(dropped),
        "kpi_deferred": len(deferred),
        "kpi_taux_dropped_pct": dropped_rate,
        # 3) Base de données
        "kpi_base_totale": base_total,
        "kpi_desabonnes_base": unsubscribed_in_base,
        "kpi_performance_par_segment_json": json.dumps(perf_by_segment, ensure_ascii=False),
        # 4) Techniques
        "kpi_mobile_vs_desktop_json": json.dumps(device_split, ensure_ascii=False),
        "kpi_webmail_vs_app_json": json.dumps(client_split, ensure_ascii=False),
        "kpi_pays_ville_ouverture_top_json": json.dumps(geo_top, ensure_ascii=False),
        "kpi_heure_ouverture_json": json.dumps(opens_by_hour, ensure_ascii=False),
        "kpi_heure_clic_json": json.dumps(clicks_by_hour, ensure_ascii=False),
        # 5) A/B testing
        "kpi_ab_testing_json": json.dumps(ab_perf, ensure_ascii=False),
        # 6) Avancés
        "kpi_heatmap_clic_top_urls_json": json.dumps(heatmap_clicks, ensure_ascii=False),
        "kpi_performance_par_fournisseur_json": json.dumps(provider_perf, ensure_ascii=False),
        "kpi_rapid_clicks": rapid["rapid_clicks"],
        "kpi_rapid_click_rate_pct": rapid["rapid_click_rate_pct"],
        "kpi_rapid_click_avg_seconds": rapid["rapid_click_avg_seconds"],
        "kpi_score_qualite": quality_score,
    }
    # Keep per-contact engagement scores separate to avoid huge JSON in the main dict.
    out.update(engagement_by_contact)
    return out


def _norm_event(ev: dict[str, Any]) -> dict[str, Any]:
    email = str(ev.get("email") or "").strip().lower()
    event = str(ev.get("event") or ev.get("event_type") or "").strip().lower()
    ts = _as_int(ev.get("timestamp") or ev.get("ts"), 0)
    msg_id = str(ev.get("sg_message_id") or ev.get("smtp-id") or ev.get("message_id") or "").strip()
    url = str(ev.get("url") or "").strip()
    useragent = str(ev.get("useragent") or ev.get("user_agent") or "").strip()
    country = str(ev.get("country") or "").strip()
    city = str(ev.get("city") or "").strip()

    # Bounce details vary; best-effort.
    bounce_kind = ""
    bt = str(ev.get("type") or ev.get("bounce_type") or ev.get("bounce_classification") or "").lower()
    if "hard" in bt:
        bounce_kind = "hard"
    elif "soft" in bt:
        bounce_kind = "soft"

    variant = _extract_variant(ev)

    return {
        "email": email,
        "event": event,
        "ts": ts,
        "hour": _hour(ts),
        "msg_id": msg_id,
        "url": url,
        "useragent": useragent,
        "country": country,
        "city": city,
        "bounce_kind": bounce_kind,
        "variant": variant,
    }


def _extract_variant(ev: dict[str, Any]) -> str:
    # If you later send with custom_args {variant:"A"} it will land in the event payload.
    v = ev.get("variant")
    if isinstance(v, str) and v.strip():
        return v.strip().upper()
    ca = ev.get("custom_args") or ev.get("unique_args") or {}
    if isinstance(ca, dict):
        v2 = ca.get("variant")
        if isinstance(v2, str) and v2.strip():
            return v2.strip().upper()
    # Fallback: parse ?v=A from click URL
    url = str(ev.get("url") or "")
    if "v=A" in url or "v=a" in url:
        return "A"
    if "v=B" in url or "v=b" in url:
        return "B"
    return ""


def _segment_performance(
    recommendations: list[Recommendation],
    opens: list[dict[str, Any]],
    clicks: list[dict[str, Any]],
    delivered: list[dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    # We only have email on SendGrid events, so segment mapping is best-effort:
    # if your Prospect.email matches SendGrid email, it will work.
    email_to_segment = {r.prospect.email.strip().lower(): r.segment for r in recommendations if r.prospect.email}
    seg_counts = defaultdict(lambda: {"delivered": 0, "unique_opens": 0, "unique_clicks": 0})

    # Dedup delivered by (email, msg_id) to match the global kpi_emails_delivres
    # definition and to stay consistent with the unique opens/clicks below.
    unique_delivered = {(e["email"], e["msg_id"] or "") for e in delivered if e["email"]}
    for em, _mid in unique_delivered:
        seg = email_to_segment.get(em, "unknown")
        seg_counts[seg]["delivered"] += 1

    unique_open = {(e["email"], e["msg_id"] or "") for e in opens if e["email"]}
    for em, _mid in unique_open:
        seg = email_to_segment.get(em, "unknown")
        seg_counts[seg]["unique_opens"] += 1

    unique_click = {(e["email"], e["msg_id"] or "") for e in clicks if e["email"]}
    for em, _mid in unique_click:
        seg = email_to_segment.get(em, "unknown")
        seg_counts[seg]["unique_clicks"] += 1

    out: dict[str, dict[str, float | int]] = {}
    for seg, c in seg_counts.items():
        d = int(c["delivered"])
        ou = int(c["unique_opens"])
        cl = int(c["unique_clicks"])
        out[seg] = {
            "delivered": d,
            "open_rate_pct": round((ou / d) * 100, 2) if d else 0.0,
            "click_rate_pct": round((cl / d) * 100, 2) if d else 0.0,
            "ctor_pct": round((cl / ou) * 100, 2) if ou else 0.0,
        }
    return out


def _by_hour(events: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter(str(e.get("hour", 0)) for e in events)
    # stable 0..23
    return {str(h): int(c.get(str(h), 0)) for h in range(24)}


def _device_split(opens: list[dict[str, Any]]) -> dict[str, int]:
    mobile = 0
    desktop = 0
    unknown = 0
    for e in opens:
        ua = (e.get("useragent") or "").lower()
        if not ua:
            unknown += 1
        elif any(k in ua for k in ("iphone", "android", "mobile", "ipad")):
            mobile += 1
        else:
            desktop += 1
    return {"mobile": mobile, "desktop": desktop, "unknown": unknown}


def _client_split(opens: list[dict[str, Any]]) -> dict[str, int]:
    # Best-effort "webmail vs app" using useragent hints.
    webmail = 0
    app = 0
    unknown = 0
    for e in opens:
        ua = (e.get("useragent") or "").lower()
        if not ua:
            unknown += 1
        elif any(k in ua for k in ("gmail", "outlook", "yahoo", "hotmail", "roundcube", "zimbra", "webmail")):
            webmail += 1
        elif any(k in ua for k in ("applemail", "thunderbird", "mail/", "spark", "airmail")):
            app += 1
        else:
            unknown += 1
    return {"webmail": webmail, "application": app, "unknown": unknown}


def _geo_top(opens: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    c = Counter((e.get("country") or "", e.get("city") or "") for e in opens)
    out = []
    for (country, city), n in c.most_common(limit):
        if not country and not city:
            continue
        out.append({"country": country, "city": city, "opens": int(n)})
    return out


def _ab_performance(
    opens: list[dict[str, Any]],
    clicks: list[dict[str, Any]],
    delivered: list[dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    def group_by_variant(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        g: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for it in items:
            v = (it.get("variant") or "").strip().upper() or "unknown"
            g[v].append(it)
        return dict(g)

    d = group_by_variant(delivered)
    o = group_by_variant(opens)
    c = group_by_variant(clicks)

    variants = sorted(set(d.keys()) | set(o.keys()) | set(c.keys()))
    out: dict[str, dict[str, float | int]] = {}
    for v in variants:
        # Dedup delivered by (email, msg_id) to match the global delivered KPI
        # and to stay consistent with unique opens/clicks below.
        delivered_n = len({(e["email"], e["msg_id"] or "") for e in d.get(v, []) if e.get("email")})
        unique_opens = len({(e["email"], e["msg_id"] or "") for e in o.get(v, []) if e.get("email")})
        unique_clicks = len({(e["email"], e["msg_id"] or "") for e in c.get(v, []) if e.get("email")})
        out[v] = {
            "delivered": delivered_n,
            "open_rate_pct": round((unique_opens / delivered_n) * 100, 2) if delivered_n else 0.0,
            "click_rate_pct": round((unique_clicks / delivered_n) * 100, 2) if delivered_n else 0.0,
            "ctor_pct": round((unique_clicks / unique_opens) * 100, 2) if unique_opens else 0.0,
        }
    return out


def _top_click_urls(clicks: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    c = Counter(e.get("url") or "" for e in clicks)
    out = []
    for url, n in c.most_common(limit):
        if not url:
            continue
        out.append({"url": url, "clicks": int(n)})
    return out


# (suffixe du domaine, libellé fournisseur) — ordre géré par longueur de suffixe décroissante.
_MAIL_PROVIDER_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Gmail", ("googlemail.com", "gmail.com")),
    (
        "Outlook / Microsoft",
        (
            "hotmail.co.uk",
            "hotmail.fr",
            "hotmail.de",
            "hotmail.es",
            "hotmail.it",
            "hotmail.com",
            "outlook.co.uk",
            "outlook.fr",
            "outlook.de",
            "outlook.es",
            "outlook.it",
            "outlook.jp",
            "outlook.com",
            "live.co.uk",
            "live.fr",
            "live.nl",
            "live.de",
            "live.com",
            "msn.com",
        ),
    ),
    (
        "Yahoo",
        (
            "yahoo.com.br",
            "yahoo.co.jp",
            "yahoo.co.uk",
            "yahoo.com.au",
            "yahoo.de",
            "yahoo.es",
            "yahoo.it",
            "yahoo.ca",
            "yahoo.fr",
            "yahoo.com",
            "ymail.com",
            "rocketmail.com",
        ),
    ),
    ("iCloud / Apple", ("icloud.com", "me.com", "mac.com")),
    ("AOL", ("aol.com", "aol.fr")),
    ("Proton Mail", ("protonmail.com", "proton.me", "pm.me")),
    ("GMX", ("gmx.fr", "gmx.de", "gmx.net", "gmx.com", "gmx.at", "gmx.ch")),
    ("Web.de", ("web.de",)),
    ("Zoho", ("zohomail.in", "zoho.com", "zohomail.com")),
    ("Orange", ("orange.fr", "wanadoo.fr")),
    ("Free", ("free.fr",)),
    ("SFR", ("sfr.fr",)),
    ("Bouygues / Bbox", ("bbox.fr",)),
    ("La Poste", ("laposte.net", "laposte.fr")),
    ("Neuf / Numéricable", ("neuf.fr",)),
    ("Mail.com", ("mail.com",)),
    ("Tutanota / Tutao", ("tutanota.com", "tuta.io", "keemail.me")),
    ("Fastmail", ("fastmail.com", "fastmail.fm", "messagingengine.com")),
    ("Yandex", ("yandex.com", "yandex.ru", "ya.ru")),
    ("Mail.ru", ("mail.ru", "inbox.ru", "list.ru", "bk.ru")),
    ("Seznam", ("seznam.cz", "email.cz")),
    ("Skynet", ("skynet.be",)),
    ("Bluewin", ("bluewin.ch",)),
    ("Posteo", ("posteo.de", "posteo.net")),
    ("Caramail (legacy)", ("caramail.fr",)),
)


def _mail_provider_rules() -> list[tuple[str, str]]:
    flat: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, suffixes in _MAIL_PROVIDER_GROUPS:
        for s in suffixes:
            s = s.lower()
            if s in seen:
                continue
            seen.add(s)
            flat.append((s, label))
    flat.sort(key=lambda x: len(x[0]), reverse=True)
    return flat


_MAIL_PROVIDER_RULES: list[tuple[str, str]] = _mail_provider_rules()


def mail_provider_label_from_domain(domain: str) -> str:
    """
    Libellé « fournisseur de messagerie » à partir du domaine de l’adresse (partie après @).
    Les webmails / ISP courants → nom lisible ; sinon « Autre · domaine ».
    """
    d = (domain or "").strip().lower()
    if not d:
        return "Inconnu"
    for suffix, label in _MAIL_PROVIDER_RULES:
        if d == suffix or d.endswith("." + suffix):
            return label
    return f"Autre · {d}"


def _provider_performance(
    opens: list[dict[str, Any]],
    delivered: list[dict[str, Any]],
    spam: list[dict[str, Any]],
) -> dict[str, dict[str, float | int]]:
    def domain(email: str) -> str:
        if "@" not in email:
            return ""
        return email.split("@", 1)[1].lower()

    def provider_from_email(email: str) -> str:
        return mail_provider_label_from_domain(domain(email))

    # Dedup delivered by (email, msg_id) to match the global delivered KPI and the
    # unique-opens denominator below.
    delivered_by = Counter(
        provider_from_email(e["email"])
        for e in {(e["email"], e["msg_id"] or ""): e for e in delivered if e.get("email")}.values()
    )
    unique_opens_by = Counter(
        provider_from_email(e["email"])
        for e in {(e["email"], e["msg_id"] or ""): e for e in opens if e.get("email")}.values()
    )
    spam_by = Counter(provider_from_email(e["email"]) for e in spam if e.get("email"))

    def sort_key(name: str) -> tuple[int, str]:
        # Webmails connus d’abord (sans préfixe Autre), puis « Autre · », puis Inconnu
        if name == "Inconnu":
            return (2, name)
        if name.startswith("Autre ·"):
            return (1, name)
        return (0, name)

    out: dict[str, dict[str, float | int]] = {}
    for prov in sorted(set(delivered_by) | set(unique_opens_by) | set(spam_by), key=sort_key):
        d_n = int(delivered_by.get(prov, 0))
        o_n = int(unique_opens_by.get(prov, 0))
        s_n = int(spam_by.get(prov, 0))
        out[prov] = {
            "delivered": d_n,
            "open_rate_pct": round((o_n / d_n) * 100, 2) if d_n else 0.0,
            "spam_rate_pct": round((s_n / d_n) * 100, 2) if d_n else 0.0,
        }
    return out


def _quality_score(
    *,
    deliverability_rate: float,
    open_rate: float,
    spam_rate: float,
    bounce_global_rate: float,
    unsubscribe_rate: float,
) -> float:
    # Simple heuristic 0..100 (not a SendGrid official metric)
    score = 100.0
    score -= max(0.0, 100.0 - deliverability_rate) * 0.6
    score -= spam_rate * 2.0
    score -= bounce_global_rate * 1.2
    score -= unsubscribe_rate * 0.8
    score += min(open_rate, 40.0) * 0.2
    return round(max(0.0, min(score, 100.0)), 2)


def _rapid_click_kpis(
    delivered: list[dict[str, Any]],
    clicks: list[dict[str, Any]],
    window_seconds: int,
) -> dict[str, int | float]:
    """
    Rapid click = first click within window_seconds after delivered for the same (email,msg_id).
    """
    delivered_ts: dict[tuple[str, str], int] = {}
    for e in delivered:
        key = (str(e.get("email") or ""), str(e.get("msg_id") or ""))
        ts = _as_int(e.get("ts"), 0)
        if key[0] and ts and (key not in delivered_ts or ts < delivered_ts[key]):
            delivered_ts[key] = ts

    first_click_ts: dict[tuple[str, str], int] = {}
    for e in clicks:
        key = (str(e.get("email") or ""), str(e.get("msg_id") or ""))
        ts = _as_int(e.get("ts"), 0)
        if key[0] and ts and (key not in first_click_ts or ts < first_click_ts[key]):
            first_click_ts[key] = ts

    rapid_deltas: list[int] = []
    for key, dts in delivered_ts.items():
        cts = first_click_ts.get(key)
        if not cts:
            continue
        delta = cts - dts
        if 0 <= delta <= window_seconds:
            rapid_deltas.append(delta)

    delivered_msgs = len(delivered_ts)
    rapid_clicks = len(rapid_deltas)
    rate_pct = round((rapid_clicks / delivered_msgs) * 100, 2) if delivered_msgs else 0.0
    avg_s = round(sum(rapid_deltas) / rapid_clicks, 2) if rapid_clicks else 0.0
    return {"rapid_clicks": rapid_clicks, "rapid_click_rate_pct": rate_pct, "rapid_click_avg_seconds": avg_s}


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _hour(ts: int) -> int:
    if not ts:
        return 0
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return int(dt.hour)

