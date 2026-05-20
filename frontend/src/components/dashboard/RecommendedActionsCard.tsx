"use client";

import type { Dispatch, SetStateAction } from "react";
import { CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { apiGet, apiPatch, apiPost } from "@/lib/api";

export type DecisionsRow = {
  prospect_id: string;
  score: string;
  segment: string;
  reason: string;
  suggested_next_action: string;
  final_next_action: string;
  approved: boolean;
  suggested_send_weekday: number;
  suggested_send_hour: number;
  final_send_weekday: number;
  final_send_hour: number;
};

type DecisionsResp = { ok: boolean; rows: DecisionsRow[] };

type MetricsPick = { metric: string; value: string }[];

function pick(metrics: MetricsPick, key: string): string {
  return metrics.find((m) => m.metric === key)?.value ?? "—";
}

type Props = {
  metrics: MetricsPick;
  decisions: DecisionsRow[];
  setDecisions: Dispatch<SetStateAction<DecisionsRow[]>>;
  selected: Record<string, boolean>;
  setSelected: Dispatch<SetStateAction<Record<string, boolean>>>;
  actionLog: string;
  setActionLog: (s: string) => void;
  loading: boolean;
};

export function RecommendedActionsCard({
  metrics,
  decisions,
  setDecisions,
  selected,
  setSelected,
  actionLog,
  setActionLog,
  loading,
}: Props) {
  const nSel = Object.values(selected).filter(Boolean).length;

  return (
    <div className="overflow-hidden rounded-3xl border-0 bg-white shadow-2xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)]">
      <div className="relative overflow-hidden bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue-deep)] to-[color:var(--brand-orange)] px-6 py-5 text-white">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/20 blur-2xl" />
        <div className="absolute bottom-0 left-1/4 h-24 w-64 rounded-full bg-[color:var(--brand-yellow)]/25 blur-3xl" />
        <div className="relative flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-white/70">Pilotage</p>
            <CardTitle className="mt-1 text-2xl font-black tracking-tight text-white md:text-3xl">
              Actions recommandées
            </CardTitle>
            <CardDescription className="mt-2 text-base text-white/85">
              Décisions IA par prospect — ajustez, cochez, validez pour envoyer.
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white/20 px-4 py-2 text-sm font-semibold text-white ring-1 ring-white/30 backdrop-blur">
              {decisions.length} prospects
            </span>
            <span className="rounded-full bg-amber-400/90 px-4 py-2 text-sm font-bold text-amber-950 shadow-lg">
              {nSel} sélectionné(s)
            </span>
            <button
              className="rounded-2xl bg-white px-5 py-3 text-sm font-bold text-[color:var(--brand-blue-deep)] shadow-lg transition hover:scale-[1.02] hover:shadow-xl disabled:pointer-events-none disabled:opacity-50"
              disabled={loading || !nSel}
              onClick={async () => {
                const ids = Object.entries(selected)
                  .filter(([, v]) => v)
                  .map(([k]) => k);
                const res = await apiPost("/api/decisions/validate", { prospect_ids: ids, execute: true });
                setActionLog(JSON.stringify(res, null, 2));
                const dec = await apiGet<DecisionsResp>("/api/decisions");
                setDecisions(dec.rows ?? []);
                setSelected({});
              }}
            >
              Valider & envoyer
            </button>
          </div>
        </div>
      </div>

      <CardContent className="space-y-4 bg-gradient-to-b from-[color:var(--brand-cream)] via-white to-[color:var(--brand-blue-pale)]/35 p-6 pt-5">
        <div className="flex flex-wrap gap-2">
          {[
            { label: "Envoyés", value: pick(metrics, "kpi_emails_envoyes"), from: "from-sky-500", to: "to-blue-700" },
            { label: "Dropped", value: pick(metrics, "kpi_dropped"), from: "from-[color:var(--brand-orange)]", to: "to-[color:var(--brand-orange-deep)]" },
            { label: "Spam %", value: `${pick(metrics, "kpi_taux_plaintes_spam_pct")}%`, from: "from-[color:var(--brand-blue-deep)]", to: "to-[color:var(--brand-blue-navy)]" },
          ].map((p) => (
            <div
              key={p.label}
              className={`rounded-2xl bg-gradient-to-r ${p.from} ${p.to} px-4 py-2.5 text-white shadow-md`}
            >
              <div className="text-[10px] font-bold uppercase tracking-wider text-white/80">{p.label}</div>
              <div className="text-lg font-black tabular-nums">{p.value}</div>
            </div>
          ))}
        </div>

        <div className="overflow-hidden rounded-2xl border border-[color:color-mix(in_srgb,var(--brand-blue)_20%,transparent)] bg-white/90 shadow-inner ring-1 ring-[color:var(--brand-blue-pale)]">
          <div className="max-h-[420px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-gradient-to-r from-[color:var(--brand-blue-deep)] to-[color:var(--brand-blue)] text-xs font-bold uppercase tracking-wide text-white shadow-md backdrop-blur">
                <tr>
                  <th className="px-3 py-3 text-left">✓</th>
                  <th className="px-3 py-3 text-left">Prospect</th>
                  <th className="px-3 py-3 text-left">Score</th>
                  <th className="px-3 py-3 text-left">Action</th>
                  <th className="px-3 py-3 text-left">Renvoi</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((r, idx) => {
                  const checked = !!selected[r.prospect_id];
                  const stripe = idx % 2 === 0 ? "bg-white" : "bg-[color:var(--brand-blue-pale)]/40";
                  return (
                    <tr key={r.prospect_id} className={`border-b border-[color:color-mix(in_srgb,var(--brand-blue)_12%,transparent)] last:border-0 ${stripe}`}>
                      <td className="px-3 py-3">
                        <input
                          type="checkbox"
                          checked={checked}
                          className="h-4 w-4 rounded border-[color:var(--brand-blue)] text-[color:var(--brand-blue-deep)] focus:ring-[color:var(--brand-orange)]"
                          onChange={(e) =>
                            setSelected((cur) => ({ ...cur, [r.prospect_id]: e.target.checked }))
                          }
                        />
                      </td>
                      <td className="px-3 py-3">
                        <span className="rounded-lg bg-gradient-to-r from-[color:var(--brand-blue-pale)] to-[color:var(--brand-yellow-soft)] px-2 py-1 font-mono text-xs font-bold text-[color:var(--brand-blue-navy)] ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)]">
                          {r.prospect_id}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span className="inline-flex min-w-[2.5rem] justify-center rounded-full bg-gradient-to-br from-amber-400 to-orange-500 px-2.5 py-1 text-xs font-black text-white shadow-sm">
                          {r.score}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <select
                          value={r.final_next_action}
                          className="w-full max-w-[220px] rounded-xl border border-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)] bg-white px-3 py-2 text-xs font-semibold text-zinc-800 shadow-sm outline-none ring-[color:var(--brand-blue-pale)] focus:ring-2 focus:ring-[color:var(--brand-orange)]"
                          onChange={async (e) => {
                            const next = e.target.value;
                            await apiPatch(`/api/decisions/${encodeURIComponent(r.prospect_id)}`, {
                              next_action: next,
                              approved: false,
                            });
                            setDecisions((cur) =>
                              cur.map((x) =>
                                x.prospect_id === r.prospect_id
                                  ? { ...x, final_next_action: next, approved: false }
                                  : x,
                              ),
                            );
                          }}
                        >
                          <option value="personalized_email_and_priority_call">
                            personalized_email_and_priority_call
                          </option>
                          <option value="follow_up_email">follow_up_email</option>
                          <option value="nurturing_newsletter">nurturing_newsletter</option>
                          <option value="do_not_contact">do_not_contact</option>
                        </select>
                        <div className="mt-1 text-[11px] text-[color:var(--brand-blue-deep)]/90">
                          IA: {r.suggested_next_action} {r.approved ? "• validé" : ""}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <select
                            value={String(r.final_send_weekday ?? -1)}
                            className="rounded-xl border border-[color:color-mix(in_srgb,var(--brand-blue)_25%,transparent)] bg-[color:var(--brand-blue-pale)]/40 px-2 py-2 text-xs font-semibold text-zinc-800 outline-none focus:ring-2 focus:ring-[color:var(--brand-orange)]"
                            onChange={async (e) => {
                              const wd = Number(e.target.value);
                              await apiPatch(`/api/decisions/${encodeURIComponent(r.prospect_id)}`, {
                                send_weekday: wd,
                                approved: false,
                              });
                              setDecisions((cur) =>
                                cur.map((x) =>
                                  x.prospect_id === r.prospect_id
                                    ? { ...x, final_send_weekday: wd, approved: false }
                                    : x,
                                ),
                              );
                            }}
                          >
                            <option value={-1}>—</option>
                            <option value={0}>Mon</option>
                            <option value={1}>Tue</option>
                            <option value={2}>Wed</option>
                            <option value={3}>Thu</option>
                            <option value={4}>Fri</option>
                            <option value={5}>Sat</option>
                            <option value={6}>Sun</option>
                          </select>
                          <select
                            value={String(r.final_send_hour ?? 9)}
                            className="rounded-xl border border-[color:color-mix(in_srgb,var(--brand-blue)_25%,transparent)] bg-[color:var(--brand-blue-pale)]/40 px-2 py-2 text-xs font-semibold text-zinc-800 outline-none focus:ring-2 focus:ring-[color:var(--brand-orange)]"
                            onChange={async (e) => {
                              const hr = Number(e.target.value);
                              await apiPatch(`/api/decisions/${encodeURIComponent(r.prospect_id)}`, {
                                send_hour: hr,
                                approved: false,
                              });
                              setDecisions((cur) =>
                                cur.map((x) =>
                                  x.prospect_id === r.prospect_id ? { ...x, final_send_hour: hr, approved: false } : x,
                                ),
                              );
                            }}
                          >
                            {Array.from({ length: 24 }).map((_, h) => (
                              <option key={h} value={h}>
                                {h}h
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="mt-1 text-[11px] text-[color:var(--brand-blue-deep)]/80">
                          IA:{" "}
                          {r.suggested_send_weekday >= 0
                            ? `${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][r.suggested_send_weekday]} `
                            : "— "}
                          {r.suggested_send_hour}h
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {!decisions.length ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-sm text-zinc-500" colSpan={5}>
                      Aucun prospect. Lancez l’analyse depuis Actions.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>

        {actionLog ? (
          <pre className="overflow-auto rounded-2xl border border-zinc-800 bg-zinc-950 p-4 text-xs text-[color:var(--brand-blue-sky)] shadow-inner">
            {actionLog}
          </pre>
        ) : null}
      </CardContent>
    </div>
  );
}
