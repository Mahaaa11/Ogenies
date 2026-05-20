import type { ReactNode } from "react";

type PageHeroProps = {
  eyebrow?: string;
  title: string;
  description: string;
  children?: ReactNode;
  /** Barre du bas + halo : uniquement bleu / jaune / orange / crème */
  variant?: "cyan" | "violet" | "amber" | "emerald" | "rose";
};

const bands: Record<NonNullable<PageHeroProps["variant"]>, string> = {
  /* Bleus (nuances) */
  cyan: "from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue-deep)] to-[color:var(--brand-blue)]",
  /* Bleu → ciel (toujours famille bleue) */
  violet: "from-[color:var(--brand-blue-deep)] via-[color:var(--brand-blue)] to-[color:var(--brand-blue-sky)]",
  /* Orange → jaune */
  amber: "from-[color:var(--brand-orange-deep)] via-[color:var(--brand-orange)] to-[color:var(--brand-yellow)]",
  /* Bleu nuit → bleu → touche jaune */
  emerald: "from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue)] to-[color:var(--brand-yellow-soft)]",
  /* Bleu → orange → jaune (bandeau « chaud ») */
  rose: "from-[color:var(--brand-blue-deep)] via-[color:var(--brand-orange)] to-[color:var(--brand-yellow)]",
};

export function PageHero({ eyebrow, title, description, children, variant = "cyan" }: PageHeroProps) {
  const grad = bands[variant];
  return (
    <div className="relative overflow-hidden rounded-3xl shadow-2xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_12%,transparent)]">
      <div className={`absolute inset-0 bg-gradient-to-br ${grad} opacity-[0.14]`} />
      <div className="absolute -right-20 -top-20 h-56 w-56 rounded-full bg-gradient-to-br from-[color:var(--brand-yellow-soft)]/50 to-transparent blur-3xl" />
      <div className="relative border border-white/60 bg-[color:color-mix(in_srgb,var(--brand-cream)_88%,white)] px-6 py-6 backdrop-blur-md md:px-8 md:py-7">
        {eyebrow ? (
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-[color:var(--brand-blue-deep)]/80">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="mt-1 bg-gradient-to-r from-[color:var(--brand-blue-navy)] via-[color:var(--brand-blue)] to-[color:var(--brand-orange)] bg-clip-text text-3xl font-black tracking-tight text-transparent md:text-4xl">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600">{description}</p>
        {children ? <div className="mt-5 flex flex-wrap items-center gap-3">{children}</div> : null}
      </div>
      <div className={`h-1.5 w-full bg-gradient-to-r ${grad}`} />
    </div>
  );
}

export function GradientTableShell({
  title,
  subtitle,
  barVariant = "cyan",
  children,
}: {
  title: string;
  subtitle?: string;
  barVariant?: keyof typeof bands;
  children: ReactNode;
}) {
  const grad = bands[barVariant];
  return (
    <div className="overflow-hidden rounded-3xl border-0 bg-white shadow-2xl ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_14%,transparent)]">
      <div className={`bg-gradient-to-r ${grad} px-5 py-3.5 text-white`}>
        <h2 className="text-base font-bold tracking-tight text-white drop-shadow-sm">{title}</h2>
        {subtitle ? <p className="mt-0.5 text-sm text-[color:var(--brand-cream)]/95">{subtitle}</p> : null}
      </div>
      <div className="bg-gradient-to-b from-[color:var(--brand-cream)]/50 via-white to-[color:var(--brand-blue-pale)]/25">
        {children}
      </div>
    </div>
  );
}
