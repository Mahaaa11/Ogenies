"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";
import { PageHero } from "@/components/ui/page-hero";

type TrackRow = {
  prospect_id: string;
  email: string;
  sg_message_id: string;
  send_batch_id: string;
  processed: string;
  delivered: string;
  opens: string;
  opens_unique: string;
  clicks: string;
  clicks_unique: string;
  time_spent_seconds: string;
  top_click_url: string;
  clicked_urls_json: string;
  rapid_click_1h: string;
  score: string;
  segment: string;
  next_action: string;
  best_send_weekday: string;
  best_send_hour: string;
  reason: string;
};

type TrackingResp = { ok: boolean; rows: TrackRow[] };
type Scope = "all" | "latest_batch" | "last_24h";

function safeParseUrls(jsonStr: string): string[] {
  try {
    const v = JSON.parse(jsonStr);
    return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function wdName(wd: string): string {
  const n = Number(wd);
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return Number.isFinite(n) && n >= 0 && n <= 6 ? names[n] : "—";
}

export default function TrackingClient() {
  const sp = useSearchParams();
  const [scope, setScope] = useState<Scope>("all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rawRows, setRawRows] = useState<TrackRow[]>([]);

  const qMid = (sp.get("sg_message_id") ?? "").trim();
  const qBatch = (sp.get("send_batch_id") ?? "").trim();
  const qEmail = (sp.get("email") ?? "").trim().toLowerCase();

  async function refresh(nextScope?: Scope) {
    const s = nextScope ?? scope;
    setBusy(true);
    setError(null);
    try {
      await apiPost(`/api/report/sendgrid?scope=${encodeURIComponent(s)}`);
      const data = await apiGet<TrackingResp>("/api/tracking");
      setRawRows(data.rows ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void refresh(scope);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows = useMemo(() => {
    return rawRows.filter((r) => {
      if (qMid && r.sg_message_id !== qMid) return false;
      if (qBatch && r.send_batch_id !== qBatch) return false;
      if (qEmail && r.email.toLowerCase() !== qEmail) return false;
      return true;
    });
  }, [rawRows, qMid, qBatch, qEmail]);

  return (
    <div className="space-y-8">
      <PageHero
        variant="emerald"
        eyebrow="SendGrid"
        title="Tracking"
        description="Événements agrégés par destinataire : livraisons, ouvertures, clics, URLs, rapidité & décisions IA."
      />

      <div className="flex flex-col gap-4 rounded-3xl border border-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)] bg-gradient-to-br from-[color:var(--brand-blue-pale)]/50 via-white to-[color:var(--brand-cream)] p-5 shadow-xl ring-1 ring-[color:var(--brand-blue-pale)] sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-2xl border border-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)] bg-white/90 px-3 py-2 text-sm font-semibold text-[color:var(--brand-blue-navy)] shadow-sm">
            <span className="text-xs text-[color:var(--brand-blue-deep)]/80">Scope</span>
            <select
              value={scope}
              onChange={async (e) => {
                const next = e.target.value as Scope;
                setScope(next);
                await refresh(next);
              }}
              className="rounded-xl border border-[color:color-mix(in_srgb,var(--brand-blue)_25%,transparent)] bg-white px-3 py-2 text-sm font-bold text-zinc-900 outline-none focus:ring-2 focus:ring-[color:var(--brand-orange)] disabled:opacity-60"
              disabled={busy}
            >
              <option value="all">Tout</option>
              <option value="latest_batch">Dernière phase</option>
              <option value="last_24h">24h</option>
            </select>
            <span className="text-xs text-[color:var(--brand-blue-deep)]/80">{busy ? "Mise à jour…" : "OK"}</span>
          </div>
          <button
            onClick={() => refresh()}
            className="rounded-2xl bg-gradient-to-r from-[color:var(--brand-blue)] to-[color:var(--brand-blue-deep)] px-5 py-2.5 text-sm font-bold text-white shadow-lg transition hover:brightness-110 disabled:opacity-60"
            disabled={busy}
          >
            {busy ? "…" : "Actualiser"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900 ring-1 ring-rose-100">
          <div className="font-bold">Erreur</div>
          <div className="mt-1 font-mono text-xs">{error}</div>
        </div>
      ) : null}

      {qMid || qBatch || qEmail ? (
        <div className="rounded-2xl border border-[color:var(--brand-blue-pale)] bg-[color:var(--brand-blue-pale)]/80 px-4 py-3 text-xs font-medium text-[color:var(--brand-blue-navy)] ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_12%,transparent)]">
          Filtré par{" "}
          {qMid ? <span className="font-mono">sg_message_id={qMid}</span> : null}
          {qMid && (qBatch || qEmail) ? <span> · </span> : null}
          {qBatch ? <span className="font-mono">send_batch_id={qBatch}</span> : null}
          {qBatch && qEmail ? <span> · </span> : null}
          {qEmail ? <span className="font-mono">email={qEmail}</span> : null}
          <span> · </span>
          <a className="font-bold text-[color:var(--brand-blue-deep)] underline underline-offset-2 hover:text-[color:var(--brand-orange-deep)]" href="/tracking">
            Réinitialiser
          </a>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-3xl border-0 bg-white shadow-2xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_20%,transparent)]">
        <div className="bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue-deep)] to-[color:var(--brand-blue)] px-5 py-3 text-white">
          <h2 className="text-base font-black tracking-tight">Destinataires & signaux</h2>
          <p className="text-sm text-white/90">Une ligne par prospect (scope actuel).</p>
        </div>
        <div className="overflow-auto bg-gradient-to-b from-white to-[color:var(--brand-blue-pale)]/25">
          <table className="min-w-[1100px] w-full text-sm">
            <thead className="sticky top-0 z-10 border-b border-[color:var(--brand-blue-pale)] bg-gradient-to-r from-[color:var(--brand-blue-pale)]/95 to-[color:var(--brand-cream)] text-xs font-bold uppercase tracking-wide text-[color:var(--brand-blue-navy)] shadow-sm backdrop-blur">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Prospect</th>
                <th className="px-4 py-3 text-left font-medium">Email</th>
                <th className="px-4 py-3 text-left font-medium">Delivered</th>
                <th className="px-4 py-3 text-left font-medium">Open</th>
                <th className="px-4 py-3 text-left font-medium">Click</th>
                <th className="px-4 py-3 text-left font-medium">Time spent</th>
                <th className="px-4 py-3 text-left font-medium">Clicked</th>
                <th className="px-4 py-3 text-left font-medium">Rapid &lt;1h</th>
                <th className="px-4 py-3 text-left font-medium">Score</th>
                <th className="px-4 py-3 text-left font-medium">Best time</th>
                <th className="px-4 py-3 text-left font-medium">Decision</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={`${r.prospect_id}:${r.send_batch_id || ""}:${r.sg_message_id || ""}`}
                  className={`border-b border-[color:color-mix(in_srgb,var(--brand-blue)_12%,transparent)] last:border-0 ${i % 2 === 0 ? "bg-white" : "bg-[color:var(--brand-cream)]/80"}`}
                >
                  <td className="px-4 py-3">
                    <span className="rounded-lg bg-gradient-to-r from-[color:var(--brand-blue-pale)] to-[color:var(--brand-yellow-soft)] px-2 py-1 font-mono text-xs font-bold text-[color:var(--brand-blue-navy)] ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)]">
                      {r.prospect_id}
                    </span>
                  </td>
                  <td className="px-4 py-3">{r.email}</td>
                  <td className="px-4 py-3">{r.delivered}</td>
                  <td className="px-4 py-3">{r.opens}</td>
                  <td className="px-4 py-3">{r.clicks}</td>
                  <td className="px-4 py-3 font-mono text-xs text-zinc-700">
                    {r.time_spent_seconds && Number(r.time_spent_seconds) > 0 ? `${r.time_spent_seconds}s` : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {(() => {
                      const urls = safeParseUrls(r.clicked_urls_json || "[]");
                      if (!urls.length) return "—";
                      return (
                        <div className="flex max-w-[420px] flex-col gap-1">
                          {urls.slice(0, 3).map((u) => (
                            <a
                              key={u}
                              className="truncate text-xs font-medium text-[color:var(--brand-blue-deep)] underline decoration-[color:var(--brand-yellow)] underline-offset-2 hover:text-[color:var(--brand-orange-deep)]"
                              href={u}
                              target="_blank"
                              rel="noreferrer"
                              title={u}
                            >
                              {u}
                            </a>
                          ))}
                          {urls.length > 3 ? <div className="text-xs text-zinc-500">+{urls.length - 3} autres</div> : null}
                        </div>
                      );
                    })()}
                  </td>
                  <td className="px-4 py-3">{r.rapid_click_1h === "1" ? "✅" : "—"}</td>
                  <td className="px-4 py-3">{r.score}</td>
                  <td className="px-4 py-3 font-mono text-xs text-zinc-700">
                    {r.best_send_hour !== undefined && r.best_send_hour !== "" && r.best_send_weekday !== undefined
                      ? `${wdName(r.best_send_weekday)} ${r.best_send_hour}h`
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium">{r.next_action}</div>
                    <div className="text-xs text-zinc-500">{r.reason}</div>
                  </td>
                </tr>
              ))}
              {!rows.length ? (
                <tr>
                  <td className="px-4 py-6 text-zinc-500" colSpan={11}>
                    Aucun tracking. Lancez d’abord “Actions” → “Générer report”.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

