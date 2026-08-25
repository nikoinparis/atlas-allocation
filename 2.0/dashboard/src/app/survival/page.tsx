import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "Survival Lab | Portfolio Optimizer",
  description: "Compare Monte Carlo, drawdown, cost, financing, concentration, and forward-evidence survival across every saved strategy.",
};

export default function SurvivalPage() {
  return <ReturnFirstDashboard initialView="survival" />;
}
