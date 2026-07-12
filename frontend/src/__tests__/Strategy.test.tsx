// T-09 수용 기준(프론트): 페르소나 선택·지침 편집 렌더링
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Strategy from "../pages/Strategy";

const data = {
  persona: "growth", guideline_text: "성장주 기본 지침", version: 3,
  updated_at: "2026-07-12T10:00:00",
  files: [{ id: 1, filename: "지침.md", uploaded_at: "2026-07-12T09:00:00" }],
  allocation: { stock_pct: 70 },
};

afterEach(cleanup);
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => data })) as unknown as typeof fetch);
});

describe("Strategy", () => {
  it("페르소나 3종·현재 지침·버전·업로드 파일을 표시한다", async () => {
    render(<Strategy />);
    await waitFor(() => expect(screen.getByText(/성장주 투자자/)).toBeTruthy());
    expect(screen.getByText(/가치투자자/)).toBeTruthy();
    expect(screen.getByText(/단기 트레이더/)).toBeTruthy();
    expect(screen.getByDisplayValue("성장주 기본 지침")).toBeTruthy();
    expect(screen.getByText(/지침 v3/)).toBeTruthy();       // FR-01-14 버전
    expect(screen.getByText(/지침\.md/)).toBeTruthy();       // FR-01-12
  });
});
