import type { FocusEntry, FocusData, MacroRow } from "./types";
import {
  IPCA_HISTORICAL,
  IGPM_HISTORICAL,
  SELIC_EOP_HISTORICAL,
  SELIC_AVG_HISTORICAL,
  BRLUSD_EOP_HISTORICAL,
  BRLUSD_AVG_HISTORICAL,
  PIB_HISTORICAL,
  PROJECTION_YEARS,
  HISTORICAL_YEARS,
  ESTIMATE_2025_YEAR,
} from "./historical-data";

const CURRENT_YEAR = 2026;

// ---- Focus helpers ----

function getLatestFocusDate(entries: FocusEntry[]): string {
  if (!entries.length) return "";
  return entries.map((e) => e.Data).sort().reverse()[0];
}

function focusMedian(
  entries: FocusEntry[],
  latestDate: string,
  year: number
): number {
  const yearStr = String(year);
  const match = entries.find(
    (e) => e.Data === latestDate && e.DataReferencia === yearStr
  );
  return match ? match.Mediana : 0;
}

// ---- IPCA projections ----
function calcIpcaProjections(
  entries: FocusEntry[],
  latestDate: string
): Record<number, number> {
  const result: Record<number, number> = {};
  let prevValue = IPCA_HISTORICAL[ESTIMATE_2025_YEAR];

  for (const year of PROJECTION_YEARS) {
    const median = focusMedian(entries, latestDate, year);
    const value = median === 0 ? prevValue : median / 100;
    result[year] = value;
    prevValue = value;
  }
  return result;
}

// ---- IGPM projections ----
function calcIgpmProjections(
  entries: FocusEntry[],
  latestDate: string
): Record<number, number> {
  const result: Record<number, number> = {};
  let prevValue = IGPM_HISTORICAL[ESTIMATE_2025_YEAR];

  for (const year of PROJECTION_YEARS) {
    const median = focusMedian(entries, latestDate, year);
    const value = median === 0 ? prevValue : median / 100;
    result[year] = value;
    prevValue = value;
  }
  return result;
}

// ---- Selic EOP projections (no fallback) ----
function calcSelicEopProjections(
  entries: FocusEntry[],
  latestDate: string
): Record<number, number> {
  const result: Record<number, number> = {};

  for (const year of PROJECTION_YEARS) {
    const median = focusMedian(entries, latestDate, year);
    result[year] = median / 100;
  }
  return result;
}

// ---- Selic Average projections ----
function calcSelicAvgProjections(
  selicEopProjections: Record<number, number>,
  selicDiaria: { date: string; year: number; value: number }[]
): Record<number, number> {
  const result: Record<number, number> = {};

  // Current year (CURRENT_YEAR) - complex formula
  const diasCurrentYear = selicDiaria.filter((d) => d.year === CURRENT_YEAR);
  const diasPrevYear = selicDiaria.filter((d) => d.year === CURRENT_YEAR - 1);

  if (diasCurrentYear.length > 0 && diasPrevYear.length > 0) {
    // Compute accumulated factor from start of data to end of prev year
    // fatorFimAnoAnterior = product of (1 + valor/100) for all days in prev year
    let fatorFimAnoAnterior = 1;
    for (const d of diasPrevYear) {
      fatorFimAnoAnterior *= 1 + d.value / 100;
    }

    // fatorAcumHoje = product of (1 + valor/100) for all days in current year up to latest
    let fatorAcumHoje = fatorFimAnoAnterior;
    for (const d of diasCurrentYear) {
      fatorAcumHoje *= 1 + d.value / 100;
    }

    // Latest daily selic rate
    const latestSelic = diasCurrentYear[diasCurrentYear.length - 1].value;
    const selicAnualizada = Math.pow(1 + latestSelic / 100, 252) - 1;

    const selicEop2026 = selicEopProjections[CURRENT_YEAR] ?? 0;
    const nDiasUteisDecorridos = diasCurrentYear.length;

    // selicAvg = (fatorAcumHoje / fatorFimAnoAnterior) *
    //            (1 + (selicEop + selicAnualizada) / 2) ^ ((252 - nDias) / 252) - 1
    const selicAvg =
      (fatorAcumHoje / fatorFimAnoAnterior) *
        Math.pow(
          1 + (selicEop2026 + selicAnualizada) / 2,
          (252 - nDiasUteisDecorridos) / 252
        ) -
      1;

    result[CURRENT_YEAR] = selicAvg;
  } else {
    // Fallback if no daily data: use midpoint of prev EOP and current EOP
    result[CURRENT_YEAR] =
      (SELIC_EOP_HISTORICAL[ESTIMATE_2025_YEAR] +
        (selicEopProjections[CURRENT_YEAR] ?? 0)) /
      2;
  }

  // Future years: average of EOP prev year and EOP current year
  let prevEop = selicEopProjections[CURRENT_YEAR] ?? 0;
  for (let i = 1; i < PROJECTION_YEARS.length; i++) {
    const year = PROJECTION_YEARS[i];
    const eopThisYear = selicEopProjections[year] ?? 0;
    result[year] = (prevEop + eopThisYear) / 2;
    prevEop = eopThisYear;
  }

  return result;
}

// ---- BRL/USD EOP projections ----
function calcCambioEopProjections(
  entries: FocusEntry[],
  latestDate: string
): Record<number, number> {
  const result: Record<number, number> = {};
  let prevValue = BRLUSD_EOP_HISTORICAL[ESTIMATE_2025_YEAR];

  for (const year of PROJECTION_YEARS) {
    const median = focusMedian(entries, latestDate, year);
    const value = median === 0 ? prevValue : median; // Câmbio NOT divided by 100
    result[year] = value;
    prevValue = value;
  }
  return result;
}

// ---- BRL/USD Average projections ----
function calcCambioAvgProjections(
  cambioEopProjections: Record<number, number>,
  ptaxEntries: { date: string; year: number; value: number }[]
): Record<number, number> {
  const result: Record<number, number> = {};

  // Current year: complex formula
  const ptax2026 = ptaxEntries.filter((d) => d.year === CURRENT_YEAR);

  if (ptax2026.length > 0) {
    const avgPtax =
      ptax2026.reduce((sum, d) => sum + d.value, 0) / ptax2026.length;
    const nDias = ptax2026.length;
    const ptaxLatest = ptax2026[ptax2026.length - 1].value;
    const cambioEop2026 = cambioEopProjections[CURRENT_YEAR] ?? 0;

    const avg2026 =
      avgPtax * (nDias / 252) +
      ((ptaxLatest + cambioEop2026) / 2) * (1 - nDias / 252);

    result[CURRENT_YEAR] = avg2026;
  } else {
    // Fallback
    result[CURRENT_YEAR] =
      (BRLUSD_EOP_HISTORICAL[ESTIMATE_2025_YEAR] +
        (cambioEopProjections[CURRENT_YEAR] ?? 0)) /
      2;
  }

  // Future years: average of EOP prev year and EOP current year
  let prevEop = cambioEopProjections[CURRENT_YEAR] ?? 0;
  for (let i = 1; i < PROJECTION_YEARS.length; i++) {
    const year = PROJECTION_YEARS[i];
    const eopThisYear = cambioEopProjections[year] ?? 0;
    result[year] = (prevEop + eopThisYear) / 2;
    prevEop = eopThisYear;
  }

  return result;
}

// ---- PIB projections ----
function calcPibProjections(
  entries: FocusEntry[],
  latestDate: string
): Record<number, number> {
  const result: Record<number, number> = {};
  let prevValue = PIB_HISTORICAL[ESTIMATE_2025_YEAR];

  for (const year of PROJECTION_YEARS) {
    const median = focusMedian(entries, latestDate, year);
    const value = median === 0 ? prevValue : median / 100;
    result[year] = value;
    prevValue = value;
  }
  return result;
}

// ---- Build historical record including 2025e ----
function buildHistorical<T extends Record<number, number>>(data: T): T {
  return data;
}

// ---- Main calculation function ----
export function calculateMacroRows(
  focusData: FocusData,
  ptaxEntries: { date: string; year: number; value: number }[],
  selicDiaria: { date: string; year: number; value: number }[]
): MacroRow[] {
  const { ipca, igpm, selic, cambio, pib, latestDate } = focusData;

  // Projections
  const ipcaProj = calcIpcaProjections(ipca, latestDate);
  const igpmProj = calcIgpmProjections(igpm, latestDate);
  const selicEopProj = calcSelicEopProjections(selic, latestDate);
  const selicAvgProj = calcSelicAvgProjections(selicEopProj, selicDiaria);
  const cambioEopProj = calcCambioEopProjections(cambio, latestDate);
  const cambioAvgProj = calcCambioAvgProjections(cambioEopProj, ptaxEntries);
  const pibProj = calcPibProjections(pib, latestDate);

  return [
    {
      section: "inflation",
      sectionHeader: "Inflação",
      label: "IPCA - EoP",
      sublabel: "Y/Y",
      format: "percent",
      historical: buildHistorical(IPCA_HISTORICAL),
      projections: ipcaProj,
    },
    {
      section: "inflation",
      label: "IGPM - EoP",
      sublabel: "Y/Y",
      format: "percent",
      historical: buildHistorical(IGPM_HISTORICAL),
      projections: igpmProj,
    },
    {
      section: "rates",
      sectionHeader: "Taxa de Juros",
      label: "Taxa Selic - EOP",
      format: "percent",
      historical: buildHistorical(SELIC_EOP_HISTORICAL),
      projections: selicEopProj,
    },
    {
      section: "rates",
      label: "Taxa Selic - Average",
      format: "percent",
      historical: buildHistorical(SELIC_AVG_HISTORICAL),
      projections: selicAvgProj,
    },
    {
      section: "fx",
      sectionHeader: "Câmbio",
      label: "BRL/USD - EOP",
      format: "decimal",
      historical: buildHistorical(BRLUSD_EOP_HISTORICAL),
      projections: cambioEopProj,
    },
    {
      section: "fx",
      label: "BRL/USD - Average",
      format: "decimal",
      historical: buildHistorical(BRLUSD_AVG_HISTORICAL),
      projections: cambioAvgProj,
    },
    {
      section: "gdp",
      sectionHeader: "PIB",
      label: "PIB Y/Y",
      format: "percent",
      historical: buildHistorical(PIB_HISTORICAL),
      projections: pibProj,
    },
  ];
}

export { HISTORICAL_YEARS, ESTIMATE_2025_YEAR, PROJECTION_YEARS };
