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
  getIndicators: () => req<Indicator[]>("/api/dashboard/indicators"),
  refreshIndicators: () => req<RefreshResult>("/api/dashboard/refresh", { method: "POST" }),
  getSettings: () => req<Settings>("/api/settings"),
  updateSettings: (s: Partial<Settings>) =>
    req<Settings>("/api/settings", { method: "PUT", body: JSON.stringify(s) }),
  scanBalanceFolder: () => req<{ imported: number; folder: string }>("/api/portfolio/scan", { method: "POST" }),
  getColumnMap: () => req<Record<string, string>>("/api/portfolio/column-map"),
  setColumnMap: (m: Record<string, string>) =>
    req<{ ok: boolean }>("/api/portfolio/column-map", { method: "PUT", body: JSON.stringify(m) }),
  listSecrets: () => req<SecretItem[]>("/api/settings/secrets"),
  setSecret: (key: string, value: string) =>
    req<{ ok: boolean }>(`/api/settings/secrets/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),
  deleteSecret: (key: string) =>
    req<{ ok: boolean }>(`/api/settings/secrets/${encodeURIComponent(key)}`, { method: "DELETE" }),
};
