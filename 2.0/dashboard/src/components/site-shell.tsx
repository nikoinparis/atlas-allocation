"use client";

import Link from "next/link";
import { ChevronDown, Menu, X } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

export type ShellViewName = "overview" | "performance" | "metrics" | "compare" | "activity" | "rebalances" | "forward" | "replay" | "research" | "survival" | "methodology" | "guardrails";

export const viewDetails: Record<ShellViewName, { label: string; title: string; description: string; path: string }> = {
  overview: { label: "Overview", title: "Portfolio overview", description: "A clear read on performance, risk, and the portfolio’s latest systematic decision.", path: "/" },
  performance: { label: "Performance", title: "Performance", description: "Study the simulated equity curve, risk-adjusted results, and the complete current allocation.", path: "/performance" },
  activity: { label: "Daily activity", title: "Daily activity", description: "Inspect daily P&L, historical holdings, and every recorded change in the strategy book.", path: "/activity" },
  rebalances: { label: "Rebalances", title: "Rebalances", description: "Review recent portfolio changes, turnover, and the strategy’s forward-validation clock.", path: "/rebalances" },
  forward: { label: "Forward record", title: "Forward record", description: "See how much untouched forward evidence actually exists, and what the last decided books did on the weeks that have closed since.", path: "/forward" },
  replay: { label: "What-if replay", title: "What-if replay", description: "What $10,000 in each strategy would be worth today, marked every trading day from its start, using only books decided before the days they are marked on.", path: "/replay" },
  research: { label: "Research status", title: "Research status", description: "What the research programme is doing now: clocks running, clocks starting, and every candidate family that has been tested and closed.", path: "/research" },
  metrics: { label: "Strategy metrics", title: "Strategy metrics", description: "Return, risk, drawdown and market-exposure figures for every strategy on this dashboard, each with a plain-language explanation of what it measures and what it cannot tell you.", path: "/metrics" },
  compare: { label: "Compare strategies", title: "Compare strategies", description: "Every dashboard strategy side by side: backtest, before and after the 2025 melt-up, return over SPY at the same risk, and the last decided book held day by day since creation.", path: "/compare" },
  survival: { label: "Survival lab", title: "Real-world survival lab", description: "See which strategies survive modeled stress, what still fails, and why none is proven live yet.", path: "/survival" },
  methodology: { label: "How it works", title: "How the portfolio works", description: "Follow the selected strategy from raw evidence to target weights, costs, and the final recorded decision.", path: "/methodology" },
  guardrails: { label: "Guardrails", title: "Research guardrails", description: "Understand exactly what the simulation can do, what it cannot do, and how its evidence is controlled.", path: "/guardrails" },
};

const navGroups: { title: string; views: ShellViewName[] }[] = [
  { title: "Portfolio", views: ["overview", "performance", "activity", "rebalances"] },
  { title: "Compare", views: ["metrics", "compare", "replay"] },
  { title: "Evidence", views: ["forward", "research", "survival"] },
  { title: "Reference", views: ["methodology", "guardrails"] },
];

export type HeroStat = { value: string; label: string; tone?: "gain" | "loss" };

const defaultStats: { left: HeroStat[]; right: HeroStat[] } = {
  left: [{ value: "Research", label: "Simulated results only" }, { value: "0", label: "Strategies promoted" }],
  right: [{ value: "Offline", label: "No brokerage connection" }, { value: "0", label: "Live orders placed" }],
};

function HeroStats({ stats, side }: { stats: HeroStat[]; side: "left" | "right" }) {
  return (
    <dl className={`hero-stats hero-stats-${side}`}>
      {stats.map((stat) => (
        <div key={stat.label}>
          <dd className={stat.tone ?? ""}>{stat.value}</dd>
          <dt>{stat.label}</dt>
        </div>
      ))}
    </dl>
  );
}

export function SiteShell({ active, freshness, stats, cta, heroNote, toolbar, overlays, footerNote, children }: {
  active: ShellViewName;
  freshness?: string;
  stats?: { left: HeroStat[]; right: HeroStat[] };
  cta?: ReactNode;
  heroNote?: string;
  toolbar?: ReactNode;
  overlays?: ReactNode;
  footerNote?: string;
  children: ReactNode;
}) {
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const details = viewDetails[active];
  const heroStats = stats ?? defaultStats;
  const words = details.title.split(" ");
  const lastWord = words.pop();

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMobileOpen(false);
      setOpenGroup(null);
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  return (
    <main className="site-page">
      <header className="top-nav">
        <Link href="/" className="wordmark">Portfolio Optimizer</Link>
        <nav className="top-links" aria-label="Sections">
          {navGroups.map((group) => {
            const current = group.views.includes(active);
            const open = openGroup === group.title;
            return (
              <div key={group.title} className={`nav-menu ${open ? "open" : ""}`} onMouseEnter={() => setOpenGroup(group.title)} onMouseLeave={() => setOpenGroup(null)}>
                <button type="button" className={current ? "current" : ""} aria-expanded={open} aria-haspopup="true" onClick={() => setOpenGroup(open ? null : group.title)}>
                  {current && <i aria-hidden="true" />}{group.title}<ChevronDown size={13} />
                </button>
                {open && <div className="nav-popover">
                  {group.views.map((view) => (
                    <Link key={view} href={viewDetails[view].path} className={active === view ? "active" : ""} aria-current={active === view ? "page" : undefined} onClick={() => setOpenGroup(null)}>
                      <strong>{viewDetails[view].label}</strong>
                      <small>{viewDetails[view].description}</small>
                    </Link>
                  ))}
                </div>}
              </div>
            );
          })}
        </nav>
        <div className="top-actions">
          {freshness && <span className="freshness">{freshness}</span>}
          <span className="state-chip">Research only</span>
          <button className="mobile-menu-button" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
        </div>
      </header>

      {mobileOpen && <div className="mobile-sheet" role="dialog" aria-modal="true" aria-label="Navigation">
        <div className="mobile-sheet-head"><span className="wordmark">Portfolio Optimizer</span><button onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={20} /></button></div>
        {navGroups.map((group) => (
          <div key={group.title} className="mobile-sheet-group">
            <span>{group.title}</span>
            {group.views.map((view) => <Link key={view} href={viewDetails[view].path} className={active === view ? "active" : ""} onClick={() => setMobileOpen(false)}>{viewDetails[view].label}</Link>)}
          </div>
        ))}
        <p>Simulated results only. No brokerage or live order connection.</p>
      </div>}

      <section className="hero">
        <div className="hero-inner">
          <h1>{words.join(" ")}{words.length > 0 && " "}<em>{lastWord}.</em></h1>
          <HeroStats stats={heroStats.left} side="left" />
          <div className="hero-center">
            <p>{details.description}</p>
            {cta}
            {heroNote && <small>{heroNote}</small>}
          </div>
          <HeroStats stats={heroStats.right} side="right" />
        </div>
      </section>

      <div className="dashboard-content">
        <div className="content-frame">
          {toolbar}
          {children}
          <footer>
            <span>{footerNote ?? "Simulated research records. No brokerage or live order connection."}</span>
            <span>Past simulated performance does not guarantee future returns.</span>
          </footer>
        </div>
      </div>
      {overlays}
    </main>
  );
}
