"use client";

import { useMemo } from "react";
import { Area, AreaChart, Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { TrendPoint } from "@/components/charts/Trend";

export type DashboardMetricRow = { metric: string; value: string };

function metricMap(rows: DashboardMetricRow[]) {
  const m = new Map<string, string>();
  for (const r of rows) m.set(r.metric, r.value);
  return m;
}

function get(m: Map<string, string>, k: string) {
  return m.get(k) ?? "—";
}

function num(s: string) {
  const n = Number(String(s).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function formatInt(n: number) {
  return new Intl.NumberFormat("fr-FR").format(Math.round(n));
}

// Hide deltas computed on tiny samples to avoid misleading "+66.7% vs point précédent"
// when both points are basically noise (e.g. 3 → 5). Only show a delta when the
// largest of the two compared points is at least MIN_BASE.
const MIN_BASE = 5;

function deltaPct(series: number[]): { pct: number; up: boolean } | null {
  if (series.length < 2) return null;
  const a = series[series.length - 2];
  const b = series[series.length - 1];
  if (Math.max(Math.abs(a), Math.abs(b)) < MIN_BASE) return null;
  if (a === 0) return b === 0 ? null : { pct: 100, up: b > 0 };
  const pct = ((b - a) / Math.abs(a)) * 100;
  return { pct: Math.round(pct * 10) / 10, up: pct >= 0 };
}

function DeltaLine({ d }: { d: { pct: number; up: boolean } | null }) {
  if (!d) {
    return (
      <span
        className="text-xs text-zinc-400"
        title="Pas assez de données pour comparer (au moins 2 points et un volume ≥ 5)"
      >
        —
      </span>
    );
  }
  const color = d.up ? "text-[color:var(--brand-blue-deep)]" : "text-[color:var(--brand-orange-deep)]";
  const sign = d.pct > 0 ? "+" : "";
  return (
    <span
      className={`text-xs font-semibold ${color}`}
      title="Variation entre les deux derniers points du trend (jour ou phase selon le scope)"
    >
      {sign}
      {d.pct}% <span className="font-normal text-zinc-500">vs point précédent</span>
    </span>
  );
}

function Macaron({
  label,
  value,
  suffix = "",
  gradient,
}: {
  label: string;
  value: string;
  suffix?: string;
  gradient: string;
}) {
  return (
    <div
      className={`relative flex min-h-[140px] flex-col justify-between overflow-hidden rounded-3xl p-6 text-white shadow-xl ${gradient}`}
    >
      <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-white/15 blur-2xl" />
      <div className="absolute -bottom-8 left-1/3 h-20 w-20 rounded-full bg-black/10 blur-xl" />
      <div className="relative text-[10px] font-bold uppercase tracking-[0.2em] text-white/85">{label}</div>
      <div className="relative mt-2 text-4xl font-black tabular-nums tracking-tight">
        {value}
        {suffix ? <span className="text-2xl font-bold">{suffix}</span> : null}
      </div>
    </div>
  );
}

export function DashboardPerformanceStrip({
  metrics,
  trend,
}: {
  metrics: DashboardMetricRow[];
  trend: TrendPoint[];
}) {
  const m = useMemo(() => metricMap(metrics), [metrics]);

  const chartData = useMemo(() => {
    return trend.map((p) => ({
      label: p.date.length > 10 ? p.date.slice(5) : p.date,
      engagement: (p.opens ?? 0) + (p.clicks ?? 0),
      delivered: p.delivered ?? 0,
      clicks: p.clicks ?? 0,
      opens: p.opens ?? 0,
      unsubscribes: p.unsubscribes ?? 0,
    }));
  }, [trend]);

  const openSeries = chartData.map((d) => d.opens);
  const clickSeries = chartData.map((d) => d.clicks);
  const deliveredSeries = chartData.map((d) => d.delivered);
  const unsubSeries = chartData.map((d) => d.unsubscribes);

  const delivered = num(get(m, "kpi_emails_delivres"));
  const opensU = num(get(m, "kpi_ouvertures_uniques"));
  const clicksT = num(get(m, "kpi_clics_totaux"));
  const unsubEv = num(get(m, "unsubscribe_events"));
  const openRate = get(m, "kpi_taux_ouverture_pct");
  const bounceGlobal = get(m, "kpi_taux_bounce_global_pct");

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-3xl bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue-deep)] to-[color:var(--brand-orange-deep)] px-5 py-4 text-white shadow-2xl ring-1 ring-white/10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-white/60">Performance campagne</p>
            <h2 className="mt-1 text-xl font-bold tracking-tight">Vue exécutive — engagement & délivrabilité</h2>
          </div>
          <div className="rounded-full bg-white/10 px-4 py-1.5 text-xs font-medium text-white/90 ring-1 ring-white/20">
            Données SendGrid + agent
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-12">
        {/* Col 1: Délivrés + area */}
        <div className="lg:col-span-3">
          <div className="flex h-full flex-col rounded-3xl border border-white/60 bg-white p-5 shadow-[0_20px_50px_-28px_rgba(26,145,168,0.35)] ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_12%,transparent)]">
            <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Emails délivrés</p>
            <p className="mt-1 text-3xl font-black tabular-nums text-zinc-900">{formatInt(delivered)}</p>
            <p className="mt-2 text-xs text-zinc-500">Volume unique (email × message)</p>
            <div className="mt-3 h-[88px] w-full min-h-[88px] min-w-0 flex-1">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%" minHeight={88}>
                  <AreaChart data={chartData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="fillEngage" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--brand-blue)" stopOpacity={0.55} />
                        <stop offset="100%" stopColor="var(--brand-blue)" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="label" hide />
                    <YAxis hide domain={[0, "dataMax"]} />
                    <Area
                      type="monotone"
                      dataKey="engagement"
                      stroke="var(--brand-blue-deep)"
                      strokeWidth={2}
                      fill="url(#fillEngage)"
                      dot={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full items-center text-xs text-zinc-400">Pas assez de points temporels</div>
              )}
            </div>
            <div className="mt-2 border-t border-zinc-100 pt-2">
              <DeltaLine d={deltaPct(deliveredSeries)} />
            </div>
          </div>
        </div>

        {/* Col 2: Désinscriptions + bars */}
        <div className="lg:col-span-3">
          <div className="flex h-full flex-col rounded-3xl border border-amber-100/80 bg-gradient-to-br from-amber-50/90 to-orange-50/50 p-5 shadow-lg ring-1 ring-amber-200/40">
            <p className="text-[10px] font-bold uppercase tracking-wider text-amber-900/70">Désinscriptions</p>
            <p className="mt-1 text-3xl font-black tabular-nums text-amber-950">{formatInt(unsubEv)}</p>
            <p className="mt-2 text-xs text-amber-900/55">Events unsubscribe (période / scope)</p>
            <div className="mt-3 h-[88px] w-full min-h-[88px] min-w-0">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%" minHeight={88}>
                  <BarChart data={chartData} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                    <XAxis dataKey="label" hide />
                    <YAxis hide domain={[0, "dataMax"]} />
                    <Bar dataKey="unsubscribes" radius={[6, 6, 0, 0]} maxBarSize={14}>
                      {chartData.map((_, i) => (
                        <Cell key={i} fill={i === chartData.length - 1 ? "var(--brand-orange)" : "color-mix(in srgb, var(--brand-orange) 45%, white)"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : null}
            </div>
            <div className="mt-2 border-t border-amber-200/50 pt-2">
              <DeltaLine d={deltaPct(unsubSeries)} />
            </div>
          </div>
        </div>

        {/* Col 3: Opens / Clicks split */}
        <div className="lg:col-span-3">
          <div className="grid h-full grid-rows-2 gap-3">
            <div className="rounded-2xl bg-gradient-to-br from-[color:var(--brand-blue)] to-[color:var(--brand-blue-navy)] p-4 text-white shadow-lg">
              <p className="text-[9px] font-bold uppercase tracking-wider text-white/75">Ouverts</p>
              <p className="mt-0.5 text-2xl font-black tabular-nums">{formatInt(opensU)}</p>
              <div className="mt-2 text-[11px] text-white/80">
                <DeltaLine d={deltaPct(openSeries)} />
              </div>
            </div>
            <div className="rounded-2xl bg-gradient-to-br from-[color:var(--brand-orange)] to-[color:var(--brand-yellow)] p-4 text-white shadow-lg">
              <p className="text-[9px] font-bold uppercase tracking-wider text-white/75">Clics (total)</p>
              <p className="mt-0.5 text-2xl font-black tabular-nums">{formatInt(clicksT)}</p>
              <div className="mt-2 text-[11px] text-white/80">
                <DeltaLine d={deltaPct(clickSeries)} />
              </div>
            </div>
          </div>
        </div>

        {/* Macarons */}
        <div className="grid gap-3 lg:col-span-3 sm:grid-cols-2">
          <Macaron
            label="Taux d’ouverture"
            value={String(openRate)}
            suffix="%"
            gradient="bg-gradient-to-br from-[color:var(--brand-blue-sky)] via-[color:var(--brand-blue)] to-[color:var(--brand-blue-navy)]"
          />
          <Macaron
            label="Taux bounce global"
            value={String(bounceGlobal)}
            suffix="%"
            gradient="bg-gradient-to-br from-[color:var(--brand-yellow-soft)] via-[color:var(--brand-orange)] to-[color:var(--brand-orange-deep)]"
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          { label: "CTR unique", value: `${get(m, "kpi_ctr_unique_pct")}%`, className: "from-[color:var(--brand-blue)] to-[color:var(--brand-blue-sky)]" },
          { label: "Délivrabilité", value: `${get(m, "kpi_taux_delivrabilite_pct")}%`, className: "from-[color:var(--brand-blue-deep)] to-[color:var(--brand-blue-navy)]" },
          { label: "Rapid click", value: `${get(m, "kpi_rapid_click_rate_pct")}%`, className: "from-[color:var(--brand-yellow)] to-[color:var(--brand-orange)]" },
          { label: "CTOR", value: `${get(m, "kpi_ctor_pct")}%`, className: "from-[color:var(--brand-blue-navy)] to-[color:var(--brand-blue)]" },
        ].map((pill) => (
          <div
            key={pill.label}
            className={`rounded-full bg-gradient-to-r px-4 py-2 text-xs font-bold text-white shadow-md ${pill.className}`}
          >
            <span className="opacity-90">{pill.label}</span>{" "}
            <span className="tabular-nums">{pill.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
