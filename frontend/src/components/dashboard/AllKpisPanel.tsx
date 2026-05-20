"use client";

import { useMemo } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export type MetricRow = { metric: string; value: string };

function useMetricMap(metrics: MetricRow[]) {
  return useMemo(() => {
    const m = new Map<string, string>();
    for (const row of metrics) m.set(row.metric, row.value);
    return m;
  }, [metrics]);
}

function get(map: Map<string, string>, key: string): string {
  return map.get(key) ?? "—";
}

function safeJson<T>(raw: string | undefined): T | null {
  if (!raw || raw === "—") return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function StatGrid({
  items,
  accent = "blue",
}: {
  items: { label: string; value: string; hint?: string }[];
  accent?: "blue" | "sky" | "orange";
}) {
  const ring =
    accent === "sky"
      ? "ring-[color:color-mix(in_srgb,var(--brand-blue)_25%,transparent)] border-[color:var(--brand-blue-pale)] bg-gradient-to-br from-[color:var(--brand-blue-pale)]/60 to-white"
      : accent === "orange"
        ? "ring-[color:color-mix(in_srgb,var(--brand-orange)_28%,transparent)] border-[color:var(--brand-yellow-soft)] bg-gradient-to-br from-[color:var(--brand-yellow-soft)]/50 to-white"
        : "ring-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)] border-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)] bg-gradient-to-br from-[color:var(--brand-blue-pale)]/40 to-white";
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {items.map((it) => (
        <div key={it.label} className={`rounded-2xl border p-4 shadow-sm ring-1 ${ring}`}>
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{it.label}</div>
          <div className="mt-1 text-lg font-bold tabular-nums tracking-tight text-zinc-900">{it.value}</div>
          {it.hint ? <div className="mt-1 text-[11px] text-zinc-500">{it.hint}</div> : null}
        </div>
      ))}
    </div>
  );
}

function HourBars({
  title,
  data,
}: {
  title: string;
  data: Record<string, number> | null;
}) {
  if (!data) {
    return <p className="text-sm text-zinc-500">Aucune donnée</p>;
  }
  const pairs = Object.entries(data).map(([h, n]) => ({ h: Number(h), n: Number(n) || 0 }));
  const max = Math.max(1, ...pairs.map((p) => p.n));
  return (
    <div className="space-y-1">
      <div className="text-xs font-medium text-zinc-500">{title} (UTC)</div>
      <div className="grid max-h-[220px] gap-1 overflow-y-auto pr-1">
        {pairs.map(({ h, n }) => (
          <div key={h} className="flex items-center gap-2 text-[11px]">
            <span className="w-6 shrink-0 tabular-nums text-zinc-500">{h}h</span>
            <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-zinc-100">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[color:var(--brand-blue-deep)] via-[color:var(--brand-blue)] to-[color:var(--brand-blue-sky)]"
                style={{ width: `${(n / max) * 100}%` }}
              />
            </div>
            <span className="w-6 shrink-0 text-right tabular-nums text-zinc-700">{n}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function JsonTable({
  columns,
  rows,
}: {
  columns: { key: string; label: string }[];
  rows: Record<string, string | number>[];
}) {
  if (!rows.length) {
    return <p className="text-sm text-zinc-500">Aucune ligne</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)]">
      <table className="w-full min-w-[320px] text-left text-sm">
        <thead className="border-b bg-gradient-to-r from-[color:var(--brand-blue-pale)]/80 via-[color:var(--brand-yellow-soft)]/40 to-[color:color-mix(in_srgb,var(--brand-orange)_15%,transparent)] text-xs text-zinc-800">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className="px-3 py-2 font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b last:border-0">
              {columns.map((c) => (
                <td key={c.key} className="px-3 py-2 tabular-nums text-zinc-800">
                  {String(row[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AllKpisPanel({ metrics }: { metrics: MetricRow[] }) {
  const map = useMetricMap(metrics);

  const segment = safeJson<Record<string, { delivered: number; open_rate_pct: number; click_rate_pct: number; ctor_pct: number }>>(
    map.get("kpi_performance_par_segment_json"),
  );
  const segmentRows = segment
    ? Object.entries(segment).map(([segment_name, v]) => ({
        segment: segment_name,
        delivered: v.delivered,
        open_rate_pct: v.open_rate_pct,
        click_rate_pct: v.click_rate_pct,
        ctor_pct: v.ctor_pct,
      }))
    : [];

  const ab = safeJson<Record<string, { delivered: number; open_rate_pct: number; click_rate_pct: number; ctor_pct: number }>>(
    map.get("kpi_ab_testing_json"),
  );
  const abRows = ab
    ? Object.entries(ab).map(([variant, v]) => ({
        variant,
        delivered: v.delivered,
        open_rate_pct: v.open_rate_pct,
        click_rate_pct: v.click_rate_pct,
        ctor_pct: v.ctor_pct,
      }))
    : [];

  const provider = safeJson<
    Record<string, { delivered: number; open_rate_pct: number; spam_rate_pct: number }>
  >(map.get("kpi_performance_par_fournisseur_json"));
  const providerRows = provider
    ? Object.entries(provider).map(([name, v]) => ({
        fournisseur: name,
        delivered: v.delivered,
        open_rate_pct: v.open_rate_pct,
        spam_rate_pct: v.spam_rate_pct,
      }))
    : [];

  const heatmap = safeJson<{ url: string; clicks: number }[]>(map.get("kpi_heatmap_clic_top_urls_json"));
  const geo = safeJson<{ country: string; city: string; opens: number }[]>(map.get("kpi_pays_ville_ouverture_top_json"));

  const mobile = safeJson<Record<string, number>>(map.get("kpi_mobile_vs_desktop_json"));
  const webmail = safeJson<Record<string, number>>(map.get("kpi_webmail_vs_app_json"));
  const hoursOpen = safeJson<Record<string, number>>(map.get("kpi_heure_ouverture_json"));
  const hoursClick = safeJson<Record<string, number>>(map.get("kpi_heure_clic_json"));

  const engagementRows = metrics
    .filter((r) => r.metric.startsWith("engagement_score_"))
    .map((r) => ({
      prospect: r.metric.replace("engagement_score_", ""),
      score: r.value,
    }))
    .sort((a, b) => a.prospect.localeCompare(b.prospect, undefined, { numeric: true }));

  return (
    <div className="space-y-8">
      <Card className="overflow-hidden border-0 shadow-xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-orange)_22%,transparent)]">
        <div className="h-1 w-full bg-gradient-to-r from-[color:var(--brand-orange)] via-[color:var(--brand-yellow)] to-[color:var(--brand-yellow-soft)]" />
        <CardHeader className="bg-gradient-to-r from-[color:var(--brand-cream)] to-[color:var(--brand-yellow-soft)]/30">
          <CardTitle className="bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue-deep)] to-[color:var(--brand-orange)] bg-clip-text text-lg font-black text-transparent">
            1. Qualité & risques
          </CardTitle>
          <CardDescription>Désinscriptions, spam, bounces, dropped / deferred.</CardDescription>
        </CardHeader>
        <CardContent>
          <StatGrid
            accent="orange"
            items={[
              { label: "Taux désinscription (%)", value: `${get(map, "kpi_taux_desinscription_pct")}%` },
              { label: "Taux plaintes spam (%)", value: `${get(map, "kpi_taux_plaintes_spam_pct")}%` },
              { label: "Hard bounce", value: get(map, "kpi_hard_bounce") },
              { label: "Soft bounce", value: get(map, "kpi_soft_bounce") },
              { label: "Taux bounce global (%)", value: `${get(map, "kpi_taux_bounce_global_pct")}%` },
              { label: "Dropped", value: get(map, "kpi_dropped") },
              { label: "Deferred", value: get(map, "kpi_deferred") },
              { label: "Taux dropped (%)", value: `${get(map, "kpi_taux_dropped_pct")}%` },
            ]}
          />
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-0 shadow-xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_20%,transparent)]">
        <div className="h-1 w-full bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue)] to-[color:var(--brand-blue-sky)]" />
        <CardHeader className="bg-gradient-to-r from-[color:var(--brand-blue-pale)]/40 to-[color:var(--brand-cream)]">
          <CardTitle className="bg-gradient-to-r from-[color:var(--brand-blue-navy)] to-[color:var(--brand-blue)] bg-clip-text text-lg font-black text-transparent">
            2. Base de données (prospects)
          </CardTitle>
          <CardDescription>Taille base, désabonnés, performance par segment (reco agent).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <StatGrid
            accent="sky"
            items={[
              { label: "Base totale", value: get(map, "kpi_base_totale") },
              { label: "Désabonnés (base)", value: get(map, "kpi_desabonnes_base") },
            ]}
          />
          <div>
            <div className="mb-2 text-xs font-medium text-zinc-500">Performance par segment</div>
            <JsonTable
              columns={[
                { key: "segment", label: "Segment" },
                { key: "delivered", label: "Messages livrés" },
                { key: "open_rate_pct", label: "Open %" },
                { key: "click_rate_pct", label: "Click %" },
                { key: "ctor_pct", label: "CTOR %" },
              ]}
              rows={segmentRows}
            />
          </div>
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-0 shadow-xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue-deep)_18%,transparent)]">
        <div className="h-1 w-full bg-gradient-to-r from-[color:var(--brand-blue-deep)] via-[color:var(--brand-blue)] to-[color:var(--brand-yellow)]" />
        <CardHeader className="bg-gradient-to-r from-[color:var(--brand-blue-pale)]/35 to-transparent">
          <CardTitle className="bg-gradient-to-r from-[color:var(--brand-blue-deep)] via-[color:var(--brand-blue)] to-[color:var(--brand-orange)] bg-clip-text text-lg font-black text-transparent">
            3. KPI techniques
          </CardTitle>
          <CardDescription>Device, client mail, géo, heures (données SendGrid / UA).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <div className="mb-2 text-xs font-medium text-zinc-500">Mobile vs desktop (opens)</div>
              <StatGrid
                accent="sky"
                items={
                  mobile
                    ? Object.entries(mobile).map(([k, v]) => ({ label: k, value: String(v) }))
                    : [{ label: "—", value: "—" }]
                }
              />
            </div>
            <div>
              <div className="mb-2 text-xs font-medium text-zinc-500">Webmail vs application (opens)</div>
              <StatGrid
                accent="sky"
                items={
                  webmail
                    ? Object.entries(webmail).map(([k, v]) => ({ label: k, value: String(v) }))
                    : [{ label: "—", value: "—" }]
                }
              />
            </div>
          </div>
          <div>
            <div className="mb-2 text-xs font-medium text-zinc-500">Pays / ville (top ouvertures)</div>
            <JsonTable
              columns={[
                { key: "country", label: "Pays" },
                { key: "city", label: "Ville" },
                { key: "opens", label: "Opens" },
              ]}
              rows={(geo ?? []).map((g) => ({ country: g.country, city: g.city, opens: g.opens }))}
            />
          </div>
          <div className="grid gap-6 lg:grid-cols-2">
            <HourBars title="Heure d’ouverture" data={hoursOpen} />
            <HourBars title="Heure de clic" data={hoursClick} />
          </div>
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-0 shadow-xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-yellow)_25%,transparent)]">
        <div className="h-1 w-full bg-gradient-to-r from-[color:var(--brand-yellow)] via-[color:var(--brand-orange)] to-[color:var(--brand-blue)]" />
        <CardHeader className="bg-gradient-to-r from-[color:var(--brand-yellow-soft)]/40 to-[color:var(--brand-cream)]">
          <CardTitle className="bg-gradient-to-r from-[color:var(--brand-blue-deep)] to-[color:var(--brand-orange)] bg-clip-text text-lg font-black text-transparent">
            4. A/B testing
          </CardTitle>
          <CardDescription>Par variante (custom_args ou URL). Sans variante → unknown.</CardDescription>
        </CardHeader>
        <CardContent>
          <JsonTable
            columns={[
              { key: "variant", label: "Variante" },
              { key: "delivered", label: "Messages livrés" },
              { key: "open_rate_pct", label: "Open %" },
              { key: "click_rate_pct", label: "Click %" },
              { key: "ctor_pct", label: "CTOR %" },
            ]}
            rows={abRows}
          />
        </CardContent>
      </Card>

      <Card className="overflow-hidden border-0 shadow-xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-orange)_22%,transparent)]">
        <div className="h-1 w-full bg-gradient-to-r from-[color:var(--brand-yellow-soft)] via-[color:var(--brand-yellow)] to-[color:var(--brand-blue-sky)]" />
        <CardHeader className="bg-gradient-to-r from-[color:var(--brand-cream)] to-[color:var(--brand-blue-pale)]/30">
          <CardTitle className="bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue)] to-[color:var(--brand-yellow)] bg-clip-text text-lg font-black text-transparent">
            5. KPI avancés
          </CardTitle>
          <CardDescription>Score qualité, heatmap URLs, messagerie (Gmail, Outlook…), scores par contact.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <StatGrid accent="blue" items={[{ label: "Score qualité (heuristique)", value: get(map, "kpi_score_qualite") }]} />
          <div>
            <div className="mb-2 text-xs font-medium text-zinc-500">Heatmap clics (top URLs)</div>
            <JsonTable
              columns={[
                { key: "url", label: "URL" },
                { key: "clicks", label: "Clics" },
              ]}
              rows={(heatmap ?? []).map((h) => ({ url: h.url, clicks: h.clicks }))}
            />
          </div>
          <div>
            <div className="mb-2 text-xs font-medium text-zinc-500">Performance par messagerie (Gmail, Outlook, Yahoo…)</div>
            <JsonTable
              columns={[
                { key: "fournisseur", label: "Messagerie" },
                { key: "delivered", label: "Messages livrés" },
                { key: "open_rate_pct", label: "Open %" },
                { key: "spam_rate_pct", label: "Spam %" },
              ]}
              rows={providerRows}
            />
          </div>
          <div>
            <div className="mb-2 text-xs font-medium text-zinc-500">Score d’engagement par contact</div>
            <div className="max-h-[280px] overflow-auto rounded-xl border border-[color:color-mix(in_srgb,var(--brand-blue)_18%,transparent)]">
              <table className="w-full text-sm">
                <thead className="sticky top-0 border-b bg-zinc-50 text-xs text-zinc-600">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Prospect</th>
                    <th className="px-3 py-2 text-left font-medium">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {engagementRows.map((r) => (
                    <tr key={r.prospect} className="border-b last:border-0">
                      <td className="px-3 py-2 font-mono text-xs">{r.prospect}</td>
                      <td className="px-3 py-2 tabular-nums">{r.score}</td>
                    </tr>
                  ))}
                  {!engagementRows.length ? (
                    <tr>
                      <td colSpan={2} className="px-3 py-4 text-zinc-500">
                        Aucun score d’engagement
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
          <p className="text-xs text-zinc-500">
            Parcours email → action (funnel conversion) : non calculé côté SendGrid seul — à brancher sur analytics
            site / objectifs.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
