// @vitest-environment node
//
// #441 F7 — 같은 낱말을 쓰는 세 자리가 서로 다른 말을 했다:
//
//   실험대 레일 → 포트폴리오 : 「포트폴리오는 아직 없습니다 — 봇 실행 엔진이 …」
//   /admin → 업무관리        : A포트·B포트·C포트 3건, 보유종목도 실제로 있다
//   터미널 사이드바 보유 탭   : 등록된 보유를 목록으로 낸다
//
// 레일 문구가 뜻하는 것은 「**봇 체결로 만들어진** 포지션」인데 적힌 낱말은 그냥 「포트폴리오」다.
// 방금 관리 화면에서 포트폴리오를 만든 사람이 실험대에서 「아직 없습니다」를 보면
// **저장이 안 된 것으로 읽는다.** #424 가 닫은 것과 같은 계층이다.
//
// 고칠 자리는 데이터가 아니라 **낱말**이다 — 이 자리가 기다리는 것이 무엇인지 말하고,
// 이미 있는 것은 어디서 보는지 가리킨다.
import { describe, expect, it } from "vitest";

import { RAIL_ITEMS } from "@/constants/shell";

const portfolio = RAIL_ITEMS.find((item) => item.id === "portfolio");

describe("레일의 포트폴리오가 무엇을 기다리는지 말한다", () => {
  it("그 자리가 있다 — 없으면 이 그물이 판정할 것이 없다", () => {
    expect(portfolio).toBeTruthy();
    expect((portfolio as { pending?: string }).pending).toBeTruthy();
  });

  it("「포트폴리오가 없다」고 단정하지 않는다 — 관리 화면에는 있다", () => {
    const pending = (portfolio as { pending: string }).pending;

    expect(pending).not.toMatch(/^포트폴리오는 아직 없습니다/);
  });

  it("기다리는 것이 봇 체결 포지션임을 말한다", () => {
    const pending = (portfolio as { pending: string }).pending;

    expect(pending).toMatch(/체결/);
    expect(pending).toMatch(/포지션|보유/);
  });

  it("이미 등록한 보유를 어디서 보는지 가리킨다", () => {
    const pending = (portfolio as { pending: string }).pending;

    expect(pending).toMatch(/시세|사이드바|관리/);
  });
});
