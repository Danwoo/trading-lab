// @vitest-environment jsdom
//
// #424 ① — **가입 다이얼로그가 코드가 실제로 간 곳을 말한다.**
//
// 실측(이슈 본문): `EMAIL_HOST` 를 비운 기본 설치에서 인증을 요청하면 다이얼로그가
// 「[이메일] 로 인증 코드를 발송 하였습니다」라고 말한다. 실제로는 메일이 나가지 않고
// 코드는 서버 콘솔에만 찍힌다 — 처음 설치한 사람은 오지 않는 메일을 기다리다 멈춘다.
//
// 여기서 잡는 것 둘:
//   ㉠ 콘솔 모드면 **서버 콘솔을 보라고** 말한다. 「발송」이라고 말하지 않는다
//   ㉡ 메일 모드면 **종전 문구 그대로** — 이 수정이 정상 설치의 말을 바꾸지 않는다
//
// **검증 경계** — 서버 응답은 스텁이다(`delivery` 를 어떤 조건에서 서버가 정하는지는
// `424-otp-delivery-mode.test.ts` 가 본다). 여기서 보는 것은 화면이 그 값을 읽어 무엇을
// 말하는가뿐이다.

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Signup } from "@/components/features/Common/Auth/Signup";

const sendEmail = vi.hoisted(() => vi.fn());
const checkEmail = vi.hoisted(() => vi.fn(async () => ({ result: false })));

vi.mock("@/services/common/authService", () => ({
  sendEmail,
  checkEmail,
  verifySignupOTP: vi.fn(),
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

// 약관 팝업은 이 그물이 보는 대상이 아니고, 배럴을 거쳐 env 까지 끌고 온다.
vi.mock("@/components/features/Common/Policy/PolicyPopup", () => ({ default: () => null }));

const shown = vi.hoisted(() => [] as { title: string; content: ReactNode }[]);
vi.mock("@/stores/shared/messageStore", () => ({
  showMessage: (title: string, content: ReactNode) => {
    shown.push({ title, content });
    return Promise.resolve(true);
  },
}));

/** 마지막 다이얼로그의 본문 텍스트. */
function lastDialogText(): string {
  const last = shown.at(-1);
  if (!last) throw new Error("다이얼로그가 뜨지 않았다");
  const { container } = render(<div>{last.content}</div>);
  return container.textContent ?? "";
}

async function requestCode(delivery: "console" | "email") {
  sendEmail.mockResolvedValue({ message: "Email sent successfully", delivery });
  const user = userEvent.setup();
  render(<Signup />);
  await user.type(screen.getByLabelText("이메일 주소"), "someone@example.com");
  await user.click(screen.getByRole("button", { name: "인증요청" }));
}

describe("#424 ① 다이얼로그가 코드가 간 곳을 말한다", () => {
  beforeEach(() => {
    shown.length = 0;
    sendEmail.mockReset();
    checkEmail.mockReset();
    checkEmail.mockResolvedValue({ result: false });
  });

  afterEach(cleanup);

  it("콘솔 모드 — 서버 콘솔을 보라고 말한다", async () => {
    await requestCode("console");

    const text = lastDialogText();
    expect(text).toContain("서버 콘솔");
    expect(text).not.toContain("발송");
  });

  it("메일 모드 — 종전 문구 그대로 발송을 말한다", async () => {
    await requestCode("email");

    const text = lastDialogText();
    expect(text).toContain("발송");
    expect(text).toContain("someone@example.com");
    expect(text).not.toContain("서버 콘솔");
  });
});
