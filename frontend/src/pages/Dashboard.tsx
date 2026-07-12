import { useEffect, useState } from "react";
import { api, HealthResponse } from "../api/client";

export default function Dashboard() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(String(e)));
  }, []);

  return (
    <section>
      <h2>대시보드</h2>
      {health && (
        <p style={{ color: "green" }}>
          ✅ 백엔드 연결됨 (v{health.version}, 기준시각 {health.as_of})
        </p>
      )}
      {error && <p style={{ color: "red" }}>❌ 백엔드 연결 실패 — FastAPI 서버(8000) 실행 여부를 확인하세요</p>}
      <p style={{ color: "#666" }}>T-04에서 시장 지표 카드 10종이 여기에 표시됩니다.</p>
    </section>
  );
}
