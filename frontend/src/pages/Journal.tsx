import { useEffect, useRef, useState } from "react";
import { api, JournalStats, JournalTx } from "../api/client";

const won = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const cell = { padding: "6px 10px", borderBottom: "1px solid #eee" } as const;

export default function Journal() {
  const [txs, setTxs] = useState<JournalTx[]>([]);
  const [stats, setStats] = useState<JournalStats | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [noteText, setNoteText] = useState("");
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    api.getTransactions().then(setTxs).catch(() => setMsg("❌ 백엔드 연결 실패"));
    api.getJournalStats().then(setStats).catch(() => {});
  };
  useEffect(load, []);

  const saveNote = async (id: number) => {
    await api.setTxNote(id, noteText);
    setEditId(null);
    load();
  };

  return (
    <section>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>투자저널</h2>
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            try {
              const r = await api.uploadTrades(f);
              setMsg(`✅ 거래 ${r.imported}건 추가 (중복 제외)`);
              load();
            } catch { setMsg("❌ 거래내역 파일 인식 실패 — 컬럼(거래일자·종목명·구분·수량·단가) 확인"); }
            if (fileRef.current) fileRef.current.value = "";
          }} />
        <span style={{ fontSize: 12, color: "#888" }}>HTS 거래내역 내보내기 파일 업로드</span>
      </div>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      {stats && stats.sell_count > 0 && (
        <div style={{ display: "flex", gap: 16, margin: "12px 0", flexWrap: "wrap" }}>
          {[["실현손익 누계", `${won(stats.total_realized_pnl)}원`],
            ["매도 횟수", `${stats.sell_count}회`],
            ["승률", `${stats.win_rate_pct}%`],
            ["손익비", stats.payoff_ratio != null ? stats.payoff_ratio.toFixed(2) : "-"]].map(([k, v]) => (
            <div key={k} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 16px" }}>
              <div style={{ fontSize: 12, color: "#666" }}>{k}</div>
              <div style={{ fontWeight: 700 }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {txs.length === 0 ? (
        <p style={{ color: "#666" }}>거래내역이 없습니다 — HTS에서 거래내역을 내보내 업로드하세요.</p>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {["일시", "종목", "구분", "수량", "단가", "실현손익", "판단 근거 (클릭해서 기록)"]
                .map((h) => <th key={h} style={{ ...cell, fontWeight: 600 }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {txs.map((t) => (
              <tr key={t.id}>
                <td style={cell}>{t.executed_at.slice(0, 10)}</td>
                <td style={cell}>{t.ticker}</td>
                <td style={{ ...cell, color: t.side === "buy" ? "#dc2626" : "#2563eb" }}>
                  {t.side === "buy" ? "매수" : "매도"}
                </td>
                <td style={cell}>{t.qty.toLocaleString()}</td>
                <td style={cell}>{won(t.price)}</td>
                <td style={{ ...cell, color: (t.realized_pnl ?? 0) >= 0 ? "#dc2626" : "#2563eb" }}>
                  {t.realized_pnl != null ? won(t.realized_pnl) : "-"}
                </td>
                <td style={{ ...cell, cursor: "pointer", minWidth: 220 }}
                  onClick={() => { setEditId(t.id); setNoteText(t.note); }}>
                  {editId === t.id ? (
                    <span style={{ display: "flex", gap: 4 }}>
                      <input autoFocus value={noteText} onChange={(e) => setNoteText(e.target.value)}
                        style={{ flex: 1, padding: 4 }}
                        onKeyDown={(e) => e.key === "Enter" && saveNote(t.id)} />
                      <button onClick={(e) => { e.stopPropagation(); saveNote(t.id); }}>저장</button>
                    </span>
                  ) : (t.note || <span style={{ color: "#bbb" }}>+ 근거 기록</span>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
