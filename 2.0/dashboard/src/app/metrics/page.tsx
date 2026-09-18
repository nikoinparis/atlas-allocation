import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "Strategy Metrics | Portfolio Optimizer",
  description: "Return, risk, drawdown and market-exposure metrics for every strategy, with a plain-language explanation of what each one means.",
};

export default function MetricsPage() {
  return <ReturnFirstDashboard initialView="metrics" />;
}
