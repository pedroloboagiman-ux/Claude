import { NextResponse } from "next/server";

// SGS Serie 11 = SELIC diária (rendimento)
const SGS_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados";

export async function GET() {
  try {
    const currentYear = new Date().getFullYear();
    // Fetch from start of previous year to get the end-of-year factor
    const startYear = currentYear - 1;

    const url =
      `${SGS_BASE}?formato=json` +
      `&dataInicial=01/01/${startYear}` +
      `&dataFinal=31/12/${currentYear}`;

    const res = await fetch(url, {
      next: { revalidate: 3600 },
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch SELIC diária: ${res.status}`);
    }

    const json = (await res.json()) as { data: string; valor: string }[];

    // Parse and tag each entry with year
    const entries = json.map((e) => {
      // data format: "DD/MM/YYYY"
      const parts = e.data.split("/");
      const year = parseInt(parts[2], 10);
      const month = parseInt(parts[1], 10);
      const day = parseInt(parts[0], 10);
      const dateIso = `${parts[2]}-${parts[1].padStart(2, "0")}-${parts[0].padStart(2, "0")}`;
      return {
        date: dateIso,
        year,
        month,
        day,
        value: parseFloat(e.valor),
      };
    });

    // Sort ascending
    entries.sort((a, b) => a.date.localeCompare(b.date));

    return NextResponse.json(
      { entries },
      {
        headers: {
          "Cache-Control": "s-maxage=3600, stale-while-revalidate=7200",
        },
      }
    );
  } catch (error) {
    console.error("Error fetching SELIC diária:", error);
    return NextResponse.json(
      { error: "Failed to fetch SELIC diária" },
      { status: 500 }
    );
  }
}
