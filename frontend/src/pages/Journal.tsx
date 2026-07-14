import { useCallback, useEffect, useRef, useState } from "react";
import { api, JournalStats, JournalTx } from "../api/client";

const won = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const cell = { padding: "6px 10px", borderBottom: "1px solid #eee" } as const;

export default function Journal() {
  const [txs, setTxs] = useState<JournalTx[]>([]);
  const [stats, setStats] = useState<JournalStats | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [editId, setEditId] = useState<number | null>(null);
  const [noteText, setNoteText] = useState("");
  const [msg, setMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    const q = new URLSearchParams();
    if (dateFrom) q.set("date_from", dateFrom);
    if (dateTo) q.set("date_to", dateTo);
    const qs = q.toString() ? `?${q}` : "";
    fetch(`/api/journal/transactions${qs}`).then((r) => r.json()).then(setTxs)
      .catch(() => setMsg("❌ 백엔드 연결 실패"));
    fetch(`/api/journal/stats${qs}`).then((r) => r.json()).then(setStats).catch(() => {});
    setChecked(new Set());
  }, [dateFrom, dateTo]);
  useEffect(load, [load]);

  const saveNote = async (id: number) => {
    await api.setTxNote(id, noteText);
    setEditId(null);
    load();
  };

  const toggleAll = () =>
    setChecked(checked.size === txs.length ? new Set() : new Set(txs.map((t) => t.id)));

  const deleteChecked = async () => {
    if (checked.size === 0) return;
    if (!confirm(`선택한 거래 ${checked.size}건을 삭제할까요? 실현손익이 재계산됩니다.`)) return;
    const r = await fetch("/api/journal/transactions", {
      method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: [...checked] }),
    });
    const b = await r.json();
    setMsg(r.ok ? `🗑️ ${b.deleted}건 삭제됨` : `❌ ${b.detail}`);
    load();
  };

  return (
    <section>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>투자저널</h2>
        <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            try {
              const r = await api.uploadTrades(f);
              setMsg(`✅ 거래 ${r.imported}건 추가 (기존 유지, 중복 제외)`);
              load();
            } catch { setMsg("❌ 파일 인식 실패 — 거래내역/기간매매 형식 확인"); }
            if (fileRef.current) fileRef.current.value = "";
          }} />
        <span style={{ fontSize: 12, color: "#888" }}>거래내역·기간 중 매매 내보내기 파일 업로드</span>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "10px 0", flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, color: "#666" }}>기간 조회:</span>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={{ padding: 5 }} />
        <span>~</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={{ padding: 5 }} />
        {(dateFrom || dateTo) && (
          <button style={{ fontSize: 12 }} onClick={() => { setDateFrom(""); setDateTo(""); }}>전체 보기</button>
        )}
        <span style={{ flex: 1 }} />
        <button onClick={deleteChecked} disabled={checked.size === 0}
          style={{ fontSize: 12, color: checked.size ? "#dc2626" : "#999" }}>
          🗑️ 선택 삭제{checked.size > 0 && ` (${checked.size})`}
        </button>
      </div>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      {stats && stats.sell_count > 0 && (
        <div style={{ display: "flex", gap: 16, margin: "12px 0", flexWrap: "wrap" }}>
          {[["실현손익 누계", `${won(stats.total_realized_pnl)}원`],
            ["매도 횟수", `${stats.sell_count}회`],
            ["승률", `${stats.win_rate_pct}%`],
            ["손익비", stats.payoff_ratio != null ? stats.payoff_ratio.toFixed(2) : "-"]].map(([k, v]) => (
            <div key={k} style={{ border: "1px solid #e5e7eb", borderRadius: 8, padding: "8px 16px" }}>
              <div style={{ fontSize: 12, color: "#666" }}>{k}{(dateFrom || dateTo) && " (조회기간)"}</div>
              <div style={{ fontWeight: 700 }}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {txs.length === 0 ? (
        <p style={{ color: "#666" }}>조회된 거래가 없습니다.</p>
      ) : (
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 14 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              <th style={cell}><input type="checkbox"
                checked={checked.size === txs.length && txs.length > 0} onChange={toggleAll} /></th>
              {["일시", "종목", "구분", "수량", "단가", "금액", "실현손익", "판단 근거 (클릭해서 기록)"]
                .map((h) => <th key={h} style={{ ...cell, fontWeight: 600 }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {txs.map((t) => (
              <tr key={t.id} style={{ background: checked.has(t.id) ? "#fef2f2" : "transparent" }}>
                <td style={cell}><input type="checkbox" checked={checked.has(t.id)}
                  onChange={() => setChecked((p) => {
                    const n = new Set(p);
                    if (n.has(t.id)) n.delete(t.id); else n.add(t.id);
                    return n;
                  })} /></td>
                <td style={cell}>{t.executed_at.slice(0, 10)}</td>
                <td style={cell}>{t.ticker}</td>
                <td style={{ ...cell, color: t.side === "buy" ? "#dc2626" : "#2563eb" }}>
                  {t.side === "buy" ? "매수" : "매도"}</td>
                <td style={cell}>{t.qty.toLocaleString()}</td>
                <td style={cell}>{won(t.price)}</td>
                <td style={cell}>{won(t.amount)}</td>
                <td style={{ ...cell, color: (t.realized_pnl ?? 0) >= 0 ? "#dc2626" : "#2563eb" }}>
                  {t.realized_pnl != null ? won(t.realized_pnl) : "-"}</td>
                <td style={{ ...cell, cursor: "pointer", minWidth: 200 }}
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
