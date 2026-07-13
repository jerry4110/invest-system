import { useEffect, useRef, useState } from "react";

interface Metrics {
  cumulative_return_pct: number | null; cagr_pct: number | null; mdd_pct: number | null;
  mar: number | null; sharpe: number | null; win_rate_pct?: number | null;
  payoff_ratio?: number | null; trades?: number;
}
interface RunResult {
  run_id: number; name: string; metrics: Metrics;
  curve: { date: string; value: number }[]; start: string; end: string; disclaimer: string;
}
interface RunItem { id: number; name: string; strategy: string; metrics: Metrics; created_at: string }

const fmt = (v: number | null | undefined, suffix = "") =>
  v == null ? "-" : `${v.toLocaleString("ko-KR", { maximumFractionDigits: 2 })}${suffix}`;

function Curve({ data }: { data: { value: number }[] }) {
  if (data.length < 2) return null;
  const w = 680, h = 180, pad = 4;
  const vals = data.map((d) => d.value);
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const pts = data.map((d, i) =>
    `${pad + (i / (data.length - 1)) * (w - pad * 2)},${h - pad - ((d.value - min) / span) * (h - pad * 2)}`).join(" ");
  return <svg width={w} height={h} style={{ maxWidth: "100%" }}>
    <polyline points={pts} fill="none" stroke="#2563eb" strokeWidth="2" /></svg>;
}

export default function Simulation() {
  const [result, setResult] = useState<RunResult | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const loadRuns = () => fetch("/api/backtest/runs").then((r) => r.json()).then(setRuns).catch(() => {});
  useEffect(() => { loadRuns(); }, []);

  const metricCards = (m: Metrics) => [
    ["누적수익률", fmt(m.cumulative_return_pct, "%")], ["CAGR", fmt(m.cagr_pct, "%")],
    ["MDD", fmt(m.mdd_pct, "%")], ["MAR", fmt(m.mar)], ["샤프", fmt(m.sharpe)],
    ...(m.trades ? [["승률", fmt(m.win_rate_pct, "%")], ["손익비", fmt(m.payoff_ratio)]] : []),
  ];

  return (
    <section>
      <h2>투자 시뮬레이션 <span style={{ fontSize: 13, color: "#888" }}>백테스트</span></h2>
      <div style={{ display: "flex", gap: 8, margin: "10px 0", alignItems: "center", flexWrap: "wrap" }}>
        <input value={name} onChange={(e) => setName(e.target.value)}
          placeholder="시나리오 이름 (예: 코스피 5년)" style={{ padding: 8, width: 200 }} />
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          const fd = new FormData();
          fd.append("file", f);
          fd.append("name", name || f.name);
          try {
            const res = await fetch("/api/backtest/upload", { method: "POST", body: fd });
            const body = await res.json();
            if (!res.ok) throw new Error(body.detail);
            setResult(body); setMsg(""); loadRuns();
          } catch (err) { setMsg(`❌ ${err instanceof Error ? err.message : "실패"}`); }
          if (fileRef.current) fileRef.current.value = "";
        }} />
        <span style={{ fontSize: 12, color: "#888" }}>지수/종목 가격 파일 업로드 (일자·종가 컬럼)</span>
      </div>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      {result && (
        <>
          <h3>{result.name} <span style={{ fontSize: 12, color: "#888" }}>{result.start} ~ {result.end}</span></h3>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
            {metricCards(result.metrics).map(([k, v]) => (
              <div key={k as string} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 16px" }}>
                <div style={{ fontSize: 12, color: "#666" }}>{k}</div>
                <div style={{ fontWeight: 700 }}>{v}</div>
              </div>
            ))}
          </div>
          <Curve data={result.curve} />
          <p style={{ fontSize: 12 }}>
            <a href={`/api/backtest/runs/${result.run_id}/chart.png`} target="_blank" rel="noreferrer">
              📊 정적 차트(PNG) 보기 — 자산곡선+드로다운</a>
          </p>
          <p style={{ fontSize: 12, color: "#d97706" }}>⚠️ {result.disclaimer}</p>
        </>
      )}

      {runs.length > 0 && (
        <>
          <h3>저장된 시나리오 비교</h3>
          <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
            <thead><tr style={{ background: "#f8fafc" }}>
              {["이름", "전략", "누적", "CAGR", "MDD", "MAR", "샤프", "실행일"].map((h) => (
                <th key={h} style={{ padding: "6px 12px", borderBottom: "1px solid #eee" }}>{h}</th>))}
            </tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td style={{ padding: "6px 12px" }}>{r.name}</td>
                  <td style={{ padding: "6px 12px" }}>{r.strategy}</td>
                  <td style={{ padding: "6px 12px" }}>{fmt(r.metrics.cumulative_return_pct, "%")}</td>
                  <td style={{ padding: "6px 12px" }}>{fmt(r.metrics.cagr_pct, "%")}</td>
                  <td style={{ padding: "6px 12px" }}>{fmt(r.metrics.mdd_pct, "%")}</td>
                  <td style={{ padding: "6px 12px" }}>{fmt(r.metrics.mar)}</td>
                  <td style={{ padding: "6px 12px" }}>{fmt(r.metrics.sharpe)}</td>
                  <td style={{ padding: "6px 12px", color: "#888" }}>{r.created_at.slice(0, 16).replace("T", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
