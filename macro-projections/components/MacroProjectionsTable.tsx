"use client";

import type { MacroRow } from "@/lib/types";
import { HISTORICAL_YEARS, ESTIMATE_2025_YEAR, PROJECTION_YEARS } from "@/lib/calculations";

interface Props {
  rows: MacroRow[];
  latestDate: string;
}

function formatValue(value: number | undefined, format: "percent" | "decimal"): string {
  if (value === undefined || isNaN(value)) return "—";

  const isNegative = value < 0;
  const abs = Math.abs(value);

  if (format === "percent") {
    const formatted = (abs * 100).toFixed(2) + "%";
    return isNegative ? `(${formatted})` : formatted;
  } else {
    const formatted = abs.toFixed(2);
    return isNegative ? `(${formatted})` : formatted;
  }
}

const SECTION_COLORS: Record<MacroRow["section"], string> = {
  inflation: "bg-blue-50",
  rates: "bg-green-50",
  fx: "bg-yellow-50",
  gdp: "bg-purple-50",
};

const SECTION_HEADER_COLORS: Record<MacroRow["section"], string> = {
  inflation: "bg-blue-100 text-blue-900",
  rates: "bg-green-100 text-green-900",
  fx: "bg-yellow-100 text-yellow-900",
  gdp: "bg-purple-100 text-purple-900",
};

const ALL_DISPLAY_YEARS = [...HISTORICAL_YEARS, ESTIMATE_2025_YEAR];
const CURRENT_YEAR = 2026;

export default function MacroProjectionsTable({ rows, latestDate }: Props) {
  const formattedLatestDate = latestDate
    ? new Date(latestDate + "T00:00:00").toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : "—";

  return (
    <div className="font-sans">
      {/* Title */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">
          Projeções Macroeconômicas — Brasil
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Real Investor Asset Management
        </p>
      </div>

      {/* Table wrapper with horizontal scroll */}
      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="border-collapse text-xs" style={{ minWidth: "max-content" }}>
          <thead>
            <tr>
              {/* Label column header */}
              <th
                className="sticky left-0 z-20 bg-[#002060] text-white font-bold px-3 py-2 text-left whitespace-nowrap border-r border-blue-800 min-w-[180px]"
                style={{ minWidth: 180 }}
              >
                Macro
              </th>

              {/* Historical years */}
              {HISTORICAL_YEARS.map((year) => (
                <th
                  key={year}
                  className="bg-[#1f3f7a] text-white font-bold px-3 py-2 text-center whitespace-nowrap border-r border-blue-800 min-w-[64px]"
                >
                  {year}
                </th>
              ))}

              {/* 2025e */}
              <th className="bg-[#002060] text-white font-bold px-3 py-2 text-center whitespace-nowrap border-r border-blue-800 min-w-[64px]">
                2025e
              </th>

              {/* Current year highlighted */}
              <th className="bg-[#002060] text-[#FFD700] font-bold px-3 py-2 text-center whitespace-nowrap border-r border-blue-900 min-w-[72px] border-l-2 border-l-yellow-400">
                {CURRENT_YEAR}e ★
              </th>

              {/* Future projection years */}
              {PROJECTION_YEARS.filter((y) => y > CURRENT_YEAR).map((year) => (
                <th
                  key={year}
                  className="bg-[#002060] text-gray-300 font-bold px-3 py-2 text-center whitespace-nowrap border-r border-blue-800 min-w-[64px]"
                >
                  {year}e
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.map((row, rowIdx) => {
              const sectionBg = SECTION_COLORS[row.section];
              const sectionHeaderBg = SECTION_HEADER_COLORS[row.section];

              return (
                <>
                  {/* Section header row */}
                  {row.sectionHeader && (
                    <tr key={`section-${rowIdx}`}>
                      <td
                        colSpan={ALL_DISPLAY_YEARS.length + PROJECTION_YEARS.length + 1}
                        className={`sticky left-0 font-bold text-xs px-3 py-1.5 uppercase tracking-wider border-t-2 border-b border-gray-300 ${sectionHeaderBg}`}
                      >
                        {row.sectionHeader}
                      </td>
                    </tr>
                  )}

                  {/* Data row */}
                  <tr
                    key={`row-${rowIdx}`}
                    className={`border-b border-gray-200 hover:brightness-95 transition-all ${sectionBg}`}
                  >
                    {/* Label */}
                    <td className={`sticky left-0 z-10 px-3 py-2 whitespace-nowrap border-r border-gray-300 font-medium text-gray-800 ${sectionBg}`}>
                      <div>{row.label}</div>
                      {row.sublabel && (
                        <div className="text-[10px] text-gray-500 font-normal">
                          {row.sublabel}
                        </div>
                      )}
                    </td>

                    {/* Historical data */}
                    {HISTORICAL_YEARS.map((year) => {
                      const val = row.historical[year];
                      const isNeg = val !== undefined && val < 0;
                      return (
                        <td
                          key={year}
                          className={`px-3 py-2 text-center tabular-nums border-r border-gray-100 text-gray-700 ${
                            isNeg ? "text-red-600" : ""
                          }`}
                        >
                          {formatValue(val, row.format)}
                        </td>
                      );
                    })}

                    {/* 2025e - hardcoded estimate */}
                    {(() => {
                      const val = row.historical[ESTIMATE_2025_YEAR];
                      const isNeg = val !== undefined && val < 0;
                      return (
                        <td
                          className={`px-3 py-2 text-center tabular-nums border-r border-gray-200 font-medium ${
                            isNeg ? "text-red-600" : "text-gray-800"
                          }`}
                        >
                          {formatValue(val, row.format)}
                        </td>
                      );
                    })()}

                    {/* 2026e - current year projection (highlighted) */}
                    {(() => {
                      const val = row.projections[CURRENT_YEAR];
                      const isNeg = val !== undefined && val < 0;
                      return (
                        <td
                          className={`px-3 py-2 text-center tabular-nums border-r border-gray-300 font-bold border-l-2 border-l-yellow-400 ${
                            isNeg ? "text-red-700" : "text-blue-700"
                          }`}
                          style={{ backgroundColor: "#FFFFF0" }}
                        >
                          {formatValue(val, row.format)}
                        </td>
                      );
                    })()}

                    {/* Future projection years */}
                    {PROJECTION_YEARS.filter((y) => y > CURRENT_YEAR).map((year) => {
                      const val = row.projections[year];
                      const isNeg = val !== undefined && val < 0;
                      return (
                        <td
                          key={year}
                          className={`px-3 py-2 text-center tabular-nums border-r border-gray-100 font-medium ${
                            isNeg ? "text-red-600" : "text-blue-600"
                          }`}
                          style={{ backgroundColor: "#FAFFF5" }}
                        >
                          {formatValue(val, row.format)}
                        </td>
                      );
                    })}
                  </tr>
                </>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="mt-4 p-3 bg-gray-50 rounded-lg border border-gray-200 text-xs text-gray-600 space-y-1">
        <div className="flex items-center gap-2 font-semibold text-gray-700">
          <span>📊</span>
          <span>Fonte: Focus - BCB (Banco Central do Brasil)</span>
        </div>
        <div>
          <span className="font-medium">Última atualização (Focus):</span>{" "}
          {formattedLatestDate}
        </div>
        <div className="flex flex-wrap gap-4 mt-2">
          <a
            href="https://www.bcb.gov.br/publicacoes/focus"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            Relatório Focus →
          </a>
          <a
            href="https://www3.bcb.gov.br/expectativas/publico/consulta/serieestatisticas"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            Séries de Expectativas BCB →
          </a>
        </div>
        <div className="mt-2 text-gray-400 text-[10px]">
          * Valores entre parênteses indicam números negativos. &nbsp;
          ★ Ano corrente destacado. &nbsp;
          Colunas "e" = estimativas/projeções (Focus BCB).
        </div>
      </div>

      {/* Legend */}
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-500">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 bg-gray-200 rounded border border-gray-300" />
          <span>Histórico</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 bg-gray-100 rounded border border-gray-300" />
          <span>2025e (fixo)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 rounded border-2 border-yellow-400" style={{ backgroundColor: "#FFFFF0" }} />
          <span>2026e (Focus - ano corrente)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-4 rounded border border-gray-200" style={{ backgroundColor: "#FAFFF5" }} />
          <span>2027e+ (Focus - projeção)</span>
        </div>
      </div>
    </div>
  );
}
