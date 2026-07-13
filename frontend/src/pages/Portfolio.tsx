import { useCallback, useEffect, useState } from "react";
import { api, PortfolioData } from "../api/client";
import Donut from "../components/Donut";
import TrendChart from "../components/TrendChart";

const won = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const pnlColor = (v: number) => (v >= 0 ? "#dc2626" : "#2563eb");
const cell = { padding: "6px 10px", borderBottom: "1px solid #eee", textAlign: "right" as const };
const cellL = { ...cell, textAlign: "left" as const };

export default function Portfolio() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [cashInput, setCashInput] = useState("");
  const [msg, setMsg] = useState("");
  const [tab, setTab] = useState<"holdings" | "analysis">("holdings");
  const [analysis, setAnalysis] = useState<Awaited<ReturnType<typeof api.getAnalysis>> | null>(null);
  const [returnsData, setReturnsData] = useState<Awaited<ReturnType<typeof api.getReturns>> | null>(null);
  const [trend, setTrend] = useState<{ date: string; total_asset: number }[]>([]);

  const load = useCallback(() => {
    api.getHoldings().then(setData).catch(() => setMsg("❌ 백엔드 연결 실패"));
    api.getAnalysis().then(setAnalysis).catch(() => {});
    api.getReturns().then(setReturnsData).catch(() => {});
    api.getTrend().then(setTrend).catch(() => {});
  }, []);
  useEffect(load, [load]);

  if (!data) return <section><h2>포트폴리오</h2><p>{msg || "불러오는 중…"}</p></section>;

  const { holdings, totals, as_of } = data;
  const stale = as_of && Date.now() - new Date(as_of).getTime() > 24 * 3600 * 1000;

  const scan = async (force = false) => {
    const r = await api.scanBalanceFolder(force);
    if (r.imported) {
      setMsg(`✅ 잔고 파일 ${r.imported}건 반영 (${r.folder})`);
    } else if (r.files.length === 0) {
      setMsg(`감시 폴더(${r.folder})에 잔고 파일이 없습니다 — 파일명에 '잔고' 또는 '미래에셋' 포함 필요`);
    } else {
      const failed = r.files.filter((f) => f.status === "failed");
      setMsg(failed.length
        ? `❌ ${failed[0].file}: ${failed[0].reason}`
        : "모든 파일이 이미 처리됨 — 변경사항이 없으면 '강제 재스캔'을 사용하세요");
    }
    load();
  };

  const saveCash = async () => {
    await api.setCash(Number(cashInput.replace(/,/g, "")) || 0);
    setCashInput("");
    load();
  };

  return (
    <section>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
        <h2 style={{ margin: 0 }}>포트폴리오</h2>
        <button onClick={() => scan(false)}>잔고 파일 스캔</button>
        <button onClick={() => scan(true)} style={{ fontSize: 12 }}>강제 재스캔</button>
        <button style={{ fontSize: 12, color: "#dc2626" }} onClick={async () => {
          if (!confirm("보유종목·예수금·계좌를 모두 삭제합니다. 이후 폴더 스캔으로 다시 불러옵니다. 계속할까요?")) return;
          await fetch("/api/portfolio/reset", { method: "POST" });
          const r = await api.scanBalanceFolder(true);
          setMsg(r.imported ? `🔄 초기화 후 ${r.imported}개 파일 재적재 완료 (폴더: ${r.folder})` : `🔄 초기화됨 — 감시 폴더(${r.folder})에 파일이 없습니다. 설정에서 폴더를 확인하세요`);
          load();
        }}>전체 초기화+재적재</button>
        <a href="/api/portfolio/export.csv" download>CSV 내려받기</a>
        {as_of && (
          <span style={{ fontSize: 12, color: stale ? "#d97706" : "#888" }}>
            잔고 기준: {as_of.replace("T", " ")}{stale && " ⚠️ 24시간 경과 — 잔고 갱신 필요"}
          </span>
        )}
      </div>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      <div style={{ display: "flex", gap: 4, margin: "10px 0" }}>
        {[["holdings", "보유현황"], ["analysis", "분석"]].map(([k, label]) => (
          <button key={k} onClick={() => setTab(k as "holdings" | "analysis")}
            style={{ padding: "6px 18px", borderRadius: 6, border: "1px solid #ddd",
              background: tab === k ? "#2563eb" : "#fff", color: tab === k ? "#fff" : "#333" }}>
            {label}
          </button>
        ))}
      </div>

      {tab === "analysis" && (
        <div>
          <div style={{ display: "flex", gap: 32, flexWrap: "wrap", marginBottom: 16 }}>
            {analysis && analysis.by_type.length > 0 && (
              <div><h3>투자유형별</h3><Donut parts={analysis.by_type} /></div>
            )}
            {analysis && analysis.by_sector.length > 0 && (
              <div><h3>산업별</h3><Donut parts={analysis.by_sector.slice(0, 6)} /></div>
            )}
          </div>
          <h3>기간별 수익률 (vs 코스피)</h3>
          {returnsData && returnsData.returns.length > 0 ? (
            <table style={{ borderCollapse: "collapse", fontSize: 14, marginBottom: 16 }}>
              <thead><tr style={{ background: "#f8fafc" }}>
                {["기간", "내 수익률", "코스피", "초과수익"].map((hh) => (
                  <th key={hh} style={{ padding: "6px 16px", borderBottom: "1px solid #eee" }}>{hh}</th>))}
              </tr></thead>
              <tbody>
                {returnsData.returns.map((r) => (
                  <tr key={r.period}>
                    <td style={{ padding: "6px 16px" }}>{{ "1w": "1주", "1m": "1개월", "3m": "3개월", "1y": "1년" }[r.period]}</td>
                    <td style={{ padding: "6px 16px", color: r.portfolio_pct >= 0 ? "#dc2626" : "#2563eb" }}>
                      {r.portfolio_pct >= 0 ? "+" : ""}{r.portfolio_pct}%</td>
                    <td style={{ padding: "6px 16px" }}>{r.benchmark_pct != null ? `${r.benchmark_pct >= 0 ? "+" : ""}${r.benchmark_pct}%` : "-"}</td>
                    <td style={{ padding: "6px 16px", fontWeight: 600,
                      color: (r.excess_pct ?? 0) >= 0 ? "#dc2626" : "#2563eb" }}>
                      {r.excess_pct != null ? `${r.excess_pct >= 0 ? "+" : ""}${r.excess_pct}%p` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: "#888", fontSize: 13 }}>스냅샷이 쌓이면 기간 수익률이 표시됩니다.</p>}
          <h3>자산 추이</h3>
          <TrendChart data={trend} />
        </div>
      )}

      {tab === "holdings" && <div>

      <div style={{ display: "flex", gap: 16, margin: "12px 0", flexWrap: "wrap" }}>
        {[["총자산", totals.total_asset], ["평가금액", totals.eval_amount],
          ["매입금액", totals.buy_amount], ["예수금", totals.cash]].map(([k, v]) => (
          <div key={k as string} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 16px" }}>
            <div style={{ fontSize: 12, color: "#666" }}>{k}</div>
            <div style={{ fontWeight: 700 }}>{won(v as number)}원</div>
          </div>
        ))}
        <div style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 16px" }}>
          <div style={{ fontSize: 12, color: "#666" }}>평가손익</div>
          <div style={{ fontWeight: 700, color: pnlColor(totals.pnl_amount) }}>
            {won(totals.pnl_amount)}원 ({totals.pnl_pct >= 0 ? "+" : ""}{totals.pnl_pct}%)
          </div>
        </div>
      </div>

      {holdings.length === 0 ? (
        <p style={{ color: "#666" }}>
          보유 종목이 없습니다 — HTS에서 잔고를 내보내 감시 폴더에 저장하거나, "잔고 파일 스캔"을 눌러주세요.
        </p>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {["계좌", "종목명", "수량", "평균단가", "매입금액", "현재가", "평가금액", "평가손익", "수익률", "비중"]
                .map((h) => <th key={h} style={{ ...cell, fontWeight: 600 }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={`${h.account}-${h.ticker}`}>
                <td style={cellL}>{h.account}</td>
                <td style={cellL}>{h.name} <span style={{ color: "#999", fontSize: 12 }}>{h.ticker}</span></td>
                <td style={cell}>{h.qty.toLocaleString()}</td>
                <td style={cell}>{won(h.avg_price)}</td>
                <td style={cell}>{won(h.buy_amount)}</td>
                <td style={cell}>{won(h.cur_price)}</td>
                <td style={cell}>{won(h.eval_amount)}</td>
                <td style={{ ...cell, color: pnlColor(h.pnl_amount) }}>{won(h.pnl_amount)}</td>
                <td style={{ ...cell, color: pnlColor(h.pnl_amount) }}>
                  {h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(2)}%
                </td>
                <td style={cell}>{h.weight_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: 16, display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: 13 }}>예수금 입력:</span>
        <input value={cashInput} onChange={(e) => setCashInput(e.target.value)}
          placeholder="예: 3000000" style={{ padding: 6, width: 140 }} />
        <button onClick={saveCash}>저장</button>
      </div>
      </div>}
    </section>
  );
}
