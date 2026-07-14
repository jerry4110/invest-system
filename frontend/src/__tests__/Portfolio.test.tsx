// T-07 수용 기준(프론트): 보유현황 테이블·합계·기준시각 배지
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Portfolio from "../pages/Portfolio";

const data = {
  holdings: [{
    account: "미래에셋(파일)", name: "삼성전자", ticker: "005930", market: "KRX",
    qty: 100, avg_price: 70000, buy_amount: 7000000, cur_price: 75000,
    eval_amount: 7500000, pnl_amount: 500000, pnl_pct: 7.14, weight_pct: 100,
    as_of: new Date().toISOString(),
  }],
  totals: { buy_amount: 7000000, eval_amount: 7500000, pnl_amount: 500000,
            pnl_pct: 7.14, cash: 1000000, total_asset: 8500000 },
  as_of: new Date().toISOString(),
};

const byAccount = {
  accounts: [{ name: "주식계좌 9325", holdings: data.holdings.map((h) => ({ ...h, weight_in_account_pct: 100 })),
    cash: 1000000, cash_source: "manual", eval_amount: 7500000, buy_amount: 7000000,
    pnl_amount: 500000, pnl_pct: 7.14, total: 8500000, weight_pct: 100 }],
  totals: data.totals, as_of: data.as_of,
};

afterEach(cleanup);
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: true,
    json: async () => (String(url).includes("by-account") ? byAccount
      : String(url).includes("grouped") ? { by: "type", groups: [] }
      : String(url).includes("analysis") || String(url).includes("returns") ? { by_type: [], by_sector: [], returns: [] }
      : String(url).includes("trend") ? []
      : data),
  })) as unknown as typeof fetch);
});

describe("Portfolio", () => {
  it("계좌 카드·합계·기준시각을 표시한다 (2026-07-14 개선)", async () => {
    render(<Portfolio />);
    await waitFor(() => expect(screen.getByText(/주식계좌 9325/)).toBeTruthy());
    expect(screen.getByText("삼성전자")).toBeTruthy();            // 기본 첫 계좌 펼침
    expect(screen.getAllByText(/8,500,000원/).length).toBeGreaterThan(0);  // 계좌 합계
    expect(screen.getByText(/\(수동\)/)).toBeTruthy();            // 수동 예수금 표시
    expect(screen.getByText(/잔고 기준:/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "산업별" })).toBeTruthy();   // 분류 탭
  });
});
