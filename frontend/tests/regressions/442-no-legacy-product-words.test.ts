// @vitest-environment node
//
// #442 F24 — 투자 지휘소 화면에 **옛 제품의 낱말**이 사용자에게 그대로 보였다:
//
//   SchedulerMemberGrid.tsx:  { dataField: "git_id", caption: "Git ID" }
//
// 같은 필드를 형제 화면(`SchedulerDetailForm.tsx`)은 이미 「계좌주 ID」라고 부른다. 한쪽만
// 옛 이름으로 남아 있었다 — 이 레포는 그 낱말을 쓸 이유가 없다(개인 투자 지휘소다).
//
// **인스턴스가 아니라 클래스를 잡는다.** 한 자리를 고쳐도 다음 화면이 같은 낱말을 다시 쓰면
// 되돌아온다. 사용자에게 보이는 격자 머리글(`caption`)을 전수로 훑는다.
//
// 새 CI 잡을 만들지 않는다 — 이 레포는 「규약 하나에 검사 잡 하나」로 값을 치른 이력이 있다
// (루트 `CLAUDE.md`). `npm test` 를 그대로 타는 그물 하나면 된다.
import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOTS = ["components", "app"];

/** 옛 제품에서 넘어온, 이 제품의 사용자가 모르는 낱말. */
const LEGACY_WORDS = [/\bGit\s?ID\b/i, /\bgit\s?계정/i, /\b리포지토리\b/, /\b커밋\b/];

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (path.endsWith(".tsx") || path.endsWith(".ts")) out.push(path);
  }
  return out;
}

function captions(): { file: string; text: string }[] {
  const found: { file: string; text: string }[] = [];
  for (const root of ROOTS) {
    for (const file of walk(root)) {
      const source = readFileSync(file, "utf8");
      for (const match of source.matchAll(/caption:\s*"([^"]+)"/g)) {
        found.push({ file, text: match[1] });
      }
    }
  }
  return found;
}

describe("사용자 화면에 옛 제품의 낱말이 없다", () => {
  const all = captions();

  it("훑을 대상이 있다 — 0건이면 그물이 죽은 것이다", () => {
    // fail-closed: 격자 머리글 표기가 바뀌어 정규식이 안 걸리면 여기서 시끄럽게 실패한다.
    expect(all.length).toBeGreaterThan(30);
  });

  it("격자 머리글에 옛 낱말이 없다", () => {
    const offenders = all.filter((c) => LEGACY_WORDS.some((w) => w.test(c.text)));

    expect(offenders.map((o) => `${o.file}: ${o.text}`)).toEqual([]);
  });
});
