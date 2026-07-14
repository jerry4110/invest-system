import { useCallback, useEffect, useState } from "react";
import { api, PortfolioData } from "../api/client";
import Donut from "../components/Donut";
import TrendChart from "../components/TrendChart";

const won = (v: number) => v.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
const pnlColor = (v: number) => (v >= 0 ? "#dc2626" : "#2563eb");
const sign = (v: number) => (v >= 0 ? "+" : "");
const cell = { padding: "5px 8px", borderBottom: "1px solid #eee", textAlign: "right" as const, fontSize: 13 };
const cellL = { ...cell, textAlign: "left" as const };
const th = { ...cell, fontWeight: 600 as const, color: "#555" };
const thL = { ...cellL, fontWeight: 600 as const, color: "#555" };

interface HoldingRow2 {
  account: string; name: string; ticker: string; market: string; sector: string;
  qty: number; avg_price: number; buy_amount: number; cur_price: number;
  eval_amount: number; pnl_amount: number; pnl_pct: number;
  weight_pct: number; weight_in_account_pct?: number; as_of: string;
}
interface AccountCard {
  name: string; holdings: HoldingRow2[]; cash: number; cash_source: string;
  eval_amount: number; buy_amount: number; pnl_amount: number; pnl_pct: number;
  total: number; weight_pct: number;
}
interface Grouped {
  by: string;
  groups: { label: string; holdings: HoldingRow2[]; eval_amount: number;
            pnl_amount: number; pnl_pct: number; weight_pct: number;
            count: number; account_count: number }[];
}

type View = "account" | "invest" | "sector" | "analysis";
const VIEWS: [View, string][] = [
  ["account", "계좌별"], ["invest", "투자유형별"], ["sector", "산업별"], ["analysis", "분석"],
];

export default function Portfolio() {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [accounts, setAccounts] = useState<AccountCard[]>([]);
  const [grouped, setGrouped] = useState<Grouped | null>(null);
  const [view, setView] = useState<View>("account");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [cashEdit, setCashEdit] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");
  const [analysis, setAnalysis] = useState<Awaited<ReturnType<typeof api.getAnalysis>> | null>(null);
  const [returnsData, setReturnsData] = useState<Awaited<ReturnType<typeof api.getReturns>> | null>(null);
  const [trend, setTrend] = useState<{ date: string; total_asset: number }[]>([]);

  const load = useCallback(() => {
    api.getHoldings().then(setData).catch(() => setMsg("❌ 백엔드 연결 실패"));
    fetch("/api/portfolio/by-account").then((r) => r.json())
      .then((b) => {
        setAccounts(b.accounts);
        setOpen((prev) => Object.keys(prev).length ? prev
          : Object.fromEntries(b.accounts.slice(0, 1).map((a: AccountCard) => [a.name, true])));
      }).catch(() => {});
    api.getAnalysis().then(setAnalysis).catch(() => {});
    api.getReturns().then(setReturnsData).catch(() => {});
    api.getTrend().then(setTrend).catch(() => {});
  }, []);
  useEffect(load, [load]);

  useEffect(() => {
    if (view === "invest" || view === "sector") {
      fetch(`/api/portfolio/grouped?by=${view}`).then((r) => r.json()).then(setGrouped).catch(() => {});
    }
  }, [view, data]);

  if (!data) return <section><h2>포트폴리오</h2><p>{msg || "불러오는 중…"}</p></section>;
  const { totals, as_of } = data;
  const stale = as_of && Date.now() - new Date(as_of).getTime() > 24 * 3600 * 1000;

  const scan = async (force = false) => {
    const r = await api.scanBalanceFolder(force);
    if (r.imported) setMsg(`✅ 잔고 파일 ${r.imported}건 반영 (${r.folder})`);
    else if (r.files.length === 0) setMsg(`감시 폴더(${r.folder})에 잔고 파일이 없습니다`);
    else {
      const failed = r.files.filter((f) => f.status === "failed");
      setMsg(failed.length ? `❌ ${failed[0].file}: ${failed[0].reason}` : "변경 없음 — '강제 재스캔' 가능");
    }
    load();
  };

  const saveCash = async (account: string) => {
    const raw = cashEdit[account];
    if (raw == null) return;
    await api.setCash(Number(raw.replace(/,/g, "")) || 0, account);
    setCashEdit((p) => ({ ...p, [account]: undefined as unknown as string }));
    setMsg(`💾 ${account} 예수금 저장됨 (수동 입력은 파일 재적재에도 유지)`);
    load();
  };

  const holdingsTable = (hs: HoldingRow2[], showAccount: boolean, weightKey: "weight_pct" | "weight_in_account_pct") => (
    <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
      <thead><tr>
        <th style={{ ...thL, width: "24%" }}>종목명</th>
        {showAccount && <th style={{ ...thL, width: "14%" }}>계좌</th>}
        <th style={th}>수량</th><th style={th}>평균단가</th><th style={th}>평가금액</th>
        <th style={th}>평가손익</th><th style={{ ...th, width: "9%" }}>수익률</th>
        <th style={{ ...th, width: "8%" }}>비중</th>
      </tr></thead>
      <tbody>
        {hs.map((h) => (
          <tr key={`${h.account}-${h.ticker}`}>
            <td style={cellL}>{h.name}{h.market === "OVERSEAS" &&
              <span style={{ fontSize: 10, color: "#2563eb", marginLeft: 4 }}>해외</span>}</td>
            {showAccount && <td style={{ ...cellL, color: "#888" }}>{h.account}</td>}
            <td style={cell}>{h.qty.toLocaleString()}</td>
            <td style={cell}>{won(h.avg_price)}</td>
            <td style={cell}>{won(h.eval_amount)}</td>
            <td style={{ ...cell, color: pnlColor(h.pnl_amount) }}>{sign(h.pnl_amount)}{won(h.pnl_amount)}</td>
            <td style={{ ...cell, color: pnlColor(h.pnl_amount) }}>{sign(h.pnl_pct)}{h.pnl_pct.toFixed(1)}%</td>
            <td style={cell}>{(h[weightKey] ?? h.weight_pct).toFixed(1)}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <section>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4, flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>포트폴리오</h2>
        {as_of && <span style={{ fontSize: 12, color: stale ? "#d97706" : "#888" }}>
          잔고 기준: {as_of.replace("T", " ")}{stale && " ⚠️ 24시간 경과"}</span>}
        <span style={{ flex: 1 }} />
        <button onClick={() => scan(false)} style={{ fontSize: 12 }}>잔고 파일 스캔</button>
        <button onClick={() => scan(true)} style={{ fontSize: 12 }}>강제 재스캔</button>
        <button style={{ fontSize: 12, color: "#dc2626" }} onClick={async () => {
          if (!confirm("보유종목·예수금(파일분)·계좌를 모두 삭제 후 폴더에서 다시 불러옵니다. 계속할까요?")) return;
          await fetch("/api/portfolio/reset", { method: "POST" });
          const r = await api.scanBalanceFolder(true);
          setMsg(r.imported ? `🔄 초기화 후 ${r.imported}개 파일 재적재 (${r.folder})` : `🔄 초기화됨 — 폴더(${r.folder}) 비어있음`);
          load();
        }}>전체 초기화+재적재</button>
        <a href="/api/portfolio/export.csv" download style={{ fontSize: 12 }}>CSV</a>
      </div>
      {msg && <p style={{ fontSize: 13 }}>{msg}</p>}

      <div style={{ display: "flex", gap: 14, margin: "10px 0", flexWrap: "wrap" }}>
        {[["총자산", won(totals.total_asset) + "원", undefined],
          ["평가금액", won(totals.eval_amount) + "원", undefined],
          ["예수금 합계", won(totals.cash) + "원", undefined],
          ["평가손익", `${sign(totals.pnl_amount)}${won(totals.pnl_amount)}원 (${sign(totals.pnl_pct)}${totals.pnl_pct}%)`,
           pnlColor(totals.pnl_amount)]].map(([k, v, color]) => (
          <div key={k as string} style={{ background: "#f8fafc", borderRadius: 8, padding: "8px 16px" }}>
            <div style={{ fontSize: 12, color: "#666" }}>{k}</div>
            <div style={{ fontWeight: 700, color: (color as string) || "inherit" }}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 4, margin: "6px 0 14px", flexWrap: "wrap" }}>
        {VIEWS.map(([k, label]) => (
          <button key={k} onClick={() => setView(k)}
            style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid #ddd",
              background: view === k ? "#2563eb" : "#fff", color: view === k ? "#fff" : "#333" }}>
            {label}
          </button>
        ))}
      </div>

      {view === "account" && accounts.map((a) => (
        <div key={a.name} style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: "10px 14px", marginBottom: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <span style={{ cursor: "pointer", fontWeight: 700 }}
              onClick={() => setOpen((p) => ({ ...p, [a.name]: !p[a.name] }))}>
              {open[a.name] ? "▼" : "▶"} {a.name}
            </span>
            <span style={{ fontSize: 12, color: "#888" }}>{a.holdings.length}종목</span>
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 12, color: "#666" }}>예수금{a.cash_source === "manual" && " (수동)"}</span>
            <input value={cashEdit[a.name] ?? won(a.cash)} style={{ width: 110, padding: 4, fontSize: 12, textAlign: "right" }}
              onChange={(e) => setCashEdit((p) => ({ ...p, [a.name]: e.target.value }))}
              onKeyDown={(e) => e.key === "Enter" && saveCash(a.name)} />
            <button style={{ fontSize: 12 }} onClick={() => saveCash(a.name)}>저장</button>
            <span style={{ fontSize: 13 }}>
              합계 <b>{won(a.total)}원</b> ({a.weight_pct}%) ·{" "}
              <span style={{ color: pnlColor(a.pnl_amount) }}>{sign(a.pnl_pct)}{a.pnl_pct}%</span>
            </span>
          </div>
          {open[a.name] && a.holdings.length > 0 && (
            <div style={{ marginTop: 8 }}>
              {holdingsTable(a.holdings, false, "weight_in_account_pct")}
              <div style={{ display: "flex", gap: 16, fontSize: 13, fontWeight: 700, padding: "6px 8px", background: "#f8fafc" }}>
                <span>계좌 합계 (평가+예수금)</span><span style={{ flex: 1 }} />
                <span>{won(a.total)}원</span>
                <span style={{ color: pnlColor(a.pnl_amount) }}>{sign(a.pnl_amount)}{won(a.pnl_amount)}원</span>
              </div>
            </div>
          )}
        </div>
      ))}

      {(view === "invest" || view === "sector") && grouped && grouped.by === view &&
        grouped.groups.map((g) => (
          <div key={g.label} style={{ border: "1px solid #e5e7eb", borderRadius: 10, padding: "10px 14px", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6, flexWrap: "wrap" }}>
              <span style={{ background: "#eff6ff", color: "#1d4ed8", fontSize: 12, padding: "2px 10px", borderRadius: 10 }}>{g.label}</span>
              <span style={{ fontSize: 12, color: "#888" }}>{g.count}종목 · {g.account_count}계좌</span>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 13, fontWeight: 700 }}>
                {won(g.eval_amount)}원 ({g.weight_pct}%) ·{" "}
                <span style={{ color: pnlColor(g.pnl_amount) }}>{sign(g.pnl_pct)}{g.pnl_pct}%</span>
              </span>
            </div>
            {holdingsTable(g.holdings, true, "weight_pct")}
          </div>
        ))}

      {view === "analysis" && (
        <div>
          <div style={{ display: "flex", gap: 32, flexWrap: "wrap", marginBottom: 16 }}>
            {analysis && analysis.by_type.length > 0 && <div><h3>투자유형별</h3><Donut parts={analysis.by_type} /></div>}
            {analysis && analysis.by_sector.length > 0 && <div><h3>산업별</h3><Donut parts={analysis.by_sector.slice(0, 6)} /></div>}
          </div>
          <h3>기간별 수익률 (vs 코스피)</h3>
          {returnsData && returnsData.returns.length > 0 ? (
            <table style={{ borderCollapse: "collapse", fontSize: 14, marginBottom: 16 }}>
              <thead><tr style={{ background: "#f8fafc" }}>
                {["기간", "내 수익률", "코스피", "초과수익"].map((hh) => (
                  <th key={hh} style={{ padding: "6px 16px", borderBottom: "1px solid #eee" }}>{hh}</th>))}
              </tr></thead>
              <tbody>
                {returnsData.returns.map((r) => (
                  <tr key={r.period}>
                    <td style={{ padding: "6px 16px" }}>{{ "1w": "1주", "1m": "1개월", "3m": "3개월", "1y": "1년" }[r.period]}</td>
                    <td style={{ padding: "6px 16px", color: pnlColor(r.portfolio_pct) }}>{sign(r.portfolio_pct)}{r.portfolio_pct}%</td>
                    <td style={{ padding: "6px 16px" }}>{r.benchmark_pct != null ? `${sign(r.benchmark_pct)}${r.benchmark_pct}%` : "-"}</td>
                    <td style={{ padding: "6px 16px", fontWeight: 600, color: pnlColor(r.excess_pct ?? 0) }}>
                      {r.excess_pct != null ? `${sign(r.excess_pct)}${r.excess_pct}%p` : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ color: "#888", fontSize: 13 }}>스냅샷이 쌓이면 기간 수익률이 표시됩니다.</p>}
          <h3>자산 추이</h3>
          <TrendChart data={trend} />
        </div>
      )}
    </section>
  );
}
