// T-04 수용 기준(프론트): 지표 카드 렌더링·갱신 버튼 (Codex 리뷰 Major 반영 — Vitest 도입)
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Dashboard from "../pages/Dashboard";

const indicator = (code: string, name: string) => ({
  code, name, category: "index", value: 1234.56, change_pct: -1.23,
  date: "2026-07-12", as_of: "2026-07-12T08:00:00", spark: [1, 2, 3],
});

afterEach(cleanup);

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      url.includes("indicators")
        ? [indicator("KOSPI", "코스피"), indicator("BTC", "비트코인")]
        : url.includes("summary")
        ? { total_asset: 12000000, total_buy: 8200000, total_eval: 10000000,
            total_pnl: 1800000, total_pnl_pct: 21.95, total_cash: 2000000,
            day_change: { amount: 1000000, pct: 9.09, vs_date: "2026-07-11" },
            composition: [{ label: "국내주식", amount: 7500000, pct: 62.5 }],
            as_of: "2026-07-12T08:00:00" }
        : { status: "ok", version: "t", as_of: "2026-07-12T08:00:00" },
  })) as unknown as typeof fetch);
});

describe("Dashboard", () => {
  it("지표 카드와 기준시각을 표시한다", async () => {
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByText("코스피")).toBeTruthy());
    expect(screen.getByText("비트코인")).toBeTruthy();
    expect(screen.getAllByText(/2026-07-12/).length).toBeGreaterThan(0); // as_of 배지
  });

  it("자산 요약과 전일 대비를 표시한다 (FR-02-01~02)", async () => {
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByText("12,000,000원")).toBeTruthy());
    expect(screen.getByText(/전일 대비/)).toBeTruthy();
    expect(screen.getByText(/국내주식/)).toBeTruthy(); // 구성 차트 (FR-02-03)
  });

  it("업데이트 버튼이 있다 (FR-02-22)", async () => {
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByRole("button", { name: /업데이트/ })).toBeTruthy());
  });
});
