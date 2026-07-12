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

afterEach(cleanup);
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => data })) as unknown as typeof fetch);
});

describe("Portfolio", () => {
  it("보유 종목·합계·기준시각을 표시한다", async () => {
    render(<Portfolio />);
    await waitFor(() => expect(screen.getByText("삼성전자")).toBeTruthy());
    expect(screen.getByText("8,500,000원")).toBeTruthy();   // 총자산 = 평가 + 예수금
    expect(screen.getByText(/잔고 기준:/)).toBeTruthy();     // as_of 배지 (NFR-04)
  });
});
