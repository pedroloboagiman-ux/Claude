export interface FocusEntry {
  Indicador: string;
  Data: string;
  DataReferencia: string;
  Media: number;
  Mediana: number;
  DesvioPadrao: number;
  Minimo: number;
  Maximo: number;
}

export interface FocusResponse {
  value: FocusEntry[];
}

export interface PtaxEntry {
  cotacaoCompra: number;
  cotacaoVenda: number;
  dataHoraCotacao: string;
}

export interface PtaxResponse {
  value: PtaxEntry[];
}

export interface SelicDiariaEntry {
  data: string;
  valor: string;
}

export interface MacroRow {
  section: "inflation" | "rates" | "fx" | "gdp";
  sectionHeader?: string;
  label: string;
  sublabel?: string;
  format: "percent" | "decimal";
  historical: Record<number, number>;
  projections: Record<number, number>;
}

export interface MacroData {
  rows: MacroRow[];
  latestDate: string;
}

export interface FocusData {
  ipca: FocusEntry[];
  igpm: FocusEntry[];
  selic: FocusEntry[];
  cambio: FocusEntry[];
  pib: FocusEntry[];
  latestDate: string;
}

export interface PtaxData {
  entries: { date: string; year: number; value: number }[];
}

export interface SelicDiariaData {
  entries: { date: string; year: number; value: number }[];
}
