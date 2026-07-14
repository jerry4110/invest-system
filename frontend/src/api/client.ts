// API 클라이언트 — 모든 백엔드 호출은 이 모듈을 경유 (로직은 backend/services에)
export interface HealthResponse {
  status: string;
  version: string;
  as_of: string; // 기준시각 (NFR-04)
}

export interface Settings {
  watch_folder: string;
  watch_enabled: boolean;
  refresh_time: string;
}

export interface Indicator {
  code: string;
  name: string;
  category: "index" | "macro";
  value: number;
  change_pct: number;
  date: string;
  as_of: string; // 기준시각 (NFR-04)
  spark: number[];
}

export interface RefreshResult {
  ok: number;
  failed: string[];
  as_of: string;
}

export interface HoldingRow {
  account: string; name: string; ticker: string; market: string;
  qty: number; avg_price: number; buy_amount: number; cur_price: number;
  eval_amount: number; pnl_amount: number; pnl_pct: number; weight_pct: number;
  as_of: string;
}

export interface PortfolioData {
  holdings: HoldingRow[];
  totals: { buy_amount: number; eval_amount: number; pnl_amount: number;
            pnl_pct: number; cash: number; total_asset: number };
  as_of: string | null;
}

export interface AssetSummary {
  total_asset: number; total_buy: number; total_eval: number;
  total_pnl: number; total_pnl_pct: number; total_cash: number;
  day_change: { amount: number; pct: number; vs_date: string } | null;
  composition: { label: string; amount: number; pct: number }[];
  as_of: string;
}

export interface StrategyData {
  persona: "value" | "growth" | "trader";
  guideline_text: string;
  version: number;
  updated_at: string;
  files: { id: number; filename: string; uploaded_at: string }[];
  allocation: Record<string, number>;
}

export interface JobLogItem {
  job_name: string;
  status: "success" | "partial" | "failed" | "running";
  started_at: string;
  duration_sec: number | null;
  message: string;
}

export interface JournalTx {
  id: number; ticker: string; side: "buy" | "sell"; qty: number; price: number;
  executed_at: string; realized_pnl: number | null; note: string;
}

export interface JournalStats {
  sell_count: number; total_realized_pnl: number; win_rate_pct: number;
  payoff_ratio: number | null;
  monthly: { month: string; realized_pnl: number }[];
}

export interface SecretItem {
  key: string;
  masked: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${path} 실패: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => req<HealthResponse>("/api/health"),
  getSummary: () => req<AssetSummary>("/api/dashboard/summary"),
  getIndicators: () => req<Indicator[]>("/api/dashboard/indicators"),
  refreshIndicators: () => req<RefreshResult>("/api/dashboard/refresh", { method: "POST" }),
  getSettings: () => req<Settings>("/api/settings"),
  updateSettings: (s: Partial<Settings>) =>
    req<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(s) }),
  uploadTrades: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/journal/upload", { method: "POST", body: fd });
    if (!res.ok) throw new Error(String(res.status));
    return res.json() as Promise<{ imported: number }>;
  },
  getTransactions: () => req<JournalTx[]>("/api/journal/transactions"),
  setTxNote: (id: number, note: string) =>
    req<{ ok: boolean }>(`/api/journal/transactions/${id}/note`, { method: "PUT", body: JSON.stringify({ note }) }),
  getJournalStats: () => req<JournalStats>("/api/journal/stats"),
  getStrategy: () => req<StrategyData>("/api/strategy"),
  setPersona: (persona: string) =>
    req<StrategyData>("/api/strategy/persona", { method: "PUT", body: JSON.stringify({ persona }) }),
  saveGuideline: (text: string) =>
    req<{ version: number }>("/api/strategy/guideline", { method: "PUT", body: JSON.stringify({ text }) }),
  saveAllocation: (alloc: Record<string, number>) =>
    req<{ ok: boolean }>("/api/strategy/allocation", { method: "PUT", body: JSON.stringify(alloc) }),
  uploadStrategyFile: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/strategy/files", { method: "POST", body: fd });
    if (!res.ok) throw new Error(`업로드 실패: ${res.status}`);
    return res.json() as Promise<{ parsed_preview: string }>;
  },
  getAnalysis: () =>
    req<{ by_type: { label: string; eval_amount: number; pct: number }[];
          by_sector: { label: string; eval_amount: number; pct: number }[]; as_of: string }>(
      "/api/portfolio/analysis"),
  getReturns: () =>
    req<{ returns: { period: string; portfolio_pct: number; benchmark_pct: number | null;
                     excess_pct: number | null }[]; as_of: string | null }>("/api/portfolio/returns"),
  getTrend: () =>
    req<{ date: string; total_asset: number }[]>("/api/portfolio/trend"),
  getHoldings: () => req<PortfolioData>("/api/portfolio/holdings"),
  setCash: (amount: number, account?: string) =>
    req<{ ok: boolean }>("/api/portfolio/cash", { method: "PUT", body: JSON.stringify({ amount, account }) }),
  scanBalanceFolder: (force = false) =>
    req<{ imported: number; folder: string;
          files: { file: string; status: string; reason?: string; holdings?: number }[] }>(
      `/api/portfolio/scan?force=${force}`, { method: "POST" }),
  getColumnMap: () => req<Record<string, string>>("/api/portfolio/column-map"),
  setColumnMap: (m: Record<string, string>) =>
    req<{ ok: boolean }>("/api/portfolio/column-map", { method: "PUT", body: JSON.stringify(m) }),
  getLlmUsage: () =>
    req<{ month_cost_usd: number; limit_usd: number; remaining_usd: number; calls: number }>(
      "/api/settings/llm-usage"),
  setLlmLimit: (limit_usd: number) =>
    req<{ ok: boolean }>("/api/settings/llm-limit", { method: "PUT", body: JSON.stringify({ limit_usd }) }),
  getJobHistory: () => req<JobLogItem[]>("/api/settings/jobs"),
  listSecrets: () => req<SecretItem[]>("/api/settings/secrets"),
  setSecret: (key: string, value: string) =>
    req<{ ok: boolean }>(`/api/settings/secrets/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
  deleteSecret: (key: string) =>
    req<{ ok: boolean }>(`/api/settings/secrets/${encodeURIComponent(key)}`, { method: "DELETE" }),
};
