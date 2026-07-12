// 30일 미니 추이 차트 (FR-02-13) — 외부 라이브러리 없이 SVG
export default function Sparkline({ data, up }: { data: number[]; up: boolean }) {
  if (data.length < 2) return null;
  const w = 120, h = 32;
  const min = Math.min(...data), max = Math.max(...data);
  const span = max - min || 1;
  const pts = data
    .map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / span) * (h - 4) - 2}`)
    .join(" ");
  return (
    <svg width={w} height={h} aria-hidden="true">
      <polyline points={pts} fill="none" stroke={up ? "#dc2626" : "#2563eb"} strokeWidth="1.5" />
    </svg>
  );
}
