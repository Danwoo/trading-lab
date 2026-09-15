// @vitest-environment jsdom
//
// #445 B-16·F30 — **「설정됨」과 「유효함」은 다르다.**
//
// 저장된 키는 값을 다시 칠 수 없다(비밀이라 화면에 안 남는다). 그런데 「연결 확인」이
// `value.trim().length > 0` 으로 잠겨 있어, 이미 저장된 키가 실제로 통하는지 **알 길이 없었다.**
// 화면은 「설정됨」이라고만 말하고 유효한지는 아무도 답하지 못했다 — Cycle 6 의 봇 서비스와 같은 병이다.
//
// 빈 값으로 확인을 부르면 서버가 저장된 것을 쓴다(`probe_key` 의 fallback). 값을 쳤으면
// 그 값이 이긴다 — 저장 전 확인은 종전 그대로다.
// 설정 이름은 **가짜**다 — 실제 이름을 쓰면 `verify_data_key_env_boundary.py` 가 잡는다
// (키를 읽는 자리는 `services/data_key/` 하나라는 규약, 리드 결정 2026-08-07).
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/services/dataKey/dataKeyService", () => ({
  probeDataKey: vi.fn(),
  saveDataKey: vi.fn(),
}));

const { probeDataKey } = await import("@/services/dataKey/dataKeyService");
const { DataKeyRow } = await import("@/components/features/Settings/DataKeyRow");

const row = (filled: boolean) =>
  ({
    source: "data_go_kr",
    setting: "FIXTURE_SETTING_NOT_A_REAL_KEY",
    filled,
    secret: true,
    guidance: null,
  }) as never;

const draw = (filled: boolean) => render(<DataKeyRow row={row(filled)} canWrite onSaved={vi.fn()} />);

describe("저장된 키도 확인할 수 있다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("설정된 키는 아무것도 안 쳐도 확인 버튼이 열려 있다", () => {
    draw(true);
    expect(screen.getByRole("button", { name: "저장된 키 확인" }).hasAttribute("disabled")).toBe(false);
  });

  it("설정 안 된 키는 종전대로 잠겨 있다 — 확인할 것이 없다", () => {
    draw(false);
    expect(screen.getByRole("button", { name: /확인/ }).hasAttribute("disabled")).toBe(true);
  });

  it("빈 값으로 부른다 — 서버가 저장된 것을 쓰라는 뜻이다", async () => {
    vi.mocked(probeDataKey).mockResolvedValue({ ok: true, checked: true, detail: "통했습니다." } as never);
    draw(true);

    await userEvent.setup().click(screen.getByRole("button", { name: "저장된 키 확인" }));

    await waitFor(() => expect(vi.mocked(probeDataKey)).toHaveBeenCalledTimes(1));
    expect(vi.mocked(probeDataKey).mock.calls[0][1]).toBe("");
  });

  it("값을 치면 그 값으로 확인한다 — 저장 전 확인은 종전 그대로", async () => {
    vi.mocked(probeDataKey).mockResolvedValue({ ok: false, checked: true, detail: "거절됐습니다." } as never);
    draw(true);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("data_go_kr FIXTURE_SETTING_NOT_A_REAL_KEY"), "NEW-KEY");
    await user.click(screen.getByRole("button", { name: "연결 확인" }));

    await waitFor(() => expect(vi.mocked(probeDataKey)).toHaveBeenCalledTimes(1));
    expect(vi.mocked(probeDataKey).mock.calls[0][1]).toBe("NEW-KEY");
  });

  it("확인 결과를 그대로 보여 준다 — 사유를 삼키지 않는다", async () => {
    vi.mocked(probeDataKey).mockResolvedValue({ ok: false, checked: true, detail: "키가 거절됐습니다." } as never);
    draw(true);

    await userEvent.setup().click(screen.getByRole("button", { name: "저장된 키 확인" }));

    expect(await screen.findByText("키가 거절됐습니다.")).toBeTruthy();
  });
});
