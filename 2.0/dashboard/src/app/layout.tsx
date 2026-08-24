import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.VERCEL_PROJECT_PRODUCTION_URL
      ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
      : "http://localhost:3000",
  ),
  title: "Portfolio Optimizer | Systematic Research Dashboard",
  description: "Inspect simulated portfolio performance, allocation decisions, daily P&L, strategy methodology, guardrails, and frozen-strategy what-if scenarios.",
  openGraph: {
    title: "Portfolio Optimizer",
    description: "Systematic research, made inspectable.",
    images: ["/og-dark.png"],
  },
  twitter: {
    card: "summary_large_image",
    title: "Portfolio Optimizer",
    description: "Systematic research, made inspectable.",
    images: ["/og-dark.png"],
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
