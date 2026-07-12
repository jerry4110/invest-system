import { useCallback, useEffect, useState } from "react";
import { api, AssetSummary, Indicator } from "../api/client";
import Donut from "../components/Donut";
import IndicatorCard from "../components/IndicatorCard";

const won = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });

export default function Dashboard() {
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [summary, setSummary] = useState<AssetSummary | null>(null);
  const [asOf, setAsOf] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string>("");

  const load = useCallback(async () => {
    try {
      const list = await api.getIndicators();
      setIndicators(list);
      if (list.length) setAsOf(list[0].as_of);
      setSummary(await api.getSummary());
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
      {summary && summary.total_asset > 0 && (
        <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: 14, marginBottom: 16 }}>
          <h3 style={{ margin: "0 0 10px" }}>💰 내 자산 요약
            <span style={{ fontSize: 12, color: "#888", fontWeight: 400, marginLeft: 8 }}>
              잔고 기준: {summary.as_of.replace("T", " ")}
            </span>
          </h3>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 13, color: "#666" }}>총자산</div>
              <div style={{ fontSize: 26, fontWeight: 700 }}>{won(summary.total_asset)}원</div>
              {summary.day_change && (
                <div style={{ fontSize: 13, color: summary.day_change.amount >= 0 ? "#dc2626" : "#2563eb" }}>
                  전일 대비 {summary.day_change.amount >= 0 ? "▲" : "▼"} {won(Math.abs(summary.day_change.amount))}원
                  ({summary.day_change.pct >= 0 ? "+" : ""}{summary.day_change.pct}%)
                </div>
              )}
            </div>
            {[["평가금액", won(summary.total_eval) + "원", undefined],
              ["매입금액", won(summary.total_buy) + "원", undefined],
              ["예수금", won(summary.total_cash) + "원", undefined],
              ["평가손익", `${won(summary.total_pnl)}원 (${summary.total_pnl_pct >= 0 ? "+" : ""}${summary.total_pnl_pct}%)`,
               summary.total_pnl >= 0 ? "#dc2626" : "#2563eb"]].map(([k, v, color]) => (
              <div key={k as string}>
                <div style={{ fontSize: 13, color: "#666" }}>{k}</div>
                <div style={{ fontWeight: 600, color: (color as string) || "inherit" }}>{v}</div>
              </div>
            ))}
            <Donut parts={summary.composition} />
          </div>
        </div>
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
