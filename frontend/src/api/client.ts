// API 클라이언트 — 모든 백엔드 호출은 이 모듈을 경유 (로직은 backend/services에)
export interface HealthResponse {
  status: string;
  version: string;
  as_of: string; // 기준시각 (NFR-04)
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`API ${path} 실패: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<HealthResponse>("/api/health"),
};
