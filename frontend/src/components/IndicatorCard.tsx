import { Indicator } from "../api/client";
import Sparkline from "./Sparkline";

const fmt = (code: string, v: number) => {
  const digits = code === "USDKRW" || code === "UST10Y" ? 2 : v >= 1000 ? 0 : 2;
  return v.toLocaleString("ko-KR", { maximumFractionDigits: digits, minimumFractionDigits: digits ? 2 : 0 });
};

export default function IndicatorCard({ ind }: { ind: Indicator }) {
  const up = ind.change_pct >= 0; // 국내 관례: 상승 빨강 / 하락 파랑
  const color = up ? "#dc2626" : "#2563eb";
  return (
    <div style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: 14, minWidth: 190 }}>
      <div style={{ fontSize: 13, color: "#555" }}>{ind.name}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{fmt(ind.code, ind.value)}</div>
      <div style={{ color, fontSize: 13, marginBottom: 6 }}>
        {up ? "▲" : "▼"} {Math.abs(ind.change_pct).toFixed(2)}%
      </div>
      <Sparkline data={ind.spark} up={up} />
      <div style={{ fontSize: 11, color: "#999", marginTop: 4 }}>{ind.date} 기준</div>
    </div>
  );
}
