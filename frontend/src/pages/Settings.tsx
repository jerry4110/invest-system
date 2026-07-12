import { useEffect, useState } from "react";
import { api, SecretItem, Settings as SettingsType } from "../api/client";

const box = { border: "1px solid #ddd", borderRadius: 8, padding: 16, marginBottom: 16 } as const;
const label = { display: "block", fontSize: 13, color: "#555", marginBottom: 4 } as const;
const input = { width: "100%", maxWidth: 420, padding: 8, marginBottom: 12 } as const;

export default function Settings() {
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [secrets, setSecrets] = useState<SecretItem[]>([]);
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [msg, setMsg] = useState("");

  const load = () => {
    api.getSettings().then(setSettings).catch(() => setMsg("설정을 불러오지 못했습니다"));
    api.listSecrets().then(setSecrets).catch(() => {});
  };
  useEffect(load, []);

  if (!settings) return <p>불러오는 중…</p>;

  const save = async () => {
    await api.updateSettings(settings);
    setMsg("저장되었습니다 ✅");
    setTimeout(() => setMsg(""), 2000);
  };

  const addSecret = async () => {
    if (!newKey || !newValue) return;
    await api.setSecret(newKey, newValue);
    setNewKey("");
    setNewValue(""); // 입력값은 즉시 화면에서 제거 — 값은 다시 조회 불가(암호화 저장)
    load();
  };

  return (
    <section>
      <h2>설정</h2>

      <div style={box}>
        <h3>📂 잔고 파일 자동 인식 (D-013)</h3>
        <label style={label}>감시 폴더 — HTS에서 내보낸 잔고 파일을 이 폴더에서 자동 인식합니다</label>
        <input style={input} value={settings.watch_folder}
          onChange={(e) => setSettings({ ...settings, watch_folder: e.target.value })} />
        <label style={{ display: "block", marginBottom: 12 }}>
          <input type="checkbox" checked={settings.watch_enabled}
            onChange={(e) => setSettings({ ...settings, watch_enabled: e.target.checked })} />
          {" "}폴더 감시 활성화
        </label>
      </div>

      <div style={box}>
        <h3>⏰ 자동 갱신</h3>
        <label style={label}>매일 갱신 시각 (기본 08:00)</label>
        <input style={input} type="time" value={settings.refresh_time}
          onChange={(e) => setSettings({ ...settings, refresh_time: e.target.value })} />
      </div>

      <div style={box}>
        <h3>🔐 API 키 (암호화 저장)</h3>
        <p style={{ fontSize: 13, color: "#666" }}>
          DART·OpenAI 키는 Phase 2에서 사용됩니다. 저장된 값은 다시 표시되지 않습니다.
        </p>
        {secrets.map((s) => (
          <div key={s.key} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <code style={{ minWidth: 160 }}>{s.key}</code>
            <span>{s.masked}</span>
            <button onClick={() => api.deleteSecret(s.key).then(load)}>삭제</button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <input placeholder="키 이름 (예: openai_api_key)" value={newKey}
            onChange={(e) => setNewKey(e.target.value)} style={{ padding: 8 }} />
          <input placeholder="값" type="password" value={newValue}
            onChange={(e) => setNewValue(e.target.value)} style={{ padding: 8 }} />
          <button onClick={addSecret}>추가</button>
        </div>
      </div>

      <button onClick={save} style={{ padding: "10px 24px", background: "#2563eb", color: "#fff", border: 0, borderRadius: 6 }}>
        저장
      </button>
      {msg && <span style={{ marginLeft: 12 }}>{msg}</span>}
    </section>
  );
}
