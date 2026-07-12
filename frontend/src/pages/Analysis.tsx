import { useState } from "react";

interface EvalItem {
  metric: string; label: string; value: number | null;
  threshold: number; direction: string; status: string;
}
interface FundResult {
  ticker: string; source: string; base_date: string;
  financials: { year: number; revenue?: number; operating_profit?: number; net_income?: number }[];
  evaluation: { items: EvalItem[]; tier1: { verdict: string; passed: string[]; failed: string[]; unknown: string[] } };
  as_of: string; disclaimer: string;
}

const cell = { padding: "6px 12px", borderBottom: "1px solid #eee", textAlign: "right" as const };
const cellL = { ...cell, textAlign: "left" as const };
const fmt조 = (v?: number) => (v == null ? "-" : (v / 1e12).toFixed(1) + "조");
const statusIcon: Record<string, string> = { "충족": "●", "부분충족": "◐", "미충족": "○", "데이터 없음": "—" };
const statusColor: Record<string, string> = { "충족": "#16a34a", "부분충족": "#f59e0b", "미충족": "#dc2626", "데이터 없음": "#999" };

export default function Analysis() {
  const [ticker, setTicker] = useState("");
  const [peers, setPeers] = useState("");
  const [results, setResults] = useState<FundResult[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const run = async () => {
    if (!ticker.trim()) return;
    setBusy(true); setMsg(""); setResults([]);
    try {
      const peerList = peers.split(",").map((p) => p.trim()).filter(Boolean);
      if (peerList.length > 0) {
        const all = [ticker.trim(), ...peerList].join(",");
        const res = await fetch(`/api/analysis/compare?tickers=${encodeURIComponent(all)}`);
        if (!res.ok) throw new Error((await res.json()).detail);
        const body = await res.json();
        setResults(body.results);
        if (body.errors.length) setMsg(`⚠️ 일부 실패: ${body.errors.map((e: { ticker: string }) => e.ticker).join(", ")}`);
      } else {
        const res = await fetch(`/api/analysis/fundamental/${encodeURIComponent(ticker.trim())}`);
        if (!res.ok) throw new Error((await res.json()).detail);
        setResults([await res.json()]);
      }
    } catch (e) { setMsg(`❌ ${e instanceof Error ? e.message : "분석 실패"}`); }
    finally { setBusy(false); }
  };

  const main = results[0];
  return (
    <section>
      <h2>종목분석 <span style={{ fontSize: 13, color: "#888" }}>분석 A — 기초(재무)</span></h2>
      <div style={{ display: "flex", gap: 8, margin: "10px 0", flexWrap: "wrap" }}>
        <input value={ticker} onChange={(e) => setTicker(e.target.value)}
          placeholder="종목코드 (예: 005930, NVDA)" style={{ padding: 8, width: 180 }}
          onKeyDown={(e) => e.key === "Enter" && run()} />
        <input value={peers} onChange={(e) => setPeers(e.target.value)}
          placeholder="비교기업 (쉼표, 최대 5개 — 선택)" style={{ padding: 8, width: 240 }} />
        <button onClick={run} disabled={busy}
          style={{ padding: "8px 20px", background: "#2563eb", color: "#fff", border: 0, borderRadius: 6 }}>
          {busy ? "분석 중…" : "분석 실행"}
        </button>
      </div>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      {main && (
        <>
          <div style={{ display: "flex", gap: 10, alignItems: "center", margin: "8px 0" }}>
            <span style={{
              padding: "4px 14px", borderRadius: 20, fontWeight: 700, color: "#fff",
              background: main.evaluation.tier1.verdict === "충족" ? "#16a34a" : "#64748b",
            }}>
              Tier 1 {main.evaluation.tier1.verdict}
            </span>
            {main.evaluation.tier1.unknown.length > 0 && (
              <span style={{ fontSize: 12, color: "#888" }}>
                판정 불가 항목 {main.evaluation.tier1.unknown.length}개 (데이터 없음)
              </span>
            )}
            <span style={{ fontSize: 12, color: "#888" }}>기준일 {main.base_date} (T-1)</span>
          </div>

          <h3>최근 3년 실적 {results.length > 1 && "(대상 기업)"}</h3>
          <table style={{ borderCollapse: "collapse", fontSize: 14, marginBottom: 16 }}>
            <thead><tr style={{ background: "#f8fafc" }}>
              {["연도", "매출액", "영업이익", "순이익"].map((h) => <th key={h} style={cell}>{h}</th>)}
            </tr></thead>
            <tbody>
              {main.financials.map((f) => (
                <tr key={f.year}>
                  <td style={cell}>{f.year}</td>
                  <td style={cell}>{fmt조(f.revenue)}</td>
                  <td style={cell}>{fmt조(f.operating_profit)}</td>
                  <td style={cell}>{fmt조(f.net_income)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>지표 평가 {results.length > 1 && "— 기업 비교"}</h3>
          <table style={{ borderCollapse: "collapse", fontSize: 14, marginBottom: 12 }}>
            <thead><tr style={{ background: "#f8fafc" }}>
              <th style={cellL}>지표</th><th style={cell}>기준</th>
              {results.map((r) => <th key={r.ticker} style={cell}>{r.ticker}</th>)}
            </tr></thead>
            <tbody>
              {main.evaluation.items.map((item, idx) => (
                <tr key={item.metric}>
                  <td style={cellL}>{item.label}</td>
                  <td style={cell}>{item.direction === "min" ? "≥" : "≤"} {item.threshold}</td>
                  {results.map((r) => {
                    const it = r.evaluation.items[idx];
                    return (
                      <td key={r.ticker} style={{ ...cell, color: statusColor[it.status] }}>
                        {statusIcon[it.status]} {it.value != null ? it.value.toLocaleString() : "-"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: 12, color: "#888" }}>
            ● 충족 ◐ 부분충족 ○ 미충족 — 없음 · {main.disclaimer}
          </p>
        </>
      )}
      {!main && !busy && (
        <p style={{ color: "#666" }}>종목코드를 입력하고 분석을 실행하세요. 기술적 분석(B)·뉴스(C)·AI 토론은 다음 업데이트에서 탭으로 추가됩니다.</p>
      )}
    </section>
  );
}
