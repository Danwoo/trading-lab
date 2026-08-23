// @vitest-environment jsdom
//
// 이슈 #344 — `.env` 를 고쳐 쓰는 자리는 시스템관리자만 통과한다. 판정의 정본은 백엔드지만,
// 화면이 「누를 때마다 403 이 되는 버튼」을 계속 내밀면 사용자는 그것을 고장으로 읽는다.
// 이 그물은 **상태는 그대로 보이고 넣는 자리만 사라지는지**를 잡는다 — 감추기와 구별한다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { DataKeyRow } from "@/components/features/Settings/DataKeyRow";
import type { DataKeyStatus } from "@/services/dataKey/dataKeyService";

afterEach(() => cleanup());

const ROW: DataKeyStatus = {
  source: "alpaca",
  setting: "MARKET_DATA_ALPACA_KEY",
  filled: false,
  secret: true,
  guidance: "Alpaca 계정(paper) → API Keys",
};

describe("DataKeyRow — 넣는 자리는 시스템관리자만 (#344)", () => {
  it("canWrite=false 면 입력칸도 버튼도 없다 — 403 이 될 행동을 권하지 않는다", () => {
    render(<DataKeyRow row={ROW} canWrite={false} onSaved={vi.fn()} />);

    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByLabelText(`${ROW.source} ${ROW.setting}`)).toBeNull();
    expect(screen.queryByRole("button", { name: "저장" })).toBeNull();
    expect(screen.queryByRole("button", { name: "연결 확인" })).toBeNull();
  });

  it("canWrite=false 여도 상태·안내는 그대로 읽힌다 — 감추는 것이 아니다", () => {
    render(<DataKeyRow row={ROW} canWrite={false} onSaved={vi.fn()} />);

    expect(screen.getByText(ROW.source)).toBeTruthy();
    expect(screen.getByText(ROW.setting)).toBeTruthy();
    expect(screen.getByText("없음")).toBeTruthy();
    expect(screen.getByText(ROW.guidance!)).toBeTruthy();
  });

  it("canWrite=true 면 넣는 자리가 있다 — 과하게 조여 화면을 죽이지 않았다", () => {
    render(<DataKeyRow row={ROW} canWrite={true} onSaved={vi.fn()} />);

    expect(screen.getByLabelText(`${ROW.source} ${ROW.setting}`)).toBeTruthy();
    expect(screen.getByRole("button", { name: "저장" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "연결 확인" })).toBeTruthy();
  });
});
