import fs from "node:fs/promises";
import path from "node:path";

import { DashboardShell } from "@/components/dashboard-shell";
import { ExecutiveSummary } from "@/components/executive-summary";
import type { DashboardData } from "@/types/dashboard";

// Force dynamic rendering so the executive summary always reflects the latest JSON snapshot
// instead of a cached build-time copy. This guarantees external viewers (ChatGPT, cURL, crawlers)
// fetch live headline numbers on first paint.
export const dynamic = "force-dynamic";
export const revalidate = 0;

async function loadDashboardData(): Promise<DashboardData | null> {
  try {
    const filePath = path.join(process.cwd(), "public", "dashboard-data.json");
    const raw = await fs.readFile(filePath, "utf8");
    return JSON.parse(raw) as DashboardData;
  } catch {
    return null;
  }
}

export default async function Home() {
  const initialData = await loadDashboardData();
  return (
    <>
      <ExecutiveSummary data={initialData} />
      <DashboardShell initialData={initialData} />
    </>
  );
}
