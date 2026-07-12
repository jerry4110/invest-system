// 자산 추이 라인차트 (FR-03-26) — SVG
export default function TrendChart({ data }: { data: { date: string; total_asset: number }[] }) {
  if (data.length < 2) return <p style={{ color: "#888", fontSize: 13 }}>추이 데이터가 쌓이면 표시됩니다 (일별 스냅샷 2개 이상 필요).</p>;
  const w = 640, h = 160, pad = 6;
  const vals = data.map((d) => d.total_asset);
  const min = Math.min(...vals), max = Math.max(...vals), span = max - min || 1;
  const pts = data.map((d, i) =>
    `${pad + (i / (data.length - 1)) * (w - pad * 2)},${h - pad - ((d.total_asset - min) / span) * (h - pad * 2)}`).join(" ");
  return (
    <div>
      <svg width={w} height={h} style={{ maxWidth: "100%" }}>
        <polyline points={pts} fill="none" stroke="#2563eb" strokeWidth="2" />
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#888", maxWidth: w }}>
        <span>{data[0].date}</span><span>{data[data.length - 1].date}</span>
      </div>
    </div>
  );
}
