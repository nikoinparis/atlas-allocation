import fs from "node:fs/promises";
import path from "node:path";

import { DashboardShell } from "@/components/dashboard-shell";
import type { DashboardData } from "@/types/dashboard";

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
  return <DashboardShell initialData={initialData} />;
}
