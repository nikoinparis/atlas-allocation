import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "Performance | Portfolio Optimizer",
  description: "Inspect simulated performance, risk-adjusted results, and current allocation.",
};

export default function PerformancePage() {
  return <ReturnFirstDashboard initialView="performance" />;
}
