// #229 — **로그인 화면의 홍보 문구가 제품 화면 안으로 새지 않는다.**
//
// 이슈는 「시세」 레일을 눌렀더니 패널에 「전략은 파일로 남는다」(로그인 카피)가 있었다고
// 적었다. 재현하지 못했고 원인도 찾았다 — 이슈가 스스로 의심한 대로 **관측 방식의 artifact**
// 였다: 로그인 화면에 그 문구를 담은 폭 419px 요소(`<dl>`)가 있어, 「폭 300~420px 요소의 첫
// 텍스트」라는 선택자가 그것을 집었다.
//
// 결함은 없었지만 **불변식은 지킬 값이 있다.** 홍보 카피는 로그인 화면의 것이고, 제품 셸
// 안에서 보이면 그때는 진짜 결함이다. 「오늘은 안 샌다」를 관측이 아니라 **검사된 사실**로
// 바꾼다.
//
// **검증 경계** — 정적 import 그래프를 본다. 런타임에 문자열이 어떻게 조합되는지는 보지 않는다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

/** 로그인 화면만 쓰는 것 — 제품 셸 어디에서도 나오면 안 된다. */
const LOGIN_ONLY = {
  component: "components/features/Common/Auth/Login",
  copy: "전략은 파일로 남는다",
};

/** 제품 셸의 뿌리들. 로그인은 `app/page.tsx`(루트)에 있고 이 아래에는 없다. */
const PRODUCT_TREES = [
  "app/(main)",
  "app/admin",
  "components/features/Terminal",
  "components/features/Bench",
  "components/shared/Layout",
];

function walk(dir: string): string[] {
  const full = path.join(FRONTEND_ROOT, dir);
  const entries = fs.existsSync(full) ? fs.readdirSync(full, { withFileTypes: true }) : [];
  return entries.flatMap((entry) => {
    const rel = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(rel);
    return /\.tsx?$/.test(entry.name) ? [rel] : [];
  });
}

describe("#229 로그인 카피는 로그인 화면에 머문다", () => {
  it("훑은 파일이 0건이면 실패한다 — 경로가 바뀌면 조용히 초록이 되지 않게", () => {
    const files = PRODUCT_TREES.flatMap(walk);

    expect(files.length).toBeGreaterThan(30);
  });

  it("제품 셸이 로그인 컴포넌트를 가져오지 않는다", () => {
    const offenders = PRODUCT_TREES.flatMap(walk).filter((file) =>
      fs.readFileSync(path.join(FRONTEND_ROOT, file), "utf8").includes(LOGIN_ONLY.component),
    );

    expect(offenders).toEqual([]);
  });

  it("홍보 문구가 제품 셸 안에 적혀 있지 않다", () => {
    const offenders = PRODUCT_TREES.flatMap(walk).filter((file) =>
      fs.readFileSync(path.join(FRONTEND_ROOT, file), "utf8").includes(LOGIN_ONLY.copy),
    );

    expect(offenders).toEqual([]);
  });

  it("그 문구가 어딘가에는 있다 — 사라진 문구를 지키느라 늘 초록이 되지 않게", () => {
    const login = fs.readFileSync(path.join(FRONTEND_ROOT, `${LOGIN_ONLY.component}.tsx`), "utf8");

    expect(login).toContain(LOGIN_ONLY.copy);
  });
});
