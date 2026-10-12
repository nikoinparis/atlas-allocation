import type { Metadata } from "next";
import { StrategyCompare } from "@/components/strategy-compare";

export const metadata: Metadata = {
  title: "Compare strategies | Portfolio Optimizer",
  description: "Every dashboard strategy side by side: backtest, before and after the 2025 melt-up, return over SPY at the same risk, and the last decided book held day by day since creation.",
};

export default function ComparePage() {
  return <StrategyCompare />;
}
