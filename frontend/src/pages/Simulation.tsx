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
  const [dc, setDc] = useState({ entry_n: 20, exit_n: 10, stop_pct: 8 });
  const [dcBusy, setDcBusy] = useState(false);
  const [todaySignal, setTodaySignal] = useState<string>("");
  const [insts, setInsts] = useState<{ id: number; name: string; cik: string }[]>([]);
  const [f13, setF13] = useState<{ period: string; source: string;
    top_holdings: { issuer: string; weight_pct: number; value: number }[];
    changes: { issuer: string; change: string }[] } | null>(null);
  const [f13Busy, setF13Busy] = useState(false);
  const [newInst, setNewInst] = useState({ name: "", cik: "" });
  const fileRef = useRef<HTMLInputElement>(null);

  const loadRuns = () => fetch("/api/backtest/runs").then((r) => r.json()).then(setRuns).catch(() => {});
  useEffect(() => { loadRuns(); fetch("/api/13f/institutions").then((r) => r.json()).then(setInsts).catch(() => {}); }, []);

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

      <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: 14, margin: "16px 0" }}>
        <h3 style={{ marginTop: 0 }}>📈 Donchian Channel 전략 (코스피)</h3>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", fontSize: 13 }}>
          <label>진입 채널 <input type="number" value={dc.entry_n} style={{ width: 60, padding: 4 }}
            onChange={(e) => setDc({ ...dc, entry_n: Number(e.target.value) })} />일</label>
          <label>청산 채널 <input type="number" value={dc.exit_n} style={{ width: 60, padding: 4 }}
            onChange={(e) => setDc({ ...dc, exit_n: Number(e.target.value) })} />일</label>
          <label>스탑로스 -<input type="number" value={dc.stop_pct} style={{ width: 50, padding: 4 }}
            onChange={(e) => setDc({ ...dc, stop_pct: Number(e.target.value) })} />%</label>
          <button disabled={dcBusy} onClick={async () => {
            setDcBusy(true);
            try {
              const res = await fetch("/api/donchian/backtest", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ticker: "KOSPI", ...dc }) });
              const body = await res.json();
              if (!res.ok) throw new Error(body.detail);
              setResult({ ...body, name: `Donchian 코스피`, start: body.curve[0]?.date ?? "",
                          end: body.curve[body.curve.length - 1]?.date ?? "" });
              loadRuns();
            } catch (e) { setMsg(`❌ ${e instanceof Error ? e.message : "실패"}`); }
            finally { setDcBusy(false); }
          }}>{dcBusy ? "실행 중…" : "코스피 2년 백테스트"}</button>
          <button onClick={async () => {
            const res = await fetch("/api/donchian/check-now", { method: "POST" });
            const b = await res.json();
            setTodaySignal(res.ok ? `${b.signal ?? "시그널 없음"} — ${b.reason}` : `❌ ${b.detail}`);
          }}>오늘 시그널 확인</button>
          {todaySignal && <span>{todaySignal}</span>}
        </div>
        <p style={{ fontSize: 12, color: "#888", marginBottom: 0 }}>
          매일 아침 배치가 자동 감시하며, 시그널 발생 시 알림센터·Windows 토스트로 통지합니다.
        </p>
      </div>

      <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: 14, margin: "16px 0" }}>
        <h3 style={{ marginTop: 0 }}>🏛️ 13F 기관 포트폴리오 (출처: SEC EDGAR)</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: 13 }}>
          {insts.map((i) => (
            <button key={i.id} disabled={f13Busy} onClick={async () => {
              setF13Busy(true);
              try {
                const res = await fetch(`/api/13f/${i.cik}`);
                const b = await res.json();
                if (!res.ok) throw new Error(b.detail);
                setF13(b);
              } catch (e) { setMsg(`❌ ${e instanceof Error ? e.message : "실패"}`); }
              finally { setF13Busy(false); }
            }}>{f13Busy ? "조회 중…" : i.name}</button>
          ))}
          <input placeholder="기관명" value={newInst.name} style={{ padding: 6, width: 120 }}
            onChange={(e) => setNewInst({ ...newInst, name: e.target.value })} />
          <input placeholder="CIK (숫자)" value={newInst.cik} style={{ padding: 6, width: 100 }}
            onChange={(e) => setNewInst({ ...newInst, cik: e.target.value })} />
          <button onClick={async () => {
            const r = await fetch("/api/13f/institutions", { method: "POST",
              headers: { "Content-Type": "application/json" }, body: JSON.stringify(newInst) });
            if (r.ok) { setNewInst({ name: "", cik: "" });
              fetch("/api/13f/institutions").then((x) => x.json()).then(setInsts); }
            else setMsg("❌ CIK는 숫자여야 합니다");
          }}>기관 추가</button>
        </div>
        {f13 && (
          <div style={{ marginTop: 10 }}>
            <b>상위 10 보유 ({f13.period} 기준)</b>
            <table style={{ borderCollapse: "collapse", fontSize: 13, marginTop: 4 }}>
              <tbody>
                {f13.top_holdings.map((h, i) => (
                  <tr key={h.issuer}>
                    <td style={{ padding: "3px 10px", color: "#888" }}>{i + 1}</td>
                    <td style={{ padding: "3px 10px" }}>{h.issuer}</td>
                    <td style={{ padding: "3px 10px", fontWeight: 600 }}>{h.weight_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {f13.changes.filter((c) => c.change !== "유지").length > 0 && (
              <p style={{ fontSize: 13 }}>
                <b>분기 변동:</b>{" "}
                {f13.changes.filter((c) => c.change !== "유지").slice(0, 10)
                  .map((c) => `${c.issuer}(${c.change})`).join(", ")}
              </p>
            )}
            <p style={{ fontSize: 12, color: "#888" }}>{f13.source}</p>
          </div>
        )}
      </div>

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
