"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import { PageHero } from "@/components/ui/page-hero";

type ReportResp = { ok: boolean; out_csv: string };

export default function ActionsPage() {
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string>("");
  const [mysqlSyncLimit, setMysqlSyncLimit] = useState<string>("");

  async function syncProspectsFromMysql() {
    setBusy(true);
    setLog("");
    try {
      const q = mysqlSyncLimit.trim() ? `?limit=${encodeURIComponent(mysqlSyncLimit.trim())}` : "";
      const res = await apiPost(`/api/sync/prospects/mysql${q}`);
      setLog(JSON.stringify(res, null, 2));
    } catch (e) {
      setLog(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  async function report() {
    setBusy(true);
    setLog("");
    try {
      const res = await apiPost<ReportResp>(
        "/api/report/sendgrid?prospects_csv=data/prospects.csv&sendgrid_raw_jsonl=data/sendgrid_events.jsonl&out_csv=output_platform/sendgrid_agent_report.csv",
      );
      setLog(JSON.stringify(res, null, 2));
    } catch (e) {
      setLog(e instanceof Error ? e.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHero
        variant="cyan"
        eyebrow="Automatisation"
        title="Actions"
        description="Synchronisez les prospects depuis MySQL, régénérez le rapport SendGrid et branchez le webhook — tout le reste du cockpit se met à jour."
      />

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="group relative overflow-hidden rounded-3xl border-0 bg-white p-6 shadow-2xl ring-1 ring-cyan-200/60">
          <div className="absolute inset-0 bg-gradient-to-br from-[color:var(--brand-blue)]/10 via-transparent to-[color:var(--brand-yellow)]/10 opacity-0 transition group-hover:opacity-100" />
          <div className="relative">
            <div className="inline-flex rounded-full bg-gradient-to-r from-cyan-500 to-[color:var(--brand-blue)] px-3 py-1 text-[10px] font-black uppercase tracking-wider text-white shadow-md">
              MySQL
            </div>
            <div className="mt-3 text-lg font-black text-zinc-900">Sync prospects</div>
            <div className="mt-1 text-sm text-zinc-600">
              Récupère automatiquement vos prospects (aucun fichier à importer).
            </div>
            <div className="mt-4 flex flex-col gap-3">
              <input
                value={mysqlSyncLimit}
                onChange={(e) => setMysqlSyncLimit(e.target.value)}
                placeholder="limit (optionnel)"
                className="w-full rounded-2xl border-2 border-cyan-200/70 bg-cyan-50/30 px-4 py-3 text-sm font-medium outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-200"
              />
              <button
                onClick={syncProspectsFromMysql}
                disabled={busy}
                className="rounded-2xl bg-gradient-to-r from-cyan-500 to-[color:var(--brand-blue-deep)] px-5 py-3 text-left text-sm font-bold text-white shadow-lg transition hover:brightness-110 disabled:opacity-50"
              >
                {busy ? "Synchronisation…" : "Sync maintenant →"}
              </button>
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={report}
          disabled={busy}
          className="group relative overflow-hidden rounded-3xl border-0 bg-gradient-to-br from-[color:var(--brand-blue-deep)] via-[color:var(--brand-orange)] to-[color:var(--brand-yellow)] p-6 text-left shadow-2xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_25%,transparent)] transition hover:brightness-105 disabled:opacity-50"
        >
          <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/20 blur-2xl" />
          <div className="relative text-white">
            <div className="text-[10px] font-black uppercase tracking-[0.2em] text-white/75">Pipeline</div>
            <div className="mt-2 text-xl font-black">Générer le rapport</div>
            <div className="mt-2 text-sm text-white/85">
              Consolide webhooks, scoring IA, tracking & campagnes.
            </div>
            <div className="mt-5 inline-flex items-center gap-2 rounded-full bg-white/20 px-4 py-2 text-xs font-bold ring-1 ring-white/30">
              {busy ? "En cours…" : "Cliquer pour exécuter"}
            </div>
          </div>
        </button>
      </div>

      <div className="overflow-hidden rounded-3xl border-0 bg-white shadow-xl ring-1 ring-amber-200/50">
        <div className="bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-3 text-white">
          <div className="text-sm font-black tracking-tight">Webhook SendGrid</div>
          <div className="text-xs text-amber-100">Automatique — pas d’upload manuel.</div>
        </div>
        <div className="bg-gradient-to-b from-amber-50/40 to-white p-5">
          <p className="text-sm text-zinc-700">
            Configurez l’Event Webhook vers{" "}
            <span className="break-all rounded-lg bg-zinc-900 px-2 py-1 font-mono text-xs text-[color:var(--brand-blue-sky)]">
              {(process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000")}/webhooks/sendgrid/events
            </span>
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-3xl border-0 bg-zinc-950 shadow-2xl ring-1 ring-zinc-700">
        <div className="border-b border-zinc-800 bg-gradient-to-r from-zinc-900 to-zinc-800 px-5 py-3">
          <div className="text-sm font-bold text-white">Logs</div>
        </div>
        <pre className="max-h-[360px] overflow-auto p-5 text-xs leading-relaxed text-[color:var(--brand-blue-sky)]">
          {log || "—"}
        </pre>
      </div>
    </div>
  );
}
