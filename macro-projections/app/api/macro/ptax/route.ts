import { NextResponse } from "next/server";

const PTAX_BASE =
  "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/";

export async function GET() {
  try {
    const currentYear = new Date().getFullYear();

    const url =
      `${PTAX_BASE}CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)` +
      `?@dataInicial='01-01-${currentYear}'` +
      `&@dataFinalCotacao='12-31-${currentYear}'` +
      `&$format=json` +
      `&$select=cotacaoCompra,cotacaoVenda,dataHoraCotacao`;

    const res = await fetch(url, {
      next: { revalidate: 3600 },
    });

    if (!res.ok) {
      throw new Error(`Failed to fetch PTAX data: ${res.status}`);
    }

    const json = await res.json();

    // Parse entries and extract year from dataHoraCotacao
    const entries = (json.value as { cotacaoCompra: number; cotacaoVenda: number; dataHoraCotacao: string }[]).map(
      (e) => {
        const date = e.dataHoraCotacao.split(" ")[0]; // "YYYY-MM-DD HH:MM:SS.0" -> "YYYY-MM-DD"
        const year = parseInt(date.substring(0, 4), 10);
        return {
          date,
          year,
          value: e.cotacaoVenda, // Use cotacaoVenda (sell rate) as per PTAX convention
        };
      }
    );

    // Sort by date ascending
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
    console.error("Error fetching PTAX data:", error);
    return NextResponse.json(
      { error: "Failed to fetch PTAX data" },
      { status: 500 }
    );
  }
}
