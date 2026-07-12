import { useCallback, useEffect, useState } from "react";
import { api, PortfolioData } from "../api/client";

const won = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const pnlColor = (v: number) => (v >= 0 ? "#dc2626" : "#2563eb");
const cell = { padding: "6px 10px", borderBottom: "1px solid #eee", textAlign: "right" as const };
const cellL = { ...cell, textAlign: "left" as const };

export default function Portfolio() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [cashInput, setCashInput] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    api.getHoldings().then(setData).catch(() => setMsg("❌ 백엔드 연결 실패"));
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
        <a href="/api/portfolio/export.csv" download>CSV 내려받기</a>
        {as_of && (
          <span style={{ fontSize: 12, color: stale ? "#d97706" : "#888" }}>
            잔고 기준: {as_of.replace("T", " ")}{stale && " ⚠️ 24시간 경과 — 잔고 갱신 필요"}
          </span>
        )}
      </div>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

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
    </section>
  );
}
