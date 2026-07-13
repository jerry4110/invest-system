import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Portfolio from "./pages/Portfolio";
import Strategy from "./pages/Strategy";
import Settings from "./pages/Settings";
import Journal from "./pages/Journal";
import Analysis from "./pages/Analysis";
import Reports from "./pages/Reports";
import Alerts from "./pages/Alerts";
import { useEffect, useState } from "react";

const navStyle = ({ isActive }: { isActive: boolean }) => ({
  padding: "8px 14px",
  textDecoration: "none",
  color: isActive ? "#fff" : "#333",
  background: isActive ? "#2563eb" : "transparent",
  borderRadius: 6,
});

export default function App() {
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    const tick = () => fetch("/api/alerts/unread-count").then((r) => r.json())
      .then((b) => setUnread(b.unread)).catch(() => {});
    tick();
    const t = setInterval(tick, 30000);
    return () => clearInterval(t);
  }, []);
  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <header style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, marginRight: 16 }}>📈 개인투자관리시스템</h1>
        <NavLink to="/" style={navStyle} end>🏠 대시보드</NavLink>
        <NavLink to="/portfolio" style={navStyle}>💼 포트폴리오</NavLink>
        <NavLink to="/strategy" style={navStyle}>🎯 투자전략</NavLink>
        <NavLink to="/analysis" style={navStyle}>🔍 종목분석</NavLink>
        <NavLink to="/journal" style={navStyle}>📓 투자저널</NavLink>
        <NavLink to="/alerts" style={navStyle}>🔔 알림{unread > 0 && <span style={{ background: "#dc2626", color: "#fff", borderRadius: 10, padding: "0 6px", fontSize: 11, marginLeft: 4 }}>{unread}</span>}</NavLink>
        <NavLink to="/reports" style={navStyle}>📄 리포트</NavLink>
        <NavLink to="/settings" style={navStyle}>⚙️ 설정</NavLink>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/strategy" element={<Strategy />} />
        <Route path="/analysis" element={<Analysis />} />
        <Route path="/journal" element={<Journal />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </div>
  );
}
