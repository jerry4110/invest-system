// T-23 수용 기준(프론트): 분석 실행 → Tier1 배지·지표 표 렌더링
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Analysis from "../pages/Analysis";

const result = {
  ticker: "005930", source: "DART", base_date: "2026-07-11",
  financials: [{ year: 2025, revenue: 333e12, operating_profit: 43e12, net_income: 45e12 }],
  evaluation: {
    items: [{ metric: "roe_pct", label: "ROE", value: 12.3, threshold: 15, direction: "min", status: "미충족" }],
    tier1: { verdict: "미충족", passed: [], failed: ["roe_pct"], unknown: ["fcf_streak"] },
  },
  as_of: "2026-07-12T10:00:00",
  disclaimer: "본 분석은 투자 참고자료이며 최종 판단은 투자자 본인의 책임입니다.",
};

afterEach(cleanup);
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => result })) as unknown as typeof fetch);
});

describe("Analysis", () => {
  it("분석 실행 시 Tier1 배지·지표·고지문을 표시한다", async () => {
    render(<Analysis />);
    fireEvent.change(screen.getByPlaceholderText(/종목코드/), { target: { value: "005930" } });
    fireEvent.click(screen.getByRole("button", { name: /분석 실행/ }));
    await waitFor(() => expect(screen.getByText(/Tier 1 미충족/)).toBeTruthy());
    expect(screen.getByText("ROE")).toBeTruthy();
    expect(screen.getByText(/투자 참고자료/)).toBeTruthy();   // FR-04-36
    expect(screen.getByText(/2026-07-11/)).toBeTruthy();      // T-1 기준일
  });
});
