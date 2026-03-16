import MacroProjectionsTable from "@/components/MacroProjectionsTable";
import { calculateMacroRows } from "@/lib/calculations";
import type { FocusData } from "@/lib/types";

async function fetchFocusData(): Promise<FocusData | null> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000"}/api/macro/focus`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchPtaxData(): Promise<{ date: string; year: number; value: number }[]> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000"}/api/macro/ptax`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return [];
    const json = await res.json();
    return json.entries ?? [];
  } catch {
    return [];
  }
}

async function fetchSelicDiaria(): Promise<{ date: string; year: number; value: number }[]> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3000"}/api/macro/selic-diaria`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return [];
    const json = await res.json();
    return json.entries ?? [];
  } catch {
    return [];
  }
}

// Empty focus data structure for fallback
function emptyFocusData(): FocusData {
  return { ipca: [], igpm: [], selic: [], cambio: [], pib: [], latestDate: "" };
}

export default async function MacroProjectionsPage() {
  const [focusData, ptaxEntries, selicDiaria] = await Promise.all([
    fetchFocusData(),
    fetchPtaxData(),
    fetchSelicDiaria(),
  ]);

  const focus = focusData ?? emptyFocusData();
  const rows = calculateMacroRows(focus, ptaxEntries, selicDiaria);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <MacroProjectionsTable rows={rows} latestDate={focus.latestDate} />
    </main>
  );
}

export const metadata = {
  title: "Projeções Macro — Real Investor",
  description: "Tabela de projeções macroeconômicas do Brasil — Real Investor Asset Management",
};
