import type { Metadata } from "next";
import { ResearchStatus } from "@/components/research-status";

export const metadata: Metadata = {
  title: "Research status | Portfolio Optimizer",
  description: "What the research programme is doing now: forward clocks running, clocks starting, and every candidate family that has been tested and closed.",
};

export default function ResearchPage() {
  return <ResearchStatus />;
}
