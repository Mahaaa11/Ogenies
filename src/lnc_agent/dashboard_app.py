from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st


@dataclass(frozen=True)
class Paths:
    dashboard_csv: Path
    recommendations_csv: Path
    sendgrid_agent_report_csv: Path
    sendgrid_events_jsonl: Path


def main() -> None:
    st.set_page_config(page_title="L&C Emailing — KPI & Agent Dashboard", layout="wide")
    st.title("Vue d’ensemble — KPI & Agent IA")

    paths = _sidebar_paths()

    dashboard = _load_dashboard_metrics(paths.dashboard_csv)
    recs = _load_csv(paths.recommendations_csv)
    report = _load_csv(paths.sendgrid_agent_report_csv)
    sg = _load_sendgrid_jsonl(paths.sendgrid_events_jsonl)

    col1, col2, col3, col4 = st.columns(4)
    _metric(col1, "Taux d’ouverture", _fmt_pct(dashboard.get("kpi_taux_ouverture_pct")))
    _metric(col2, "Taux de clic (CTR unique)", _fmt_pct(dashboard.get("kpi_ctr_unique_pct")))
    _metric(col3, "Désinscriptions", str(int(dashboard.get("unsubscribe_events", 0) or 0)))
    _metric(col4, "Plaintes spam", str(int(dashboard.get("spam_events", 0) or 0)))

    st.divider()

    left, right = st.columns([1.6, 1.0])
    with left:
        st.subheader("Évolution des performances (événements SendGrid)")
        st.caption("Ouvertures & clics par jour (d’après `sendgrid_events.jsonl`).")
        trend = _opens_clicks_trend(sg)
        if trend is not None and not trend.empty:
            fig = px.line(trend, x="date", y=["opens", "clicks"], markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucun événement SendGrid exploitable pour la courbe (open/click).")

    with right:
        st.subheader("Engagement utilisateur")
        st.caption("Rapidité de clic = clic ≤ 1h après délivré (même message).")
        _metric(st, "Temps moyen avant clic (sec)", _fmt_num(dashboard.get("kpi_rapid_click_avg_seconds")))
        _metric(st, "Rapidité de clic", _fmt_pct(dashboard.get("kpi_rapid_click_rate_pct")))

    st.divider()

    c1, c2, c3 = st.columns([1.0, 1.0, 1.0])
    with c1:
        st.subheader("Délivrabilité")
        delivered = int(dashboard.get("kpi_emails_delivres", 0) or 0)
        bounced = int(dashboard.get("kpi_hard_bounce", 0) or 0) + int(dashboard.get("kpi_soft_bounce", 0) or 0)
        dropped = int(dashboard.get("kpi_dropped", 0) or 0)
        donut = pd.DataFrame(
            [
                {"status": "Délivrés", "count": delivered},
                {"status": "Bounces", "count": bounced},
                {"status": "Dropped", "count": dropped},
            ]
        )
        fig = px.pie(donut, names="status", values="count", hole=0.6)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Taux de délivrabilité: {_fmt_pct(dashboard.get('kpi_taux_delivrabilite_pct'))}")

    with c2:
        st.subheader("Performance par messagerie")
        provider_json = dashboard.get("kpi_performance_par_fournisseur_json")
        providers = _maybe_json_to_df(provider_json, orient="index")
        if providers is not None and not providers.empty:
            providers = providers.reset_index(names=["fournisseur"]).sort_values("delivered", ascending=False)
            st.dataframe(providers, use_container_width=True, hide_index=True)
        else:
            st.info("Pas assez de données pour la performance par messagerie (Gmail, Outlook, etc.).")

    with c3:
        st.subheader("Répartition des scores d’intérêt")
        if not recs.empty and "score" in recs.columns:
            recs["score_bucket"] = pd.cut(
                pd.to_numeric(recs["score"], errors="coerce").fillna(0),
                bins=[-1, 29, 69, 100],
                labels=["Froids (<30)", "Tièdes (30–69)", "Chauds (≥70)"],
            )
            dist = recs["score_bucket"].value_counts().reindex(["Chauds (≥70)", "Tièdes (30–69)", "Froids (<30)"]).fillna(0)
            fig = px.bar(dist.reset_index(), x="score_bucket", y="count")
            st.plotly_chart(fig, use_container_width=True)
            _metric(st, "Score moyen", _fmt_num(dashboard.get("avg_interest_score")))
        else:
            st.info("Aucune recommandation/score à afficher (fichier manquant).")

    st.divider()

    l2, r2 = st.columns([1.6, 1.0])
    with l2:
        st.subheader("Aperçu des campagnes / recommandations")
        if not recs.empty:
            st.dataframe(
                recs[["prospect_id", "score", "segment", "next_action", "campaign_step", "reason"]].head(50),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("`recommendations.csv` introuvable ou vide.")

    with r2:
        st.subheader("Top prospects (scores)")
        if not recs.empty and "score" in recs.columns:
            top = recs.sort_values("score", ascending=False).head(10)
            st.dataframe(top[["prospect_id", "score", "segment", "next_action"]], use_container_width=True, hide_index=True)
        else:
            st.info("Aucun score disponible.")

    st.divider()

    st.subheader("Tracking “emails envoyés” (SendGrid + décisions IA)")
    if not report.empty:
        st.dataframe(report, use_container_width=True, hide_index=True)
    else:
        st.info("Générez le fichier via `python -m src.lnc_agent.cli report-sendgrid ...`.")


def _sidebar_paths() -> Paths:
    st.sidebar.header("Sources de données")
    base = st.sidebar.text_input("Dossier output", value="output_real_sendgrid_rapid1h")
    base_path = Path(base)

    dashboard_csv = st.sidebar.text_input("dashboard.csv", value=str(base_path / "dashboard.csv"))
    recommendations_csv = st.sidebar.text_input("recommendations.csv", value=str(base_path / "recommendations.csv"))
    report_csv = st.sidebar.text_input(
        "sendgrid_agent_report.csv",
        value="output_sendgrid_report/sendgrid_agent_report.csv",
    )
    jsonl = st.sidebar.text_input("sendgrid_events.jsonl", value="data/sendgrid_events.jsonl")

    return Paths(
        dashboard_csv=Path(dashboard_csv),
        recommendations_csv=Path(recommendations_csv),
        sendgrid_agent_report_csv=Path(report_csv),
        sendgrid_events_jsonl=Path(jsonl),
    )


def _load_csv(path: Path) -> pd.DataFrame:
    try:
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_dashboard_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
        if "metric" not in df.columns or "value" not in df.columns:
            return {}
        out: dict[str, Any] = {}
        for _, row in df.iterrows():
            out[str(row["metric"])] = _coerce_number(row["value"])
        return out
    except Exception:
        return {}


def _load_sendgrid_jsonl(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True, errors="coerce")
        df["date"] = df["dt"].dt.date.astype(str)
    return df


def _opens_clicks_trend(sg: pd.DataFrame) -> pd.DataFrame | None:
    if sg.empty or "event" not in sg.columns or "date" not in sg.columns:
        return None
    sub = sg[sg["event"].isin(["open", "click"])].copy()
    if sub.empty:
        return None
    g = sub.groupby(["date", "event"]).size().unstack(fill_value=0).reset_index()
    if "open" not in g.columns:
        g["open"] = 0
    if "click" not in g.columns:
        g["click"] = 0
    g = g.rename(columns={"open": "opens", "click": "clicks"})
    return g.sort_values("date")


def _maybe_json_to_df(value: Any, orient: str) -> pd.DataFrame | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None
    try:
        obj = json.loads(value) if isinstance(value, str) else value
        if isinstance(obj, dict):
            return pd.DataFrame.from_dict(obj, orient=orient)
        if isinstance(obj, list):
            return pd.DataFrame(obj)
        return None
    except Exception:
        return None


def _metric(container: Any, label: str, value: str) -> None:
    try:
        container.metric(label, value)
    except Exception:
        st.metric(label, value)


def _fmt_pct(v: Any) -> str:
    try:
        if v is None:
            return "—"
        return f"{float(v):.2f}%"
    except Exception:
        return "—"


def _fmt_num(v: Any) -> str:
    try:
        if v is None:
            return "—"
        f = float(v)
        if abs(f - round(f)) < 1e-9:
            return str(int(round(f)))
        return f"{f:.2f}"
    except Exception:
        return "—"


def _coerce_number(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    try:
        if "." in s:
            return float(s)
        return int(s)
    except Exception:
        return v


if __name__ == "__main__":
    main()

