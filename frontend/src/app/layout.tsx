import type { Metadata } from "next";
import Image from "next/image";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";
import {
  Activity,
  BarChart3,
  Gauge,
  LayoutDashboard,
  MailCheck,
  Send,
  Users,
} from "lucide-react";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "L&C Emailing",
  description: "Agent IA + Emailing + KPIs + Tracking",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const logoSrc = process.env.NEXT_PUBLIC_LOGO_PATH ?? "/lc-logo.png";
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-lc text-zinc-950">
        <div className="mx-auto grid min-h-screen w-full max-w-7xl grid-cols-1 gap-6 px-4 py-6 md:grid-cols-[280px_1fr] md:px-6">
          <aside className="hidden md:block">
            <div className="sticky top-6 rounded-3xl border border-white/10 bg-white/60 p-4 shadow-[0_1px_0_0_rgba(255,255,255,.6),0_30px_80px_-40px_rgba(0,0,0,.45)] backdrop-blur">
              <div className="flex flex-col items-center gap-1 px-2 py-3">
                <Image
                  src={logoSrc}
                  alt="Lead & Connect — Emailing"
                  width={476}
                  height={282}
                  priority
                  className="h-auto w-40"
                />
                <div className="text-[11px] uppercase tracking-widest text-zinc-500">Emailing</div>
              </div>

              <nav className="mt-4 space-y-1">
                <SideLink href="/" icon={<LayoutDashboard className="h-4 w-4" />} title="Dashboard" />
                <SideLink href="/campaigns" icon={<BarChart3 className="h-4 w-4" />} title="Campagnes" />
                <SideLink href="/recommendations" icon={<Users className="h-4 w-4" />} title="Prospects" />
                <SideLink href="/tracking" icon={<Activity className="h-4 w-4" />} title="Tracking" />
                <div className="my-3 h-px bg-black/5" />
                <SideLink href="/actions" icon={<Send className="h-4 w-4" />} title="Actions" />
              </nav>

              <div className="mt-6 rounded-2xl border border-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)] bg-white/70 p-4">
                <div className="text-xs font-semibold text-zinc-700">Live API</div>
                <div className="mt-1 text-xs text-zinc-500">
                  <span className="font-mono">
                    {process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-[11px] text-zinc-600">
                  <MiniStat icon={<Gauge className="h-4 w-4" />} label="KPI" />
                  <MiniStat icon={<BarChart3 className="h-4 w-4" />} label="Scoring" />
                  <MiniStat icon={<MailCheck className="h-4 w-4" />} label="Send" />
                </div>
              </div>
            </div>
          </aside>

          <div className="flex flex-col">
            <header className="mb-6 flex items-center justify-between rounded-3xl border border-white/10 bg-white/60 px-5 py-4 shadow-[0_1px_0_0_rgba(255,255,255,.6),0_25px_70px_-40px_rgba(0,0,0,.45)] backdrop-blur md:hidden">
              <div className="flex items-center gap-3">
                <Image
                  src={logoSrc}
                  alt="Lead & Connect — Emailing"
                  width={476}
                  height={282}
                  priority
                  className="h-auto w-24"
                />
              </div>
              <div className="flex items-center gap-3 text-sm">
                <a className="text-zinc-700 hover:text-zinc-950" href="/">
                  Dashboard
                </a>
                <a className="text-zinc-700 hover:text-zinc-950" href="/actions">
                  Actions
                </a>
              </div>
            </header>

            <main className="flex-1">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}

function SideLink({
  href,
  title,
  icon,
}: {
  href: string;
  title: string;
  icon: React.ReactNode;
}) {
  return (
    <a
      href={href}
      className={cn(
        "flex items-center gap-3 rounded-2xl px-3 py-2 text-sm text-zinc-700 hover:bg-white/70 hover:text-zinc-950",
      )}
    >
      <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-zinc-950/5 text-zinc-800">
        {icon}
      </span>
      <span className="font-medium">{title}</span>
    </a>
  );
}

function MiniStat({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl bg-zinc-50/70 px-2 py-2 ring-1 ring-[color:color-mix(in_srgb,var(--brand-blue)_22%,transparent)]">
      <span className="text-zinc-700">{icon}</span>
      <span className="truncate">{label}</span>
    </div>
  );
}
