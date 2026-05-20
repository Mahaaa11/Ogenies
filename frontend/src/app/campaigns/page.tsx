"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { PageHero } from "@/components/ui/page-hero";

type PhaseRow = {
  campaign_id: string;
  phase_id: string;
  template_id: string;
  date: string;
  recipients_known: number;
  recipients_total: number;
  processed: number;
  delivered: number;
  opens: number;
  clicks: number;
  dropped: number;
  bounces: number;
  spam: number;
  unsub: number;
  rapid_click_1h: number;
  open_rate_pct: number;
  ctr_unique_pct: number;
  ctor_unique_pct: number;
  delta_open_rate_pct: number | null;
  delta_ctr_unique_pct: number | null;
  likely_blocker: string;
  assignee: string;
  blocker_owner: string;
  status: string;
};

type Campaign = {
  campaign_id: string;
  name: string;
  phases_count: number;
  total_recipients: number;
  total_recipients_total: number;
  total_delivered: number;
  phases: PhaseRow[];
};

type CampaignsResp = { ok: boolean; campaigns: Campaign[] };

type Scope = "all" | "latest_batch" | "last_24h";

function Delta({ v }: { v: number | null }) {
  if (v === null) return <span className="text-zinc-400">—</span>;
  const up = v > 0;
  const down = v < 0;
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ring-1",
        up ? "bg-[color:var(--brand-blue-pale)] text-[color:var(--brand-blue-deep)] ring-[color:color-mix(in_srgb,var(--brand-blue)_25%,transparent)]" : "",
        down ? "bg-[color:var(--brand-yellow-soft)] text-[color:var(--brand-orange-deep)] ring-[color:color-mix(in_srgb,var(--brand-orange)_28%,transparent)]" : "",
        v === 0 ? "bg-zinc-50 text-zinc-700 ring-zinc-200" : "",
      ].join(" ")}
    >
      <span aria-hidden>{up ? "▲" : down ? "▼" : "■"}</span>
      <span>{Math.abs(v).toFixed(2)}%</span>
    </span>
  );
}

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<Scope>("all");

  async function refresh(nextScope?: Scope) {
    const s = nextScope ?? scope;
    setBusy(true);
    try {
      // Regenerate artifacts for consistent numbers across pages.
      await apiPost(`/api/report/sendgrid?scope=${encodeURIComponent(s)}`);
      const data = await apiGet<CampaignsResp>(`/api/campaigns?scope=${encodeURIComponent(s)}`);
      setCampaigns(data.campaigns ?? []);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refresh().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return campaigns;
    return campaigns.filter((c) => {
      const hay = `${c.campaign_id} ${c.name}`.toLowerCase();
      return hay.includes(s);
    });
  }, [q, campaigns]);

  return (
    <div className="space-y-8">
      <PageHero
        variant="amber"
        eyebrow="Pilotage"
        title="Aperçu des campagnes"
        description="Une ligne = une campagne (ex. Acquisition). Dépliez pour voir les phases / envois, deltas, intervenants et blocages."
      />

      <div className="flex flex-col gap-4 rounded-3xl border border-amber-100/80 bg-gradient-to-br from-amber-50/50 via-white to-orange-50/30 p-5 shadow-xl ring-1 ring-orange-200/40 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-2xl border border-orange-200/60 bg-white/90 px-3 py-2 text-xs font-semibold text-orange-900 shadow-sm">
            <span className="text-orange-600/80">Scope</span>
            <select
              value={scope}
              onChange={async (e) => {
                const next = e.target.value as Scope;
                setScope(next);
                await refresh(next);
              }}
              className="rounded-xl border border-orange-200 bg-white px-2 py-1.5 text-xs font-bold text-zinc-900 outline-none focus:ring-2 focus:ring-orange-400 disabled:opacity-60"
              disabled={busy}
            >
              <option value="all">Tout</option>
              <option value="latest_batch">Dernière phase</option>
              <option value="last_24h">24h</option>
            </select>
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher campagne, phase, statut…"
            className="min-w-[200px] flex-1 rounded-2xl border-2 border-orange-200/60 bg-white px-4 py-2.5 text-sm font-medium text-zinc-800 shadow-inner outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-200"
          />
          <button
            onClick={() => refresh()}
            className="rounded-2xl bg-gradient-to-r from-[color:var(--brand-orange)] to-[color:var(--brand-yellow)] px-5 py-2.5 text-sm font-bold text-white shadow-lg transition hover:brightness-110 disabled:opacity-60"
            disabled={busy}
          >
            {busy ? "…" : "Actualiser"}
          </button>
        </div>
        <div className="rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2 text-sm font-black text-white shadow-md">
          {filtered.length} campagne(s)
        </div>
      </div>

      <div className="overflow-hidden rounded-3xl border-0 bg-white shadow-2xl ring-1 ring-orange-200/50">
        <div className="bg-gradient-to-r from-[color:var(--brand-orange)] via-[color:var(--brand-yellow)] to-[color:var(--brand-blue)] px-5 py-3 text-white">
          <h2 className="text-base font-black tracking-tight">Tableau des campagnes</h2>
          <p className="text-sm text-white/90">Phases, KPIs, deltas et liens vers le tracking.</p>
        </div>
        <div className="overflow-auto bg-gradient-to-b from-white to-amber-50/20">
          <table className="min-w-[1100px] w-full text-sm">
            <thead className="border-b border-orange-100 bg-gradient-to-r from-amber-100/90 to-orange-100/80 text-xs font-bold uppercase tracking-wide text-amber-950">
              <tr>
                <th className="px-4 py-3 text-left font-medium">Campagne</th>
                <th className="px-4 py-3 text-left font-medium">Phases</th>
                <th className="px-4 py-3 text-left font-medium">Audience</th>
                <th className="px-4 py-3 text-left font-medium">Delivered</th>
                <th className="px-4 py-3 text-left font-medium">Détails</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <CampaignRowView key={c.campaign_id} campaign={c} setCampaigns={setCampaigns} />
              ))}
              {!filtered.length ? (
                <tr>
                  <td className="px-4 py-6 text-zinc-500" colSpan={5}>
                    Aucun envoi. Ajoutez des événements dans <span className="font-mono">data/sendgrid_events.jsonl</span>.
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

function CampaignRowView({
  campaign,
  setCampaigns,
}: {
  campaign: Campaign;
  setCampaigns: React.Dispatch<React.SetStateAction<Campaign[]>>;
}) {
  const [open, setOpen] = useState(true);
  return (
    <>
      <tr className="border-b border-orange-100/80 align-top bg-gradient-to-r from-white to-amber-50/30">
        <td className="px-4 py-4">
          <div className="text-sm font-semibold">{campaign.name}</div>
          <div className="mt-1 font-mono text-xs text-zinc-600">{campaign.campaign_id}</div>
        </td>
        <td className="px-4 py-4">{campaign.phases_count}</td>
        <td className="px-4 py-4">
          <div className="text-sm">{campaign.total_recipients}</div>
          <div className="text-xs text-zinc-500">
            prospects
            {campaign.total_recipients_total !== campaign.total_recipients ? (
              <span> (total events: {campaign.total_recipients_total})</span>
            ) : null}
          </div>
        </td>
        <td className="px-4 py-4">{campaign.total_delivered}</td>
        <td className="px-4 py-4">
          <button
            className="rounded-xl bg-gradient-to-r from-zinc-800 to-zinc-950 px-4 py-2 text-xs font-bold text-white shadow-md transition hover:brightness-110"
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Masquer" : "Voir"} phases
          </button>
        </td>
      </tr>
      {open ? (
        <tr className="border-b">
          <td className="px-4 pb-5 pt-0" colSpan={5}>
            <div className="mt-3 overflow-hidden rounded-2xl border border-orange-200/60 bg-white shadow-inner ring-1 ring-orange-100/80">
              <table className="min-w-[1100px] w-full text-sm">
                <thead className="border-b border-orange-100 bg-gradient-to-r from-[color:var(--brand-blue-pale)]/90 to-[color:var(--brand-cream)] text-xs font-bold uppercase tracking-wide text-[color:var(--brand-blue-navy)]">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">Phase</th>
                    <th className="px-4 py-3 text-left font-medium">Date</th>
                    <th className="px-4 py-3 text-left font-medium">Audience</th>
                    <th className="px-4 py-3 text-left font-medium">Delivered</th>
                    <th className="px-4 py-3 text-left font-medium">Open%</th>
                    <th className="px-4 py-3 text-left font-medium">Δ Open%</th>
                    <th className="px-4 py-3 text-left font-medium">CTR%</th>
                    <th className="px-4 py-3 text-left font-medium">Δ CTR%</th>
                    <th className="px-4 py-3 text-left font-medium">Intervenant</th>
                    <th className="px-4 py-3 text-left font-medium">Blocage</th>
                    <th className="px-4 py-3 text-left font-medium">Statut</th>
                    <th className="px-4 py-3 text-left font-medium">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {campaign.phases.map((p) => {
                    const drill = `/tracking?send_batch_id=${encodeURIComponent(p.phase_id)}`;
                    return (
                      <tr key={p.phase_id} className="border-b border-orange-50 last:border-b-0 odd:bg-white even:bg-cyan-50/20">
                        <td className="px-4 py-3 font-mono text-xs">{p.phase_id}</td>
                        <td className="px-4 py-3">{p.date || "—"}</td>
                        <td className="px-4 py-3">
                          {p.recipients_known}
                          {p.recipients_total !== p.recipients_known ? (
                            <span className="text-xs text-zinc-500"> (total {p.recipients_total})</span>
                          ) : null}
                        </td>
                        <td className="px-4 py-3">{p.delivered}</td>
                        <td className="px-4 py-3">{p.open_rate_pct.toFixed(2)}%</td>
                        <td className="px-4 py-3">
                          <Delta v={p.delta_open_rate_pct} />
                        </td>
                        <td className="px-4 py-3">{p.ctr_unique_pct.toFixed(2)}%</td>
                        <td className="px-4 py-3">
                          <Delta v={p.delta_ctr_unique_pct} />
                        </td>
                        <td className="px-4 py-3">
                          <InlineEdit
                            value={p.assignee || ""}
                            placeholder="Nom"
                            onCommit={async (val) => {
                              setCampaigns((cur) =>
                                cur.map((c) =>
                                  c.campaign_id !== campaign.campaign_id
                                    ? c
                                    : {
                                        ...c,
                                        phases: c.phases.map((x) =>
                                          x.phase_id === p.phase_id ? { ...x, assignee: val } : x,
                                        ),
                                      },
                                ),
                              );
                              await apiPatch(
                                `/api/campaigns/${encodeURIComponent(campaign.campaign_id)}/${encodeURIComponent(
                                  p.phase_id,
                                )}`,
                                { assignee: val },
                              );
                            }}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <InlineEdit
                            value={p.blocker_owner || ""}
                            placeholder="Qui bloque ?"
                            onCommit={async (val) => {
                              setCampaigns((cur) =>
                                cur.map((c) =>
                                  c.campaign_id !== campaign.campaign_id
                                    ? c
                                    : {
                                        ...c,
                                        phases: c.phases.map((x) =>
                                          x.phase_id === p.phase_id ? { ...x, blocker_owner: val } : x,
                                        ),
                                      },
                                ),
                              );
                              await apiPatch(
                                `/api/campaigns/${encodeURIComponent(campaign.campaign_id)}/${encodeURIComponent(
                                  p.phase_id,
                                )}`,
                                { blocker: val },
                              );
                            }}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <InlineEdit
                            value={p.status || ""}
                            placeholder="ex: en cours"
                            onCommit={async (val) => {
                              setCampaigns((cur) =>
                                cur.map((c) =>
                                  c.campaign_id !== campaign.campaign_id
                                    ? c
                                    : {
                                        ...c,
                                        phases: c.phases.map((x) =>
                                          x.phase_id === p.phase_id ? { ...x, status: val } : x,
                                        ),
                                      },
                                ),
                              );
                              await apiPatch(
                                `/api/campaigns/${encodeURIComponent(campaign.campaign_id)}/${encodeURIComponent(
                                  p.phase_id,
                                )}`,
                                { status: val },
                              );
                            }}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <a
                            className="inline-flex items-center rounded-xl bg-gradient-to-r from-cyan-600 to-[color:var(--brand-blue-deep)] px-3 py-2 text-xs font-bold text-white shadow-md transition hover:brightness-110"
                            href={drill}
                          >
                            Voir la source
                          </a>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      ) : null}
    </>
  );
}

function InlineEdit({
  value,
  placeholder,
  onCommit,
}: {
  value: string;
  placeholder: string;
  onCommit: (v: string) => Promise<void>;
}) {
  const [v, setV] = useState(value);
  const [saving, setSaving] = useState(false);

  useEffect(() => setV(value), [value]);

  return (
    <div className="flex items-center gap-2">
      <input
        value={v}
        onChange={(e) => setV(e.target.value)}
        placeholder={placeholder}
        className="w-44 rounded-lg border border-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)] px-2 py-1 text-xs outline-none focus:border-[color:color-mix(in_srgb,var(--brand-blue)_55%,transparent)]"
      />
      <button
        className="rounded-lg border border-[color:color-mix(in_srgb,var(--brand-blue)_28%,transparent)] bg-white px-2 py-1 text-xs hover:bg-zinc-50 disabled:opacity-60"
        disabled={saving}
        onClick={async () => {
          setSaving(true);
          try {
            await onCommit(v.trim());
          } finally {
            setSaving(false);
          }
        }}
      >
        {saving ? "…" : "OK"}
      </button>
    </div>
  );
}

