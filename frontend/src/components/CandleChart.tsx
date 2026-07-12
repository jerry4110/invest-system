// 캔들차트 + 이동평균 오버레이 (FR-04-18) — SVG, 외부 라이브러리 없음
interface Bar { date: string; open: number; high: number; low: number; close: number; volume: number }

export default function CandleChart({ data }: { data: Bar[] }) {
  if (data.length < 2) return null;
  const w = 720, h = 220, volH = 40, pad = 4;
  const bars = data.slice(-90);
  const min = Math.min(...bars.map((b) => b.low));
  const max = Math.max(...bars.map((b) => b.high));
  const span = max - min || 1;
  const maxVol = Math.max(...bars.map((b) => b.volume)) || 1;
  const bw = (w - pad * 2) / bars.length;
  const y = (v: number) => pad + (1 - (v - min) / span) * (h - pad * 2);

  const ma = (n: number) =>
    bars.map((_, i) => {
      const src = data.slice(0, data.length - bars.length + i + 1);
      if (src.length < n) return null;
      return src.slice(-n).reduce((a, b) => a + b.close, 0) / n;
    });
  const lines: [number, string][] = [[5, "#f59e0b"], [20, "#8b5cf6"], [60, "#0891b2"]];

  return (
    <div>
      <svg width={w} height={h + volH} style={{ maxWidth: "100%" }}>
        {bars.map((b, i) => {
          const x = pad + i * bw + bw / 2;
          const up = b.close >= b.open;
          const color = up ? "#dc2626" : "#2563eb";
          return (
            <g key={b.date}>
              <line x1={x} x2={x} y1={y(b.high)} y2={y(b.low)} stroke={color} strokeWidth="1" />
              <rect x={x - bw * 0.3} width={bw * 0.6}
                y={y(Math.max(b.open, b.close))}
                height={Math.max(Math.abs(y(b.open) - y(b.close)), 1)}
                fill={color} />
              <rect x={x - bw * 0.3} width={bw * 0.6}
                y={h + volH - (b.volume / maxVol) * volH}
                height={(b.volume / maxVol) * volH} fill="#cbd5e1" />
            </g>
          );
        })}
        {lines.map(([n, color]) => {
          const vals = ma(n);
          const pts = vals.map((v, i) =>
            v == null ? null : `${pad + i * bw + bw / 2},${y(v)}`).filter(Boolean).join(" ");
          return <polyline key={n} points={pts} fill="none" stroke={color} strokeWidth="1.5" />;
        })}
      </svg>
      <div style={{ fontSize: 11, color: "#888" }}>
        <span style={{ color: "#f59e0b" }}>━ MA5</span>{" "}
        <span style={{ color: "#8b5cf6" }}>━ MA20</span>{" "}
        <span style={{ color: "#0891b2" }}>━ MA60</span>{" "}
        · {bars[0].date} ~ {bars[bars.length - 1].date} · 하단: 거래량
      </div>
    </div>
  );
}
