// #355 — **권한 행을 만드는 자리의 전수 대조 그물.**
//
// 이 이슈의 클래스는 「계정을 만드는 경로가 셋인데 각자 다른 기본 권한 규칙을 들고 있었다」는
// 것이다 — 가입은 운영자, 수정은 게스트, 생성은 아무것도 안 줬다. 규칙을 `lib/auth/defaultAuthor.ts`
// 하나로 모았지만, 새 경로가 생기며 역할 상수를 직접 고르면 같은 갈림이 다시 생긴다.
//
// 그래서 이 파일은 소스를 **훑어서** ① 계정을 만드는 라우트(`auth.api.signUpEmail`)와 ② 권한 행을
// 만드는 라우트(`authorMember.create(`)를 찾고, 찾은 것 전부가 아래 표에 있으며 표에 적힌 대로
// 규칙 함수를 부르는지(또는 명시적 부여라 규칙 밖인지) 대조한다. 표에 없는 경로가 나오면 실패하고,
// 표에 있는데 소스에서 사라져도 실패한다. 규칙을 따르는 경로가 역할 상수(`GUEST_AUTHOR_ID`·
// `SIGNUP_AUTHOR_ID`)를 직접 들면 실패한다 — 그게 곧 「경로가 자기 규칙을 갖기 시작했다」는 신호다.
//
// **fail-closed**: 훑어서 찾은 경로가 0건이면 실패한다. 검사한 파일 수·경로 수를 출력에 남긴다.
// `343-account-creation-paths.test.ts` 와 같은 골격이다 — 그쪽은 「문지기가 있는가」, 여기는
// 「기본 권한 규칙을 따르는가」를 본다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

/** 계정을 만드는 호출. 이 문자열이 있는 라우트는 만든 계정에 기본 권한을 붙여야 한다. */
const CREATE_ACCOUNT_CALL = "auth.api.signUpEmail";
/** 권한 행을 직접 만드는 호출. 규칙 함수 밖에서 이것을 쓰는 라우트는 명시적 부여여야 한다. */
const CREATE_AUTHOR_MEMBER_CALL = "authorMember.create(";
/** 규칙 함수 — 기본 권한을 붙이는 라우트는 이 호출 형태를 가져야 한다 (import 만으로는 통과하지 않는다). */
const RULE_CALL = "await grantDefaultAuthor(";
/** 규칙을 따르는 라우트가 직접 들면 안 되는 역할 상수. */
const ROLE_CONSTANTS = ["GUEST_AUTHOR_ID", "SIGNUP_AUTHOR_ID"];

/**
 * 권한 행을 만드는 자리와 그 판정 — **경로마다 하나씩**.
 * - `rule`: 기본 권한이라 `grantDefaultAuthor` 를 불러야 하고 역할 상수를 직접 들지 않는다.
 * - `explicit`: 관리자가 골라서 주는 자리라 규칙 밖이다 — 대신 본문에서 고른 값을 그대로 쓴다.
 */
const AUTHOR_GRANT_PATHS: ReadonlyArray<{ file: string; kind: "rule" | "explicit"; why: string }> = [
  {
    file: "app/api/common/signup/route.ts",
    kind: "rule",
    why: "가입 — 개인 워크스페이스면 주인(운영자), 도메인 매핑이면 손님(게스트), OEM 은 승인 시",
  },
  {
    file: "app/api/common/system/adminuser/route.ts",
    kind: "rule",
    why: "관리자 생성 — 예전엔 아무것도 안 줘서 제품 화면이 통째로 닫혔다 (#355 의 원래 증상)",
  },
  {
    file: "app/api/common/system/adminuser/[email]/route.ts",
    kind: "rule",
    why: "관리자 수정 — 워크스페이스 배정·승인 전환 때 붙인다",
  },
  {
    file: "app/api/common/system/author/[author_id]/user/route.ts",
    kind: "explicit",
    why: "권한관리·소속 권한 탭의 + — 관리자가 고른 권한을 그대로 준다 (기본값이 아니다)",
  },
];

function listRouteFiles(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) listRouteFiles(full, out);
    else if (entry.name === "route.ts") out.push(path.relative(FRONTEND_ROOT, full));
  }
  return out;
}

const read = (rel: string) => fs.readFileSync(path.join(FRONTEND_ROOT, rel), "utf8");

const routeFiles = listRouteFiles(path.join(FRONTEND_ROOT, "app", "api"));
const grantRoutes = routeFiles
  .filter((rel) => {
    const src = read(rel);
    return src.includes(CREATE_ACCOUNT_CALL) || src.includes(CREATE_AUTHOR_MEMBER_CALL) || src.includes(RULE_CALL);
  })
  .sort();

describe("#355 권한 행을 만드는 경로 전수", () => {
  it(`라우트를 훑어 권한 부여 경로를 찾았다 (route.ts ${routeFiles.length}개 중 ${grantRoutes.length}개)`, () => {
    // 0건은 통과가 아니다 — 훑기가 죽었거나 호출 형태가 바뀐 것이다.
    expect(routeFiles.length).toBeGreaterThan(0);
    expect(grantRoutes.length).toBeGreaterThan(0);
    console.info(
      `[#355] route.ts ${routeFiles.length}개를 훑어 권한 부여 경로 ${grantRoutes.length}개를 검사했다: ${grantRoutes.join(", ")}`,
    );
  });

  it("찾은 경로와 판정표가 정확히 일치한다 (표에 없는 새 경로도, 사라진 경로도 실패)", () => {
    expect(grantRoutes).toEqual([...AUTHOR_GRANT_PATHS.map((p) => p.file)].sort());
  });

  it.each(AUTHOR_GRANT_PATHS.filter((p) => p.kind === "rule"))(
    "$file 은 규칙 함수를 부르고 역할 상수를 직접 들지 않는다 — $why",
    ({ file }) => {
      const src = read(file);
      expect(src, `${file} 이 grantDefaultAuthor 를 부르지 않는다 — 자기 규칙을 갖기 시작했다`).toContain(RULE_CALL);
      expect(src, `${file} 이 권한 행을 규칙 밖에서 직접 만든다`).not.toContain(CREATE_AUTHOR_MEMBER_CALL);
      for (const constant of ROLE_CONSTANTS) {
        expect(src, `${file} 이 ${constant} 를 직접 든다 — 기본 권한은 defaultAuthor.ts 만 고른다`).not.toContain(
          constant,
        );
      }
    },
  );

  it.each(AUTHOR_GRANT_PATHS.filter((p) => p.kind === "explicit"))(
    "$file 은 명시적 부여라 규칙 함수를 부르지 않는다 — $why",
    ({ file }) => {
      const src = read(file);
      expect(src).toContain(CREATE_AUTHOR_MEMBER_CALL);
      expect(src, `${file} 이 기본 권한 규칙을 부른다 — 관리자가 고른 값이 규칙에 덮인다`).not.toContain(RULE_CALL);
    },
  );

  it("규칙 함수 자신이 역할 상수를 고르는 유일한 자리다", () => {
    const rule = read("lib/auth/defaultAuthor.ts");
    for (const constant of ROLE_CONSTANTS) expect(rule).toContain(constant);
    expect(rule).toContain("export async function grantDefaultAuthor(");
  });
});
