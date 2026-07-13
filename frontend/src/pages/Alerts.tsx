import { useEffect, useState } from "react";

interface AlertItem { id: number; kind: string; title: string; body: string; read: boolean; created_at: string }

const KIND_LABEL: Record<string, string> = {
  donchian: "📈 시그널", price_move: "⚡ 급등락", "13f_update": "🏛️ 13F", batch_fail: "⚠️ 배치",
};

export default function Alerts() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [unread, setUnread] = useState(0);

  const load = () =>
    fetch("/api/alerts").then((r) => r.json())
      .then((b) => { setAlerts(b.alerts); setUnread(b.unread); })
      .catch(() => {});
  useEffect(() => { load(); }, []);

  return (
    <section>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>알림센터 {unread > 0 && <span style={{ color: "#dc2626" }}>({unread})</span>}</h2>
        {unread > 0 && (
          <button onClick={async () => { await fetch("/api/alerts/read-all", { method: "PUT" }); load(); }}>
            모두 읽음
          </button>
        )}
      </div>
      {alerts.length === 0 ? (
        <p style={{ color: "#666" }}>알림이 없습니다 — Donchian 시그널·급등락·13F 변동이 여기에 쌓입니다.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, fontSize: 14 }}>
          {alerts.map((a) => (
            <li key={a.id} onClick={async () => {
                if (!a.read) { await fetch(`/api/alerts/${a.id}/read`, { method: "PUT" }); load(); }
              }}
              style={{ padding: "10px 12px", borderBottom: "1px solid #eee", cursor: "pointer",
                       background: a.read ? "transparent" : "#eff6ff" }}>
              <b>{KIND_LABEL[a.kind] ?? a.kind}</b> {a.title}
              <div style={{ fontSize: 12, color: "#666" }}>{a.body}</div>
              <div style={{ fontSize: 11, color: "#999" }}>{a.created_at.replace("T", " ")}</div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
