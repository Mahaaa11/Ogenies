import argparse
from pathlib import Path

from .agent import analyze_campaign
from .db import MySQLConfig
from .io import (
    read_events,
    read_prospects,
    write_dashboard,
    write_email_drafts,
    write_recommendations,
)
from .repository import MySQLStores
from .sendgrid_kpis import compute_sendgrid_kpis, load_sendgrid_raw_events
from .send_cli import send_drafts_via_sendgrid
from .report_sendgrid import write_sendgrid_agent_report
from .powerbi_export import PowerBIExportConfig, export_powerbi_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Lead & Connect AI email campaign agent.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Analyze a campaign and generate outputs.")
    run_parser.add_argument("--prospects", required=True, help="Path to prospects CSV.")
    run_parser.add_argument("--events", required=True, help="Path to email events CSV.")
    run_parser.add_argument(
        "--sendgrid-raw",
        default=None,
        help="Optional path to SendGrid raw events JSONL for advanced KPIs.",
    )
    run_parser.add_argument("--out", default="output", help="Output folder.")

    run_mysql = subparsers.add_parser("run-mysql", help="Analyze using MySQL prospects/events tables.")
    run_mysql.add_argument("--mysql-host", required=True)
    run_mysql.add_argument("--mysql-port", type=int, default=3306)
    run_mysql.add_argument("--mysql-user", required=True)
    run_mysql.add_argument("--mysql-password", required=True)
    run_mysql.add_argument("--mysql-database", required=True)
    run_mysql.add_argument("--prospects-table", default="prospects")
    run_mysql.add_argument("--events-table", default="email_events")
    run_mysql.add_argument("--limit-prospects", type=int, default=None)
    run_mysql.add_argument("--limit-events", type=int, default=None)
    run_mysql.add_argument(
        "--sendgrid-raw",
        default=None,
        help="Optional path to SendGrid raw events JSONL for advanced KPIs.",
    )
    run_mysql.add_argument("--out", default="output", help="Output folder.")

    send_parser = subparsers.add_parser("send-sendgrid", help="Send generated drafts via SendGrid.")
    send_parser.add_argument("--prospects", required=True, help="Path to prospects CSV (id,email...).")
    send_parser.add_argument("--drafts", required=True, help="Path to email_drafts.csv produced by the agent.")
    send_parser.add_argument("--api-key", default=None, help="SendGrid API key (or set SENDGRID_API_KEY env).")
    send_parser.add_argument("--limit", type=int, default=1, help="Safety limit: number of emails to send.")
    send_parser.add_argument("--prospect-id", default=None, help="Only send the draft for this prospect_id.")
    send_parser.add_argument("--to-email", default=None, help="Override recipient email (for testing).")

    report_parser = subparsers.add_parser(
        "report-sendgrid",
        help="Generate agent scoring/decision report for recipients found in SendGrid JSONL.",
    )
    report_parser.add_argument("--prospects", required=True, help="Path to prospects CSV.")
    report_parser.add_argument("--sendgrid-raw", required=True, help="Path to SendGrid raw events JSONL.")
    report_parser.add_argument("--out", default="output_sendgrid_report", help="Output folder.")

    pbi = subparsers.add_parser("export-powerbi", help="Export Power BI dataset files (for Service refresh).")
    pbi.add_argument("--prospects", default="data/prospects.csv")
    pbi.add_argument("--recommendations", default="output_fullflow/recommendations.csv")
    pbi.add_argument("--agent-report", default="output_sendgrid_report/sendgrid_agent_report.csv")
    pbi.add_argument("--sendgrid-raw", default="data/sendgrid_events.jsonl")
    pbi.add_argument("--out", default="powerbi_dataset")

    args = parser.parse_args()

    if args.command == "run":
        run_agent(args.prospects, args.events, args.out, sendgrid_raw=args.sendgrid_raw)
    if args.command == "run-mysql":
        run_agent_mysql(
            host=args.mysql_host,
            port=args.mysql_port,
            user=args.mysql_user,
            password=args.mysql_password,
            database=args.mysql_database,
            prospects_table=args.prospects_table,
            events_table=args.events_table,
            limit_prospects=args.limit_prospects,
            limit_events=args.limit_events,
            output_dir=args.out,
            sendgrid_raw=args.sendgrid_raw,
        )
    if args.command == "send-sendgrid":
        results = send_drafts_via_sendgrid(
            prospects_csv=args.prospects,
            drafts_csv=args.drafts,
            api_key=args.api_key,
            limit=args.limit,
            prospect_id=args.prospect_id,
            to_email=args.to_email,
        )
        print(results)
    if args.command == "report-sendgrid":
        out_dir = Path(args.out)
        write_sendgrid_agent_report(
            prospects_csv=args.prospects,
            sendgrid_jsonl=args.sendgrid_raw,
            out_csv=out_dir / "sendgrid_agent_report.csv",
        )
        print(f"Wrote report to {out_dir / 'sendgrid_agent_report.csv'}")
    if args.command == "export-powerbi":
        export_powerbi_dataset(
            PowerBIExportConfig(
                prospects_csv=Path(args.prospects),
                recommendations_csv=Path(args.recommendations),
                agent_report_csv=Path(args.agent_report),
                sendgrid_events_jsonl=Path(args.sendgrid_raw),
                out_dir=Path(args.out),
            )
        )
        print(f"Wrote Power BI dataset to {Path(args.out)}")


def run_agent(prospects_path: str, events_path: str, output_dir: str, sendgrid_raw: str | None) -> None:
    prospects = read_prospects(prospects_path)
    events = read_events(events_path)
    recommendations, email_drafts, dashboard = analyze_campaign(prospects, events)

    if sendgrid_raw:
        raw_events = load_sendgrid_raw_events(Path(sendgrid_raw))
        dashboard.update(
            compute_sendgrid_kpis(
                prospects=prospects,
                recommendations=recommendations,
                raw_events=raw_events,
            )
        )

    output_path = Path(output_dir)
    write_recommendations(output_path / "recommendations.csv", recommendations)
    write_email_drafts(output_path / "email_drafts.csv", email_drafts)
    write_dashboard(output_path / "dashboard.csv", dashboard)

    print(f"Analyzed {len(prospects)} prospects")
    print(f"Wrote outputs to {output_path}")


def run_agent_mysql(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    prospects_table: str,
    events_table: str,
    limit_prospects: int | None,
    limit_events: int | None,
    output_dir: str,
    sendgrid_raw: str | None,
) -> None:
    stores = MySQLStores(
        MySQLConfig(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            prospects_table=prospects_table,
            events_table=events_table,
        )
    )
    prospects = stores.list_prospects(limit=limit_prospects)
    events = stores.list_events(limit=limit_events)
    recommendations, email_drafts, dashboard = analyze_campaign(prospects, events)

    if sendgrid_raw:
        raw_events = load_sendgrid_raw_events(Path(sendgrid_raw))
        dashboard.update(
            compute_sendgrid_kpis(
                prospects=prospects,
                recommendations=recommendations,
                raw_events=raw_events,
            )
        )

    output_path = Path(output_dir)
    write_recommendations(output_path / "recommendations.csv", recommendations)
    write_email_drafts(output_path / "email_drafts.csv", email_drafts)
    write_dashboard(output_path / "dashboard.csv", dashboard)

    print(f"Analyzed {len(prospects)} prospects (MySQL)")
    print(f"Wrote outputs to {output_path}")


if __name__ == "__main__":
    main()
