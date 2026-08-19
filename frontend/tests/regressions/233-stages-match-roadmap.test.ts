// #233 — **화면이 말하는 단계가 ROADMAP.md 와 갈라지지 않는다.**
//
// 제품이 「굴리는 자리」라고 말하는데 굴릴 길이 없으면, 받은 사람은 설정 어딘가에 실계좌
// 연결이 있으리라 여기고 찾다가 없다는 것을 알게 된다. 그래서 남은 단계를 화면이 스스로
// 말하게 했다 — 이 레포의 「경로를 보여준다」 원칙을 제품 전체 단계에 적용한 것이다.
//
// 화면에 옮겨 적은 것은 **갈라진다.** 로드맵이 바뀌었는데 화면이 옛 순서를 말하면, 없느니만
// 못한 로드맵이 된다. 그래서 구간 이름과 「지금은 안 하는 것」을 문서와 맞댄다.
//
// **검증 경계** — 문서의 절 이름과 항목의 **존재**를 본다. 문장까지 같은지는 보지 않는다
// (화면은 한 눈에 낼 만큼만 옮기므로 문장은 달라도 된다).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { PRODUCT_STAGES, ROADMAP_URL, STAGE_LABELS } from "@/constants/stages";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const ROADMAP = fs.readFileSync(path.join(REPO_ROOT, "ROADMAP.md"), "utf8");

describe("#233 화면의 단계가 로드맵과 같은 것을 말한다", () => {
  it("로드맵을 실제로 읽었다 — 파일이 비면 아래 대조가 무의미하다", () => {
    expect(ROADMAP.length).toBeGreaterThan(500);
  });

  it("구간 이름이 문서의 절 이름과 같다", () => {
    expect(ROADMAP).toContain("## 지금");
    expect(ROADMAP).toContain("## 다음");
    expect(ROADMAP).toContain("## 나중");
    expect(ROADMAP).toContain("## 하지 않는 것 (지금은)");

    expect(Object.values(STAGE_LABELS)).toEqual(["지금", "다음", "나중", "지금은 안 합니다"]);
  });

  it("「지금은 안 합니다」로 적은 것이 문서의 그 절에 실제로 있다", () => {
    const notNow = PRODUCT_STAGES.filter((stage) => stage.state === "not-now");
    const section = ROADMAP.slice(ROADMAP.indexOf("## 하지 않는 것 (지금은)"));

    expect(notNow.length).toBeGreaterThan(0);
    for (const stage of notNow) {
      // 화면은 「검증 없는 실주문 자동화」, 문서는 「실주문 자동화」 — 핵심어로 맞댄다.
      expect(section, `${stage.label} 이 문서의 그 절에 없다`).toContain("실주문 자동화");
    }
  });

  it("실주문은 「안 함」이 아니라 「나중」이다 — 리드 결정을 화면이 뒤집지 않는다", () => {
    const live = PRODUCT_STAGES.find((stage) => stage.id === "live");

    expect(live?.state).toBe("later");
    expect(ROADMAP.slice(ROADMAP.indexOf("## 나중"))).toContain("실주문 승격");
  });

  it("지금 되는 것이 하나 이상 있다 — 전부 미래면 화면이 거짓말이다", () => {
    expect(PRODUCT_STAGES.filter((stage) => stage.state === "now").length).toBeGreaterThan(0);
  });

  it("로드맵으로 가는 길이 그 파일을 가리킨다", () => {
    expect(ROADMAP_URL).toMatch(/ROADMAP\.md$/);
  });
});
