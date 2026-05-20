"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { AllKpisPanel } from "@/components/dashboard/AllKpisPanel";
import { DashboardPerformanceStrip } from "@/components/dashboard/DashboardPerformanceStrip";
import { RecommendedActionsCard, type DecisionsRow } from "@/components/dashboard/RecommendedActionsCard";
import { Trend, type TrendPoint } from "@/components/charts/Trend";
import { Activity, ShieldCheck, Zap } from "lucide-react";

type DashboardResp = { ok: boolean; metrics: { metric: string; value: string }[] };
type TrendResp = { ok: boolean; points: TrendPoint[] };
type PhaseTrendResp = { ok: boolean; points: TrendPoint[] };
type DecisionsResp = { ok: boolean; rows: DecisionsRow[] };

type Scope = "all" | "latest_batch" | "last_24h";

export default function Home() {
  const [scope, setScope] = useState<Scope>("all");
  const [data, setData] = useState<DashboardResp | null>(null);
  const [trendResp, setTrendResp] = useState<TrendResp | null>(null);
  const [phaseTrend, setPhaseTrend] = useState<PhaseTrendResp | null>(null);
  const [decisions, setDecisions] = useState<DecisionsRow[]>([]);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [actionLog, setActionLog] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  async function refresh(nextScope: Scope) {
    setLoading(true);
    setError(null);
    try {
      await apiPost(`/api/report/sendgrid?scope=${encodeURIComponent(nextScope)}`);
      const [d, t, p] = await Promise.all([
        apiGet<DashboardResp>("/api/dashboard"),
        apiGet<TrendResp>(`/api/trend?scope=${encodeURIComponent(nextScope)}`),
        apiGet<PhaseTrendResp>(`/api/trend/phases?scope=${encodeURIComponent(nextScope)}`),
      ]);
      const dec = await apiGet<DecisionsResp>("/api/decisions");
      setData(d);
      setTrendResp(t);
      setPhaseTrend(p);
      setDecisions(dec.rows ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh(scope);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const metrics = data?.metrics ?? [];
  const trend: TrendPoint[] = trendResp?.points ?? [];
  const trendPhases: TrendPoint[] = phaseTrend?.points ?? [];

  const scopeLabel = useMemo(() => {
    if (scope === "all") return "Tout";
    if (scope === "latest_batch") return "Dernière phase";
    return "24h";
  }, [scope]);

  return (
    <div className="space-y-8">
      <div className="relative overflow-hidden rounded-3xl border border-white/40 bg-white/70 p-6 shadow-xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)] backdrop-blur-md md:p-8">
        <div className="pointer-events-none absolute -right-16 top-0 h-48 w-48 rounded-full bg-gradient-to-br from-[color:var(--brand-blue-sky)]/35 to-[color:var(--brand-yellow)]/20 blur-3xl" />
        <div className="relative flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-[color:var(--brand-blue-pale)]/80 to-[color:var(--brand-yellow-soft)]/60 px-3 py-1 text-xs font-bold uppercase tracking-wider text-[color:var(--brand-blue-deep)] ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_20%,transparent)]">
              <ShieldCheck className="h-4 w-4 text-[color:var(--brand-blue-deep)]" />
              KPI • Scoring • Tracking
            </div>
            <h1 className="mt-3 bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue-deep)] to-[color:var(--brand-orange)] bg-clip-text text-3xl font-black tracking-tight text-transparent md:text-4xl">
              Vue d’ensemble
            </h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-zinc-600">
              Cockpit coloré : performance, tendances, puis actions à valider en bas de page.
            </p>
          </div>
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="flex items-center gap-2 rounded-2xl border border-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)] bg-gradient-to-r from-white to-[color:var(--brand-cream)] px-3 py-2 text-sm text-zinc-800 shadow-sm">
              <span className="text-xs font-semibold text-[color:var(--brand-blue-deep)]">Scope</span>
              <select
                value={scope}
                onChange={async (e) => {
                  const next = e.target.value as Scope;
                  setScope(next);
                  await refresh(next);
                }}
                className="rounded-xl border border-[color:color-mix(in_srgb,var(--brand-blue)_25%,transparent)] bg-white px-3 py-2 text-sm font-bold text-zinc-900 outline-none ring-2 ring-transparent focus:ring-[color:var(--brand-orange)] disabled:opacity-60"
                disabled={loading}
              >
                <option value="all">Tout</option>
                <option value="latest_batch">Dernière phase</option>
                <option value="last_24h">24h</option>
              </select>
              <span className="text-xs font-medium text-[color:var(--brand-blue-deep)]/80">{loading ? "Mise à jour…" : scopeLabel}</span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <a
                className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-[color:var(--brand-blue)] to-[color:var(--brand-blue-deep)] px-5 py-3 text-sm font-bold text-white shadow-lg shadow-[color:color-mix(in_srgb,var(--brand-blue)_35%,transparent)] transition hover:brightness-110"
                href="/actions"
              >
                <Zap className="h-4 w-4" />
                Lancer l’analyse
              </a>
              <a
                className="inline-flex items-center gap-2 rounded-2xl border-2 border-[color:var(--brand-orange)]/40 bg-white px-5 py-3 text-sm font-bold text-[color:var(--brand-orange-deep)] shadow-sm transition hover:bg-[color:var(--brand-yellow-soft)]/50"
                href="/tracking"
              >
                <Activity className="h-4 w-4" />
                Tracking
              </a>
            </div>
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900 ring-1 ring-rose-100">
          <div className="font-bold">Backend non prêt</div>
          <div className="mt-1 font-mono text-xs">{error}</div>
          <div className="mt-3 text-xs text-rose-700">
            Démarrez l’API: <span className="font-mono">uvicorn backend.app.main:app --port 8000</span>
          </div>
        </div>
      ) : null}

      <DashboardPerformanceStrip metrics={metrics} trend={trend} />

      <AllKpisPanel metrics={metrics} />

      <Card className="overflow-hidden border-0 shadow-2xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_20%,transparent)]">
        <div className="bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue-deep)] to-[color:var(--brand-blue)] px-6 py-4 text-white">
          <CardTitle className="text-lg font-black text-white">Évolution des performances</CardTitle>
          <CardDescription className="text-[color:var(--brand-blue-pale)]/95">Par jour (UTC) — ouvertures & clics.</CardDescription>
        </div>
        <CardContent className="bg-gradient-to-b from-white via-[color:var(--brand-cream)] to-[color:var(--brand-blue-pale)]/30 pt-5">
          <Trend data={trend} />
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-0 shadow-2xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-orange)_22%,transparent)]">
        <div className="bg-gradient-to-r from-[color:var(--brand-blue-deep)] via-[color:var(--brand-orange)] to-[color:var(--brand-yellow)] px-6 py-4 text-white">
          <CardTitle className="text-lg font-black text-white">Performance par phase</CardTitle>
          <CardDescription className="text-white/90">Chaque phase = un envoi (ex. phase-1, phase-2).</CardDescription>
        </div>
        <CardContent className="bg-gradient-to-b from-white to-[color:var(--brand-yellow-soft)]/25 pt-5">
          <Trend data={trendPhases} />
        </CardContent>
      </Card>

      <RecommendedActionsCard
        metrics={metrics}
        decisions={decisions}
        setDecisions={setDecisions}
        selected={selected}
        setSelected={setSelected}
        actionLog={actionLog}
        setActionLog={setActionLog}
        loading={loading}
      />
    </div>
  );
}
