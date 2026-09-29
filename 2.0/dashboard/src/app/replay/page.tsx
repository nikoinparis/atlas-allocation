import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "What-if replay | Portfolio Optimizer",
  description: "What $10,000 in each strategy would be worth today, marked every trading day from its start.",
};

export default function ReplayPage() {
  return <ReturnFirstDashboard initialView="replay" />;
}
