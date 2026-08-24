import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "How It Works | Portfolio Optimizer",
  description: "Follow each portfolio strategy from evidence and selection rules through sizing, risk checks, costs, and saved target weights.",
};

export default function MethodologyPage() {
  return <ReturnFirstDashboard initialView="methodology" />;
}
