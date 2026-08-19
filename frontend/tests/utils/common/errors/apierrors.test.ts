// #224 — **영문 원문이 화면에 나오지 않는다.**
//
// 401 이 나면 화면 한가운데에 axios 의 `Request failed with status code 401` 이 떴다.
// 두 경로가 있었다: 훅이 `error.message` 를 그대로 실은 것과, `getApiErrorMessage` 가
// FastAPI 의 영문 `detail`("Not authenticated")을 그대로 돌려준 것이다.
//
// 이 파일은 뒤쪽을 잠근다 — 401·5xx 는 서버가 무엇을 적어 보내든 우리 문구로 바꾼다.
// 그 밖의 상태에서 서버 문구를 계속 쓰는 것도 함께 잠근다 (과잉 억제 방지 — 우리 백엔드가
// 400·403 에 실어 보내는 한국어 안내가 사라지면 안 된다).

import { describe, expect, it } from "vitest";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";

function axiosLike(status: number, data: unknown) {
  return { message: `Request failed with status code ${status}`, response: { status, data } };
}

const HAS_LATIN_WORDS = /[A-Za-z]{3,}/;

describe("#224 화면에 나가는 API 에러 문구", () => {
  it("401 은 FastAPI 영문 detail 대신 다시 로그인하라는 우리 말로 나온다", () => {
    const message = getApiErrorMessage(axiosLike(401, { detail: "Not authenticated" }));

    expect(message).not.toMatch(HAS_LATIN_WORDS);
    expect(message).toContain("로그인");
  });

  // 실측 — 세션 없이 `/api/external/backend/watchlist` 를 부르면 이 본문이 온다.
  it("프록시가 실제로 보내는 401 본문(영문 error 필드)도 화면에 나가지 않는다", () => {
    const message = getApiErrorMessage(axiosLike(401, { error: "Authentication required" }));

    expect(message).not.toMatch(HAS_LATIN_WORDS);
    expect(message).toContain("로그인");
  });

  it("401 은 axios 원문도 내보내지 않는다", () => {
    expect(getApiErrorMessage(axiosLike(401, {}))).not.toContain("Request failed");
  });

  it("5xx 는 서버 원문 대신 다시 시도하라는 우리 말로 나온다", () => {
    for (const status of [500, 502, 503, 504]) {
      const message = getApiErrorMessage(axiosLike(status, { detail: "Internal Server Error" }));

      expect(message, `status ${status}`).not.toMatch(HAS_LATIN_WORDS);
      expect(message, `status ${status}`).toContain("다시 시도");
    }
  });

  it("400 은 서버가 준 한국어 안내를 그대로 쓴다", () => {
    expect(getApiErrorMessage(axiosLike(400, { detail: "종목 코드를 확인해 주세요" }))).toBe(
      "종목 코드를 확인해 주세요",
    );
  });

  it("403 은 우리 백엔드가 실은 사유를 그대로 쓴다", () => {
    const forbidden = axiosLike(403, {
      detail: [{ type: "forbidden", loc: ["auth"], msg: "이 워크스페이스에 접근할 수 없습니다" }],
    });

    expect(getApiErrorMessage(forbidden)).toBe("이 워크스페이스에 접근할 수 없습니다");
  });

  it("응답이 없는 네트워크 오류도 원문을 내지 않는다", () => {
    const message = getApiErrorMessage({ message: "Network Error" });

    expect(message).not.toMatch(HAS_LATIN_WORDS);
  });

  it("JS 내장 예외의 영문도 나가지 않는다", () => {
    expect(getApiErrorMessage(new TypeError("Failed to fetch"))).not.toMatch(HAS_LATIN_WORDS);
  });

  it("axios 가 만든 예외는 응답이 없어도 원문을 내지 않는다", () => {
    const axiosError = Object.assign(new Error("Network Error"), { isAxiosError: true });

    expect(getApiErrorMessage(axiosError)).not.toMatch(HAS_LATIN_WORDS);
  });

  // 이 레포가 직접 던진 문구는 이미 사람 말이다 — 일반 문구로 뭉개면 원인이 사라진다.
  it("우리가 쓴 한국어 예외 문구는 그대로 나온다", () => {
    expect(getApiErrorMessage(new Error("봇 목록을 불러오지 못했습니다"))).toBe("봇 목록을 불러오지 못했습니다");
  });
});
