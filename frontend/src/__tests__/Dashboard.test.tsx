// T-04 수용 기준(프론트): 지표 카드 렌더링·갱신 버튼 (Codex 리뷰 Major 반영 — Vitest 도입)
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import Dashboard from "../pages/Dashboard";

const indicator = (code: string, name: string) => ({
  code, name, category: "index", value: 1234.56, change_pct: -1.23,
  date: "2026-07-12", as_of: "2026-07-12T08:00:00", spark: [1, 2, 3],
});

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      url.includes("indicators")
        ? [indicator("KOSPI", "코스피"), indicator("BTC", "비트코인")]
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

  it("업데이트 버튼이 있다 (FR-02-22)", async () => {
    render(<Dashboard />);
    await waitFor(() => expect(screen.getByRole("button", { name: /업데이트/ })).toBeTruthy());
  });
});
