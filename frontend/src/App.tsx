import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Portfolio from "./pages/Portfolio";
import Strategy from "./pages/Strategy";
import Settings from "./pages/Settings";
import Journal from "./pages/Journal";
import Analysis from "./pages/Analysis";

const navStyle = ({ isActive }: { isActive: boolean }) => ({
  padding: "8px 14px",
  textDecoration: "none",
  color: isActive ? "#fff" : "#333",
  background: isActive ? "#2563eb" : "transparent",
  borderRadius: 6,
});

export default function App() {
  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <header style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, marginRight: 16 }}>📈 개인투자관리시스템</h1>
        <NavLink to="/" style={navStyle} end>🏠 대시보드</NavLink>
        <NavLink to="/portfolio" style={navStyle}>💼 포트폴리오</NavLink>
        <NavLink to="/strategy" style={navStyle}>🎯 투자전략</NavLink>
        <NavLink to="/analysis" style={navStyle}>🔍 종목분석</NavLink>
        <NavLink to="/journal" style={navStyle}>📓 투자저널</NavLink>
        <NavLink to="/settings" style={navStyle}>⚙️ 설정</NavLink>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/portfolio" element={<Portfolio />} />
        <Route path="/strategy" element={<Strategy />} />
        <Route path="/analysis" element={<Analysis />} />
        <Route path="/journal" element={<Journal />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </div>
  );
}
