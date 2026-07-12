import { useCallback, useEffect, useState } from "react";
import { api, Indicator } from "../api/client";
import IndicatorCard from "../components/IndicatorCard";

export default function Dashboard() {
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [asOf, setAsOf] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string>("");

  const load = useCallback(async () => {
    try {
      const list = await api.getIndicators();
      setIndicators(list);
      if (list.length) setAsOf(list[0].as_of);
    } catch {
      setNotice("❌ 백엔드 연결 실패 — FastAPI 서버(8000) 실행 여부를 확인하세요");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const refresh = async () => {
    setBusy(true);
    setNotice("");
    try {
      const r = await api.refreshIndicators();
      if (r.failed.length) setNotice(`⚠️ 일부 지표 갱신 실패: ${r.failed.join(", ")} (이전 데이터 표시)`);
      await load();
    } catch {
      setNotice("❌ 갱신 실패");
    } finally {
      setBusy(false);
    }
  };

  const indices = indicators.filter((i) => i.category === "index");
  const macros = indicators.filter((i) => i.category === "macro");

  return (
    <section>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>대시보드</h2>
        <button onClick={refresh} disabled={busy}
          style={{ padding: "6px 16px", background: "#2563eb", color: "#fff", border: 0, borderRadius: 6 }}>
          {busy ? "갱신 중…" : "업데이트"}
        </button>
        {asOf && <span style={{ fontSize: 12, color: "#888" }}>마지막 갱신: {asOf}</span>}
      </div>
      {notice && <p style={{ fontSize: 13 }}>{notice}</p>}
      {indicators.length === 0 && !notice && (
        <p style={{ color: "#666" }}>데이터가 없습니다 — "업데이트"를 눌러 첫 수집을 실행하세요.</p>
      )}
      {indices.length > 0 && <>
        <h3 style={{ marginBottom: 8 }}>📊 주요 지수</h3>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          {indices.map((i) => <IndicatorCard key={i.code} ind={i} />)}
        </div>
      </>}
      {macros.length > 0 && <>
        <h3 style={{ marginBottom: 8 }}>🌍 거시 지표</h3>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          {macros.map((i) => <IndicatorCard key={i.code} ind={i} />)}
        </div>
      </>}
      <p style={{ color: "#888", fontSize: 13 }}>자산 요약 카드는 T-08에서 추가됩니다.</p>
    </section>
  );
}
