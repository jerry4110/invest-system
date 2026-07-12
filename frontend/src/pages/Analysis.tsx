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

interface Judgment {
  fair_value_current?: number | null; fair_value_future?: number | null;
  recommendation: string | null; plan?: string | null;
  assumptions?: string[] | null; rationale?: string | null;
  narrative?: string | null; price?: number | null; as_of: string; disclaimer: string;
}
interface Debate { bull: string; bear: string; conclusion: string; as_of: string }

interface NewsResult {
  ticker: string; as_of: string; disclaimer: string;
  disclosures: { title: string; link: string; date: string; filer?: string }[];
  news: { title: string; link: string; source: string; date: string;
          sentiment?: string | null; importance?: string | null; summary?: string | null }[];
  consensus: { target_price: number; analysts: number; recommendation: string } | null;
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
  const [tab, setTab] = useState<"fund" | "tech" | "news" | "ai">("fund");
  const [judgment, setJudgment] = useState<Judgment | null>(null);
  const [debate, setDebate] = useState<Debate | null>(null);
  const [deep, setDeep] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState("");
  const [tech, setTech] = useState<TechResult | null>(null);
  const [newsData, setNewsData] = useState<NewsResult | null>(null);
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
      // 기술적 분석·뉴스 (대상 종목만)
      try {
        const tr = await fetch(`/api/analysis/technical/${encodeURIComponent(ticker.trim())}`);
        setTech(tr.ok ? await tr.json() : null);
      } catch { setTech(null); }
      try {
        const nr = await fetch(`/api/analysis/news/${encodeURIComponent(ticker.trim())}`);
        setNewsData(nr.ok ? await nr.json() : null);
      } catch { setNewsData(null); }
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
          {[["fund", "기초(재무) 분석"], ["tech", "기술적 분석"], ["news", "뉴스·공시"], ["ai", "종합·AI 토론"]].map(([k, label]) => (
            <button key={k} onClick={() => setTab(k as "fund" | "tech")}
              style={{ padding: "6px 18px", borderRadius: 6, border: "1px solid #ddd",
                background: tab === k ? "#2563eb" : "#fff", color: tab === k ? "#fff" : "#333" }}>
              {label}
            </button>
          ))}
        </div>
      )}

      {tab === "ai" && (main || tech) && (() => {
        const t = ticker.trim();
        const call = async (path: string, after: (b: unknown) => void, label: string) => {
          setAiBusy(label);
          try {
            const res = await fetch(`/api/analysis/${path}/${encodeURIComponent(t)}`, { method: "POST" });
            const body = await res.json();
            if (!res.ok) throw new Error(body.detail);
            after(body);
          } catch (e) { setMsg(`❌ ${e instanceof Error ? e.message : "실패"}`); }
          finally { setAiBusy(""); }
        };
        return (
          <>
            <p style={{ fontSize: 13, color: "#888" }}>
              아래 기능은 OpenAI API를 호출합니다 (월 상한 내, 설정에서 사용량 확인).
            </p>
            <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
              <button disabled={!!aiBusy} onClick={() => call("comprehensive", (b) => setJudgment(b as Judgment), "종합 판단")}>
                {aiBusy === "종합 판단" ? "분석 중…" : "🎯 종합 판단"}</button>
              <button disabled={!!aiBusy} onClick={() => call("debate", (b) => setDebate(b as Debate), "AI 토론")}>
                {aiBusy === "AI 토론" ? "토론 중…" : "🗣️ AI 토론 (Bull vs Bear)"}</button>
              <button disabled={!!aiBusy} onClick={() => call("deepresearch", (b) => setDeep((b as { content: string }).content), "딥리서치")}>
                {aiBusy === "딥리서치" ? "리서치 중…" : "🔬 딥리서치"}</button>
              <button disabled={!!aiBusy} onClick={async () => {
                setAiBusy("리포트");
                try {
                  const res = await fetch(`/api/reports/stock/${encodeURIComponent(t)}`, { method: "POST" });
                  const body = await res.json();
                  if (!res.ok) throw new Error(body.detail);
                  setMsg(`📄 리포트 생성됨 — 리포트 보관함에서 다운로드하세요 (${body.relpath})`);
                } catch (e) { setMsg(`❌ ${e instanceof Error ? e.message : "리포트 실패"}`); }
                finally { setAiBusy(""); }
              }}>{aiBusy === "리포트" ? "생성 중…" : "📄 Word 리포트 생성"}</button>
            </div>
            {judgment && (
              <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: 14, marginBottom: 12 }}>
                {judgment.recommendation ? (
                  <>
                    <span style={{ padding: "4px 16px", borderRadius: 20, fontWeight: 700, color: "#fff",
                      background: judgment.recommendation === "매수" ? "#dc2626"
                        : judgment.recommendation === "매도" ? "#2563eb" : "#64748b" }}>
                      {judgment.recommendation}
                    </span>
                    <p style={{ fontSize: 14 }}>
                      적정가(현재) <b>{judgment.fair_value_current?.toLocaleString() ?? "-"}</b> ·
                      적정가(12개월) <b>{judgment.fair_value_future?.toLocaleString() ?? "-"}</b>
                      {judgment.price != null && <> · 현재가 {judgment.price.toLocaleString()}</>}
                    </p>
                    {judgment.plan && <p style={{ fontSize: 14 }}>📋 <b>투자 방안</b>: {judgment.plan}</p>}
                    {judgment.rationale && <p style={{ fontSize: 13, color: "#555" }}>{judgment.rationale}</p>}
                    {judgment.assumptions && judgment.assumptions.length > 0 && (
                      <p style={{ fontSize: 12, color: "#888" }}>가정: {judgment.assumptions.join(" / ")}</p>
                    )}
                  </>
                ) : <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{judgment.narrative}</pre>}
                <p style={{ fontSize: 12, color: "#888" }}>{judgment.disclaimer}</p>
              </div>
            )}
            {debate && (
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
                <div style={{ flex: 1, minWidth: 260, border: "2px solid #dc2626", borderRadius: 10, padding: 12 }}>
                  <b style={{ color: "#dc2626" }}>🐂 강세론</b>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{debate.bull}</pre>
                </div>
                <div style={{ flex: 1, minWidth: 260, border: "2px solid #2563eb", borderRadius: 10, padding: 12 }}>
                  <b style={{ color: "#2563eb" }}>🐻 약세론</b>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{debate.bear}</pre>
                </div>
                <div style={{ width: "100%", border: "1px solid #e5e7eb", borderRadius: 10, padding: 12 }}>
                  <b>⚖️ 중재 결론</b>
                  <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{debate.conclusion}</pre>
                </div>
              </div>
            )}
            {deep && (
              <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: 14 }}>
                <b>🔬 딥리서치</b>
                <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{deep}</pre>
              </div>
            )}
          </>
        );
      })()}

      {tab === "news" && newsData && (
        <>
          {newsData.consensus && (
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: 12, marginBottom: 12, fontSize: 14 }}>
              🎯 <b>애널리스트 컨센서스</b> — 평균 목표가{" "}
              <b>{newsData.consensus.target_price.toLocaleString()}</b>
              {" "}(의견 {newsData.consensus.analysts}건, {newsData.consensus.recommendation})
              <span style={{ color: "#888", fontSize: 12 }}> · 출처: Yahoo Finance 집계</span>
            </div>
          )}
          {newsData.disclosures.length > 0 && <>
            <h3>📢 최근 공시 (30일, 출처: DART)</h3>
            <ul style={{ fontSize: 14 }}>
              {newsData.disclosures.slice(0, 8).map((d) => (
                <li key={d.link}><a href={d.link} target="_blank" rel="noreferrer">{d.title}</a>
                  <span style={{ color: "#888", fontSize: 12 }}> {d.date}</span></li>
              ))}
            </ul>
          </>}
          <h3>📰 뉴스</h3>
          <ul style={{ fontSize: 14 }}>
            {newsData.news.map((n) => (
              <li key={n.link} style={{ marginBottom: 4 }}>
                {n.sentiment && (
                  <span style={{
                    fontSize: 12, padding: "1px 8px", borderRadius: 10, marginRight: 6, color: "#fff",
                    background: n.sentiment === "호재" ? "#dc2626" : n.sentiment === "악재" ? "#2563eb" : "#64748b",
                  }}>{n.sentiment}{n.importance === "상" && " ★"}</span>
                )}
                <a href={n.link} target="_blank" rel="noreferrer">{n.title}</a>
                <span style={{ color: "#888", fontSize: 12 }}> — {n.source} {n.date}</span>
                {n.summary && <span style={{ color: "#666", fontSize: 12 }}> · {n.summary}</span>}
              </li>
            ))}
          </ul>
          {newsData.notes.map((n, i) => <p key={i} style={{ fontSize: 12, color: "#d97706" }}>ℹ️ {n}</p>)}
          <p style={{ fontSize: 12, color: "#888" }}>{newsData.disclaimer}</p>
        </>
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
      {!main && !tech && !newsData && !busy && (
        <p style={{ color: "#666" }}>종목코드를 입력하고 분석을 실행하세요. 종합 판단·AI 토론·딥리서치는 다음 업데이트에서 추가됩니다.</p>
      )}
    </section>
  );
}
