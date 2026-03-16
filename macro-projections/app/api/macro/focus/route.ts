import { NextResponse } from "next/server";
import type { FocusEntry, FocusData } from "@/lib/types";

const BCB_BASE =
  "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/";

async function fetchFocusIndicator(indicator: string): Promise<FocusEntry[]> {
  const encodedIndicator = encodeURIComponent(indicator);
  const url = `${BCB_BASE}ExpectativasMercadoAnuais?$filter=Indicador%20eq%20'${encodedIndicator}'&$orderby=Data%20desc&$top=500&$format=json&$select=Indicador,Data,DataReferencia,Media,Mediana,DesvioPadrao,Minimo,Maximo`;

  const res = await fetch(url, {
    next: { revalidate: 3600 },
  });

  if (!res.ok) {
    throw new Error(
      `Failed to fetch Focus data for ${indicator}: ${res.status}`
    );
  }

  const json = await res.json();
  return json.value as FocusEntry[];
}

export async function GET() {
  try {
    const [ipca, igpm, selic, cambio, pib] = await Promise.all([
      fetchFocusIndicator("IPCA"),
      fetchFocusIndicator("IGP-M"),
      fetchFocusIndicator("Selic"),
      fetchFocusIndicator("Câmbio"),
      fetchFocusIndicator("PIB Total"),
    ]);

    // Find the latest date across all indicators
    const allDates = [...ipca, ...igpm, ...selic, ...cambio, ...pib]
      .map((e) => e.Data)
      .sort()
      .reverse();

    const latestDate = allDates[0] ?? "";

    const data: FocusData = {
      ipca,
      igpm,
      selic,
      cambio,
      pib,
      latestDate,
    };

    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "s-maxage=3600, stale-while-revalidate=7200",
      },
    });
  } catch (error) {
    console.error("Error fetching Focus data:", error);
    return NextResponse.json(
      { error: "Failed to fetch Focus data" },
      { status: 500 }
    );
  }
}
