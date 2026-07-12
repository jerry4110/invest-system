import { useEffect, useState } from "react";

interface ReportItem { id: number; ticker: string; kind: string; filename: string; created_at: string }

export default function Reports() {
  const [items, setItems] = useState<ReportItem[]>([]);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetch("/api/reports").then((r) => r.json()).then(setItems)
      .catch(() => setMsg("❌ 백엔드 연결 실패"));
  }, []);

  return (
    <section>
      <h2>리포트 보관함</h2>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}
      {items.length === 0 ? (
        <p style={{ color: "#666" }}>생성된 리포트가 없습니다 — 종목분석 페이지에서 "리포트 생성"을 눌러보세요.</p>
      ) : (
        <ul style={{ fontSize: 14 }}>
          {items.map((r) => (
            <li key={r.id} style={{ marginBottom: 6 }}>
              📄 <a href={`/api/reports/${r.id}/download`}>{r.filename}</a>
              <span style={{ color: "#888", fontSize: 12 }}> — {r.ticker} · {r.created_at.replace("T", " ")}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
