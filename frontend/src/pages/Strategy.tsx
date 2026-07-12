import { useEffect, useRef, useState } from "react";
import { api, StrategyData } from "../api/client";

const PERSONAS: { key: StrategyData["persona"]; label: string; desc: string }[] = [
  { key: "value", label: "🏛️ 가치투자자", desc: "저평가 기업, 장기 보유" },
  { key: "growth", label: "🚀 성장주 투자자", desc: "고성장 기업, Tier 1 기준" },
  { key: "trader", label: "⚡ 단기 트레이더", desc: "추세·수급, 기계적 손절" },
];
const ALLOC_FIELDS: [string, string][] = [
  ["stock_pct", "주식 비중(%)"], ["cash_pct", "현금 비중(%)"],
  ["domestic_pct", "국내 비중(%)"], ["overseas_pct", "해외 비중(%)"],
];
const box = { border: "1px solid #e5e7eb", borderRadius: 10, padding: 14, marginBottom: 16 } as const;

export default function Strategy() {
  const [data, setData] = useState<StrategyData | null>(null);
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () =>
    api.getStrategy().then((d) => { setData(d); setText(d.guideline_text); })
      .catch(() => setMsg("❌ 백엔드 연결 실패"));
  useEffect(() => { load(); }, []);

  if (!data) return <section><h2>투자전략</h2><p>{msg || "불러오는 중…"}</p></section>;

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(""), 2500); };

  return (
    <section>
      <h2>투자전략 <span style={{ fontSize: 13, color: "#888" }}>지침 v{data.version}</span></h2>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      <div style={box}>
        <h3>페르소나 (종목분석·리밸런싱에 반영)</h3>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {PERSONAS.map((p) => (
            <label key={p.key} style={{
              border: data.persona === p.key ? "2px solid #2563eb" : "1px solid #ddd",
              borderRadius: 10, padding: "10px 16px", cursor: "pointer",
            }}>
              <input type="radio" name="persona" checked={data.persona === p.key}
                onChange={async () => { const d = await api.setPersona(p.key); setData(d); setText(d.guideline_text); }}
                style={{ marginRight: 6 }} />
              <b>{p.label}</b>
              <div style={{ fontSize: 12, color: "#666", marginLeft: 22 }}>{p.desc}</div>
            </label>
          ))}
        </div>
      </div>

      <div style={box}>
        <h3>행동양식·투자지침</h3>
        <textarea value={text} onChange={(e) => setText(e.target.value)}
          rows={10} style={{ width: "100%", padding: 10, fontFamily: "inherit" }} />
        <button onClick={async () => {
          const r = await api.saveGuideline(text);
          flash(`저장됨 ✅ (v${r.version})`);
          load();
        }} style={{ marginTop: 6 }}>지침 저장</button>
      </div>

      <div style={box}>
        <h3>지침 문서 업로드 (MD·TXT·Word·PDF)</h3>
        {data.files.map((f) => (
          <div key={f.id} style={{ fontSize: 13, marginBottom: 2 }}>📄 {f.filename}
            <span style={{ color: "#999" }}> — {f.uploaded_at.replace("T", " ")}</span></div>
        ))}
        <input ref={fileRef} type="file" accept=".md,.txt,.docx,.pdf" style={{ marginTop: 6 }}
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            try { await api.uploadStrategyFile(f); flash("업로드·파싱 완료 ✅"); load(); }
            catch { flash("❌ 지원하지 않는 형식이거나 업로드 실패"); }
            if (fileRef.current) fileRef.current.value = "";
          }} />
      </div>

      <div style={box}>
        <h3>목표 자산배분 (리밸런싱 기준값)</h3>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {ALLOC_FIELDS.map(([k, label]) => (
            <label key={k} style={{ fontSize: 13 }}>
              {label}<br />
              <input type="number" min={0} max={100} value={data.allocation[k] ?? ""}
                onChange={(e) => setData({ ...data,
                  allocation: { ...data.allocation, [k]: Number(e.target.value) } })}
                style={{ width: 110, padding: 6, marginTop: 2 }} />
            </label>
          ))}
        </div>
        <button style={{ marginTop: 10 }} onClick={async () => {
          await api.saveAllocation(data.allocation);
          flash("목표배분 저장됨 ✅");
        }}>배분 저장</button>
      </div>
    </section>
  );
}
