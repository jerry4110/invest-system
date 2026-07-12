import { useState } from "react";
import CandleChart from "../components/CandleChart";

interface EvalItem {
  metric: string; label: string; value: number | null;
  threshold: number; direction: string; status: string;
}
interface TechResult {
  ticker: string; base_date: string; as_of: string; disclaimer: string;
  ma: Record<string, number | null>; ma_alignment: string | null;
  rsi: number | null; macd: { macd: number; signal: number; histogram: number } | null;
  cross: string | null; volume_surge_ratio: number | null;
  signal: { verdict: string; score: number; reasons: string[] };
  ohlcv: { date: string; open: number; high: number; low: number; close: number; volume: number }[];
  investor_flows: { date: string; individual: number; institution: number; foreign: number }[] | null;
  short_interest: { date: string; balance: number; ratio_pct: number }[] | null;
  notes: string[];
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
  const [tab, setTab] = useState<"fund" | "tech">("fund");
  const [tech, setTech] = useState<TechResult | null>(null);
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
      // 기술적 분석 (대상 종목만)
      try {
        const tr = await fetch(`/api/analysis/technical/${encodeURIComponent(ticker.trim())}`);
        setTech(tr.ok ? await tr.json() : null);
      } catch { setTech(null); }
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

      {(main || tech) && (
        <div style={{ display: "flex", gap: 4, margin: "8px 0" }}>
          {[["fund", "기초(재무) 분석"], ["tech", "기술적 분석"]].map(([k, label]) => (
            <button key={k} onClick={() => setTab(k as "fund" | "tech")}
              style={{ padding: "6px 18px", borderRadius: 6, border: "1px solid #ddd",
                background: tab === k ? "#2563eb" : "#fff", color: tab === k ? "#fff" : "#333" }}>
              {label}
            </button>
          ))}
        </div>
      )}

      {tab === "tech" && tech && (
        <>
          <div style={{ display: "flex", gap: 10, alignItems: "center", margin: "8px 0", flexWrap: "wrap" }}>
            <span style={{ padding: "4px 14px", borderRadius: 20, fontWeight: 700, color: "#fff",
              background: tech.signal.verdict === "매수" ? "#dc2626"
                : tech.signal.verdict === "매도" ? "#2563eb" : "#64748b" }}>
              시그널: {tech.signal.verdict}
            </span>
            <span style={{ fontSize: 13 }}>
              {tech.ma_alignment ?? "-"} · RSI {tech.rsi ?? "-"}
              {tech.cross && ` · ${tech.cross}`}
              {tech.volume_surge_ratio != null && tech.volume_surge_ratio >= 1.5 && ` · 거래량 ${tech.volume_surge_ratio}배`}
            </span>
            <span style={{ fontSize: 12, color: "#888" }}>기준일 {tech.base_date}</span>
          </div>
          <CandleChart data={tech.ohlcv} />
          <ul style={{ fontSize: 13, marginTop: 10 }}>
            {tech.signal.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
          {tech.investor_flows && tech.investor_flows.length > 0 && (() => {
            const sum = (k: "individual" | "institution" | "foreign") =>
              tech.investor_flows!.slice(-20).reduce((a, b) => a + b[k], 0);
            const fmt억 = (v: number) => (v / 1e8).toFixed(0) + "억";
            return (
              <p style={{ fontSize: 13 }}>
                <b>최근 20일 누적 순매수</b> — 개인 {fmt억(sum("individual"))} ·
                기관 {fmt억(sum("institution"))} · 외국인 {fmt억(sum("foreign"))}
              </p>
            );
          })()}
          {tech.short_interest && tech.short_interest.length > 0 && (
            <p style={{ fontSize: 13 }}>
              <b>공매도 비중</b> — 최근 {tech.short_interest[tech.short_interest.length - 1].ratio_pct}%
            </p>
          )}
          {tech.notes.map((n, i) => <p key={i} style={{ fontSize: 12, color: "#d97706" }}>ℹ️ {n}</p>)}
          <p style={{ fontSize: 12, color: "#888" }}>{tech.disclaimer}</p>
        </>
      )}

      {tab === "fund" && main && (
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
      {!main && !tech && !busy && (
        <p style={{ color: "#666" }}>종목코드를 입력하고 분석을 실행하세요. 뉴스(C)·AI 토론·딥리서치는 다음 업데이트에서 추가됩니다.</p>
      )}
    </section>
  );
}
