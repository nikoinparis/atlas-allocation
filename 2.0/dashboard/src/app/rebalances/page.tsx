import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "Rebalances | Portfolio Optimizer",
  description: "Review recent portfolio changes, turnover, and forward validation progress.",
};

export default function RebalancesPage() {
  return <ReturnFirstDashboard initialView="rebalances" />;
}
