import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "Guardrails | Portfolio Optimizer",
  description: "Understand the execution boundary, evidence controls, costs, and research disclosures.",
};

export default function GuardrailsPage() {
  return <ReturnFirstDashboard initialView="guardrails" />;
}
