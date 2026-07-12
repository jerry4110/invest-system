// 자산 구성 도넛 차트 (FR-02-03) — SVG, 외부 라이브러리 없음
const COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#8b5cf6"];

export default function Donut({ parts }: { parts: { label: string; pct: number }[] }) {
  const r = 40, c = 2 * Math.PI * r;
  let acc = 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
      <svg width="110" height="110" viewBox="0 0 110 110">
        <circle cx="55" cy="55" r={r} fill="none" stroke="#f1f5f9" strokeWidth="14" />
        {parts.map((p, i) => {
          const dash = (p.pct / 100) * c;
          const el = (
            <circle key={p.label} cx="55" cy="55" r={r} fill="none"
              stroke={COLORS[i % COLORS.length]} strokeWidth="14"
              strokeDasharray={`${dash} ${c - dash}`}
              strokeDashoffset={-acc} transform="rotate(-90 55 55)" />
          );
          acc += dash;
          return el;
        })}
      </svg>
      <div>
        {parts.map((p, i) => (
          <div key={p.label} style={{ fontSize: 13, marginBottom: 2 }}>
            <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2,
              background: COLORS[i % COLORS.length], marginRight: 6 }} />
            {p.label} {p.pct.toFixed(1)}%
          </div>
        ))}
      </div>
    </div>
  );
}
