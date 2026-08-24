import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "Daily Activity | Portfolio Optimizer",
  description: "Inspect daily simulated P&L, holdings, and recorded allocation changes.",
};

export default function ActivityPage() {
  return <ReturnFirstDashboard initialView="activity" />;
}
