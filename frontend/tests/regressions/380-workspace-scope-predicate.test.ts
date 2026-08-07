// #380 정적 그물 — 워크스페이스 소속 판정이 다시 두 벌로 갈리는 것을 막는다.
//
// 소속의 사실 원천은 `workspaceScopedUserWhere`(스칼라 `tn_user.workspace_id` ∪ 다대다
// `tn_workspace_member`) 하나다. 라우트마다 `session.user.workspaceId` 를 스칼라 컬럼과 직접
// 비교하면 같은 사용자가 어떤 화면에는 보이고 어떤 화면에는 안 보이는 상태가 되고, 다음에
// 한쪽만 고치는 사고가 난다 — #241 오더2 가 통일했는데 다섯 자리가 뒤늦게 발견됐다(#380).
//
// 이 파일은 **소스 텍스트**를 본다. 짝인 `380-workspace-scope-predicate.dbtest.ts` 는 같은 축을
// 실제 DB 로 확인한다 — 정적 검사는 새 라우트가 옛 형태로 들어오는 것을 값싸게 막고, 동적 검사는
// 술어가 실제로 두 축을 다 잡는지 본다. 둘 중 하나만으로는 부족하다:
// 정적 검사는 우회 형태(중간 변수 등)를 못 잡고, 동적 검사는 아직 없는 라우트를 못 본다.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));
const SCAN_ROOTS = [path.join(FRONTEND_ROOT, "app/api"), path.join(FRONTEND_ROOT, "lib/auth")];

/**
 * 소속 판정을 `session.user.workspaceId` 와 스칼라 컬럼의 직접 비교로 하는 형태.
 * - `workspace_id: session.user.workspaceId` — 조회 where 에 스칼라만 넣는 형태
 * - `workspace_id !== session.user.workspaceId` / `===` — 가드에서 손으로 비교하는 형태
 * 워크스페이스 **자신**을 고르는 자리(`id: session.user.workspaceId`, workspace/options)는
 * 사용자 소속 판정이 아니므로 컬럼명으로 걸러진다.
 */
const SCALAR_ONLY_PATTERNS = [
  /workspace_id\s*:\s*session\.user\.workspaceId/,
  /workspace_id\s*[!=]==\s*session\.user\.workspaceId/,
  /session\.user\.workspaceId\s*[!=]==\s*\w+(\?)?\.workspace_id/,
];

const CANONICAL_PREDICATE = "workspaceScopedUserWhere";

/**
 * 이 술어를 실제로 쓰는 파일 수. 술어가 사라지거나(이름 변경·삭제) 호출부가 줄면 여기서 드러난다 —
 * "위반 0건"만 보는 그물은 술어를 통째로 걷어내도 초록이다. 라우트를 더하며 이 수가 바뀌면
 * 값을 갱신하되, 줄어드는 방향이면 그 자리가 스칼라 단독으로 돌아간 것은 아닌지 먼저 확인한다.
 */
const EXPECTED_CANONICAL_CALLERS = 5;

function listSourceFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listSourceFiles(full));
    else if (entry.isFile() && entry.name.endsWith(".ts")) out.push(full);
  }
  return out;
}

describe("#380 — 소속 판정 술어의 단일화 (정적)", () => {
  const files = SCAN_ROOTS.flatMap(listSourceFiles);

  it("검사 대상이 0건이 아니다", () => {
    // 경로가 바뀌거나 사라지면 "위반 없음"이 아니라 "아무것도 안 봄"이다 — 그 상태로 초록이 되지 않게 한다.
    expect(SCAN_ROOTS.filter((d) => fs.existsSync(d))).toHaveLength(SCAN_ROOTS.length);
    expect(files.length).toBeGreaterThan(0);
  });

  it("스칼라 workspace_id 단독 비교로 소속을 판정하는 자리가 없다", () => {
    const violations: string[] = [];
    for (const file of files) {
      const source = fs.readFileSync(file, "utf8");
      source.split("\n").forEach((line, i) => {
        if (line.trimStart().startsWith("*") || line.trimStart().startsWith("//")) return; // 주석의 설명문은 제외
        if (SCALAR_ONLY_PATTERNS.some((p) => p.test(line))) {
          violations.push(`${path.relative(FRONTEND_ROOT, file)}:${i + 1}: ${line.trim()}`);
        }
      });
    }
    expect(violations, `소속 판정은 ${CANONICAL_PREDICATE} 하나만 쓴다 (#380)`).toEqual([]);
  });

  it("정본 술어를 쓰는 호출부가 기대 수만큼 있다", () => {
    const callers = files.filter((f) => {
      const source = fs.readFileSync(f, "utf8");
      // 정의부(authUtils.ts 의 export)가 아니라 실제 호출부만 센다.
      return new RegExp(`${CANONICAL_PREDICATE}\\s*\\(`).test(source);
    });
    expect(callers.map((f) => path.relative(FRONTEND_ROOT, f)).sort()).toHaveLength(EXPECTED_CANONICAL_CALLERS);
  });
});
