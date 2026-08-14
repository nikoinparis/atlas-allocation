import { DashboardShell } from "@/components/dashboard-shell";
import { ExecutiveSummary } from "@/components/executive-summary";
import { compactBundleToDashboardData } from "@/lib/compact-dashboard";
import type { DashboardData } from "@/types/dashboard";
import compactBundle from "../../public/production-candidate-dashboard-bundle.json";

// Force dynamic rendering so the executive summary always reflects the latest JSON snapshot
// instead of a cached build-time copy. This guarantees external viewers (ChatGPT, cURL, crawlers)
// fetch live headline numbers on first paint.
export const dynamic = "force-dynamic";
export const revalidate = 0;

async function loadDashboardData(): Promise<DashboardData | null> {
  try {
    return compactBundleToDashboardData(compactBundle);
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
