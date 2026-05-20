"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { GradientTableShell, PageHero } from "@/components/ui/page-hero";

type RecRow = {
  prospect_id: string;
  score: string;
  segment: string;
  next_action: string;
  campaign_step: string;
  best_send_weekday: string;
  best_send_hour: string;
  reason: string;
};

function wdName(wd: string): string {
  const n = Number(wd);
  const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  return Number.isFinite(n) && n >= 0 && n <= 6 ? names[n] : "—";
}

type RecommendationsResp = { ok: boolean; rows: RecRow[] };

export default function RecommendationsPage() {
  const [rows, setRows] = useState<RecRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<RecommendationsResp>("/api/recommendations")
      .then((d) => {
        if (!cancelled) setRows(d.rows ?? []);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-8">
      <PageHero
        variant="violet"
        eyebrow="Audience"
        title="Prospects"
        description="Scores, segments, meilleur créneau d’envoi et actions proposées par l’agent — vue colorée pour prioriser vite."
      />

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900 ring-1 ring-rose-100">
          <div className="font-bold">Backend non prêt</div>
          <div className="mt-1 font-mono text-xs">{error}</div>
        </div>
      ) : null}

      <GradientTableShell
        title="Liste des prospects"
        subtitle="Tri visuel par segment — survolez les raisons pour le détail."
        barVariant="violet"
      >
        <div className="overflow-auto">
          <table className="min-w-[900px] w-full text-sm">
            <thead className="sticky top-0 z-10 bg-gradient-to-r from-[color:var(--brand-blue-deep)] to-[color:var(--brand-blue)] text-xs font-bold uppercase tracking-wide text-white shadow-md">
              <tr>
                <th className="px-4 py-3 text-left">Prospect</th>
                <th className="px-4 py-3 text-left">Score</th>
                <th className="px-4 py-3 text-left">Segment</th>
                <th className="px-4 py-3 text-left">Best time</th>
                <th className="px-4 py-3 text-left">Action</th>
                <th className="px-4 py-3 text-left">Step</th>
                <th className="px-4 py-3 text-left">Raison</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr
                  key={r.prospect_id}
                  className={`border-b border-[color:color-mix(in_srgb,var(--brand-blue)_15%,transparent)] last:border-0 ${i % 2 === 0 ? "bg-white" : "bg-[color:var(--brand-blue-pale)]/35"}`}
                >
                  <td className="px-4 py-3">
                    <span className="rounded-lg bg-gradient-to-r from-[color:var(--brand-blue-pale)] to-[color:var(--brand-yellow-soft)] px-2.5 py-1 font-mono text-xs font-bold text-[color:var(--brand-blue-navy)] ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)]">
                      {r.prospect_id}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex min-w-[2.25rem] justify-center rounded-full bg-gradient-to-br from-amber-400 to-orange-500 px-2 py-1 text-xs font-black text-white shadow-sm">
                      {r.score}
                    </span>
                  </td>
                  <td className="px-4 py-3">{badge(r.segment)}</td>
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-[color:var(--brand-blue-deep)]">
                    {r.best_send_hour !== undefined && r.best_send_hour !== "" && r.best_send_weekday !== undefined
                      ? `${wdName(r.best_send_weekday)} ${r.best_send_hour}h`
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-lg bg-white px-2 py-1 text-xs font-semibold text-zinc-800 ring-1 ring-[color:var(--brand-blue-pale)]">
                      {r.next_action}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-[color:var(--brand-blue-pale)] px-2.5 py-1 text-xs font-bold text-[color:var(--brand-blue-navy)]">
                      {r.campaign_step}
                    </span>
                  </td>
                  <td className="max-w-md px-4 py-3 text-xs leading-relaxed text-zinc-600">{r.reason}</td>
                </tr>
              ))}
              {!rows.length ? (
                <tr>
                  <td className="px-4 py-10 text-center text-sm text-zinc-500" colSpan={7}>
                    Aucun résultat. Lancez l’analyse dans « Actions ».
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </GradientTableShell>
    </div>
  );
}

function badge(segment: string) {
  const s = (segment || "").toLowerCase();
  const cls =
    s === "high"
      ? "bg-gradient-to-r from-[color:var(--brand-blue-deep)] to-[color:var(--brand-blue)] text-white shadow-md ring-0"
      : s === "medium"
        ? "bg-gradient-to-r from-amber-400 to-orange-500 text-amber-950 shadow-md"
        : "bg-gradient-to-r from-zinc-400 to-zinc-600 text-white shadow-sm";
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-bold ${cls}`}>{segment}</span>
  );
}
