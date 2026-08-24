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

// 실제 설정 이름을 적지 않는다 — 그 이름이 나와도 되는 자리는 정의처·로더·예시뿐이고
// `backend-service/scripts/verify_data_key_env_boundary.py` 가 그 밖의 코드를 잡는다. 백엔드
// 테스트는 로더의 표에서 이름을 꺼내 쓰지만 그 표는 파이썬에만 있고, 이 컴포넌트는 이름의
// 내용을 보지 않으므로 여기서는 지어낸 한 쌍으로 충분하다.
const ROW: DataKeyStatus = {
  source: "fixture-source",
  setting: "FIXTURE_SETTING_NOT_A_REAL_KEY",
  filled: false,
  secret: true,
  guidance: "발급처에서 받은 값을 넣습니다",
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
