import type { Metadata } from "next";
import { ReturnFirstDashboard } from "@/components/return-first-dashboard";

export const metadata: Metadata = {
  title: "Forward record | Portfolio Optimizer",
  description: "How much untouched forward evidence has actually accumulated, and what the last decided books did on the weeks that have closed since.",
};

export default function ForwardPage() {
  return <ReturnFirstDashboard initialView="forward" />;
}
