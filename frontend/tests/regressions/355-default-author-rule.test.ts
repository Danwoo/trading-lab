// #355 — 계정을 만들거나 승인할 때 붙는 기본 권한의 **규칙 자체**를 잰다.
//
// 규칙은 `lib/auth/defaultAuthor.ts` 의 `defaultAuthorIdFor` 하나다(가입·관리자 생성·관리자 수정이
// 전부 이것을 부른다 — 그 사실은 `355-default-author-paths.test.ts` 가 소스를 훑어 잠근다). 이
// 파일은 그 함수가 리드 결정(2026-08-23 가입=운영자 · 2026-08-24 공용 워크스페이스=게스트)을
// 그대로 내는지 **자리마다 하나씩** 판정표로 대조한다.
//
// 값을 상수 이름으로만 적지 않고 `WRITE_AUTHOR_IDS` 로도 판정하는 이유(#341 과 같다): 지키는 것은
// 문자열이 아니라 「주인은 쓰기가 열리고, 손님은 안 열린다」는 성질이다.
//
// **fail-closed**: 판정표가 비면 실패한다. 검사한 자리 수를 출력에 남긴다.

import { describe, expect, it } from "vitest";
import { defaultAuthorIdFor, type AccountPlacement } from "@/lib/auth/defaultAuthor";
import { GUEST_AUTHOR_ID, SIGNUP_AUTHOR_ID } from "@/constants/protected";
import { WRITE_AUTHOR_IDS } from "@/constants/writeAccess";

/** 자리 → 기대 권한. `null` 은 「아직 주지 않는다」. */
const PLACEMENTS: ReadonlyArray<{ placement: AccountPlacement; expected: string | null; why: string }> = [
  {
    placement: { workspace: "personal", approved: true },
    expected: SIGNUP_AUTHOR_ID,
    why: "자기 개인 워크스페이스의 주인 — 가입 경로 (리드 결정 2026-08-23)",
  },
  {
    placement: { workspace: "shared", approved: true },
    expected: GUEST_AUTHOR_ID,
    why: "남의 공용 워크스페이스에 들어간 계정 — 도메인 매핑 가입·관리자 생성·관리자 배정 (보완 2026-08-24)",
  },
  {
    placement: { workspace: "none", approved: true },
    expected: GUEST_AUTHOR_ID,
    why: "워크스페이스가 없는 계정 — 주인이 아닌 것은 같다",
  },
  {
    placement: { workspace: "personal", approved: false },
    expected: null,
    why: "승인 전에는 아무것도 주지 않는다 — 승인이 붙인다",
  },
  {
    placement: { workspace: "shared", approved: false },
    expected: null,
    why: "OEM 가입·관리자가 「대기」로 만든 계정",
  },
  {
    placement: { workspace: "none", approved: false },
    expected: null,
    why: "워크스페이스도 승인도 없는 계정",
  },
];

describe("#355 기본 권한 규칙 — 자리마다 하나씩", () => {
  it(`판정표가 비어 있지 않다 (${PLACEMENTS.length}자리)`, () => {
    expect(PLACEMENTS.length).toBeGreaterThan(0);
    // 세 축(workspace 3종 × approved 2종)을 빠짐없이 덮는다 — 한 칸이 빠지면 그 칸의 회귀는 못 본다.
    const keys = new Set(PLACEMENTS.map((p) => `${p.placement.workspace}/${p.placement.approved}`));
    expect(keys.size).toBe(6);
    console.info(`[#355] 기본 권한 규칙 ${PLACEMENTS.length}자리를 검사했다`);
  });

  it.each(PLACEMENTS)(
    "$placement.workspace · approved=$placement.approved → $expected — $why",
    ({ placement, expected }) => {
      expect(defaultAuthorIdFor(placement)).toBe(expected);
    },
  );

  it("주인에게는 쓰기가 열리고, 손님에게는 안 열린다 — 이름이 아니라 성질", () => {
    expect(WRITE_AUTHOR_IDS.length, "쓰기가 열리는 역할이 0건이다 — 대조할 것이 없다").toBeGreaterThan(0);
    const owner = defaultAuthorIdFor({ workspace: "personal", approved: true });
    const guest = defaultAuthorIdFor({ workspace: "shared", approved: true });
    expect(owner, "주인이 받은 역할로는 저장·실행이 안 열린다 — #341 의 원래 증상").toBeOneOf([...WRITE_AUTHOR_IDS]);
    expect(guest, "손님이 쓰기 역할을 받았다 — 초대 없이 남의 워크스페이스가 열린다").not.toBeOneOf([
      ...WRITE_AUTHOR_IDS,
    ]);
  });
});
