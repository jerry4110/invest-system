import { useEffect, useState } from "react";

interface Deviation { key: string; label: string; current_pct: number; target_pct: number; deviation_pp: number }
interface Action { ticker: string; name: string; action: string; qty: number; est_amount: number; rationale: string }
interface Proposal {
  deviations: Deviation[]; actions: Action[]; summary: string | null;
  warnings: string[]; narrative: string | null;
  before_after: { key: string; label: string; before_pct: number; after_pct: number }[];
  disclaimer: string;
}

const won = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const cell = { padding: "6px 12px", borderBottom: "1px solid #eee" } as const;

export default function Rebalance() {
  const [devs, setDevs] = useState<Deviation[]>([]);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch("/api/rebalance/deviation").then((r) => r.json())
      .then((b) => setDevs(b.deviations)).catch(() => setMsg("❌ 백엔드 연결 실패"));
  }, []);

  const propose = async () => {
    setBusy(true); setMsg("");
    try {
      const res = await fetch("/api/rebalance/propose", { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail);
      setProposal(body);
    } catch (e) { setMsg(`❌ ${e instanceof Error ? e.message : "실패"}`); }
    finally { setBusy(false); }
  };

  return (
    <section>
      <h2>자산 리밸런싱</h2>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      {devs.length === 0 ? (
        <p style={{ color: "#666" }}>목표 배분이 없습니다 — 투자전략 페이지에서 목표 자산배분을 먼저 설정하세요.</p>
      ) : (
        <>
          <h3>목표 대비 이탈</h3>
          <table style={{ borderCollapse: "collapse", fontSize: 14, marginBottom: 12 }}>
            <thead><tr style={{ background: "#f8fafc" }}>
              {["항목", "현재", "목표", "이탈"].map((h) => <th key={h} style={cell}>{h}</th>)}
            </tr></thead>
            <tbody>
              {devs.map((d) => (
                <tr key={d.key}>
                  <td style={cell}>{d.label}</td>
                  <td style={cell}>{d.current_pct}%</td>
                  <td style={cell}>{d.target_pct}%</td>
                  <td style={{ ...cell, fontWeight: 700,
                    color: Math.abs(d.deviation_pp) >= 5 ? "#dc2626" : "#16a34a" }}>
                    {d.deviation_pp > 0 ? "+" : ""}{d.deviation_pp}%p
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button onClick={propose} disabled={busy}
            style={{ padding: "8px 20px", background: "#2563eb", color: "#fff", border: 0, borderRadius: 6 }}>
            {busy ? "제안 생성 중… (AI)" : "⚖️ 리밸런싱 제안 받기 (AI)"}
          </button>
        </>
      )}

      {proposal && (
        <div style={{ marginTop: 16 }}>
          {proposal.summary && <p><b>{proposal.summary}</b></p>}
          {proposal.warnings.map((w, i) => (
            <p key={i} style={{ fontSize: 13, color: "#d97706" }}>⚠️ 검증 경고: {w}</p>
          ))}
          {proposal.actions.length > 0 && (
            <table style={{ borderCollapse: "collapse", fontSize: 14, marginBottom: 12 }}>
              <thead><tr style={{ background: "#f8fafc" }}>
                {["종목", "액션", "수량", "예상금액", "근거"].map((h) => <th key={h} style={cell}>{h}</th>)}
              </tr></thead>
              <tbody>
                {proposal.actions.map((a, i) => (
                  <tr key={i}>
                    <td style={cell}>{a.name} <span style={{ color: "#999", fontSize: 12 }}>{a.ticker}</span></td>
                    <td style={{ ...cell, fontWeight: 700,
                      color: ["매수", "신규편입"].includes(a.action) ? "#dc2626" : "#2563eb" }}>{a.action}</td>
                    <td style={cell}>{a.qty?.toLocaleString()}</td>
                    <td style={cell}>{won(a.est_amount)}원</td>
                    <td style={{ ...cell, fontSize: 13 }}>{a.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {proposal.narrative && <pre style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{proposal.narrative}</pre>}
          <h3>실행 전/후 비중</h3>
          {proposal.before_after.map((r) => (
            <p key={r.key} style={{ fontSize: 14 }}>
              {r.label}: {r.before_pct}% → <b>{r.after_pct}%</b>
            </p>
          ))}
          <button onClick={async () => {
            const res = await fetch("/api/reports/rebalance", { method: "POST" });
            const b = await res.json();
            setMsg(res.ok ? `📄 리포트 생성됨 — 리포트 보관함에서 다운로드 (${b.relpath})` : `❌ ${b.detail}`);
          }}>📄 Word 리포트 생성</button>
          <p style={{ fontSize: 12, color: "#888" }}>{proposal.disclaimer}</p>
        </div>
      )}
    </section>
  );
}
