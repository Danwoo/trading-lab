// #224 — **예외 원문이 화면 문구로 실리는 자리를 늘리지 않는다.**
//
// 첫 판에서는 훅 두 개만 고쳤는데, 독립 리뷰가 같은 패턴 두 곳을 더 찾았고(신선도 배너·
// 격자 폼) 그중 하나는 이슈가 실측으로 나열한 401 자리였다. 셋째(봇 목록 배너)는 그 뒤
// 전수 조사에서 나왔다. **손으로 훑는 것으로는 이 클래스가 닫히지 않는다** — 그래서
// 정적으로 잡는다.
//
// 규칙: 화면 문구가 되는 값에 `…error.message` 를 그대로 싣지 않는다. 번역기
// (`getApiErrorMessage`)를 태우면 401·5xx 가 우리 말로 바뀌고 원문은 콘솔로 간다.
//
// **검증 경계** — 정적 검사다. 실제로 그 문구가 렌더되는지는 보지 않는다. 아래 ALLOWED 에
// 적힌 자리는 사람이 판단해 통과시킨 것이고, 새로 늘어나는 자리는 여기서 막힌다.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.dirname(path.dirname(path.dirname(fileURLToPath(import.meta.url))));

/** 화면 문구가 만들어지는 계층 — 서버 라우트·로깅은 원문을 남겨야 하므로 대상이 아니다. */
const SCANNED_DIRS = ["hooks", "components", "stores", "app/(main)"];

/**
 * 예외에서 나온 값의 `.message` 를 읽는 모양 — `error.message`·`error?.response?.data?.message`·
 * `botDetailError.message`·`e.message` 를 잡는다. 성공 응답의 `result.message` 나 우리 토스트
 * 객체의 `toast.message` 는 대상이 아니다.
 */
const RAW_MESSAGE = /(?:\b\w*(?:[Ee]rror|[Ee]rr|cause)\w*\b|(?<![\w$])e)\s*\??\.(?:\w+\??\.)*message\b/;

/**
 * 사람이 판단해 통과시킨 자리. 각 항목에 왜 괜찮은지를 적는다 — 이유 없이 늘리지 않기 위해서다.
 */
const ALLOWED: Record<string, string> = {
  "components/features/Bot/BotForm.tsx": "백엔드가 전략 파일별로 만든 사유다 — axios 원문이 아니다",
  "components/features/Common/Auth/Login.tsx": "문자열 매칭만 한다 — 화면에 싣지 않는다",
  "components/features/Terminal/PanelErrorBoundary.tsx": "React 렌더 예외의 진단 문구다 — API 오류가 아니다",
  "components/shared/ui/primitives/fieldState.ts": "Zod 검증 메시지다 — 이미 한국어다",
  "components/shared/ui/CheckBoxGroup.tsx": "DevExtreme 폼 검증 메시지다 — API 오류가 아니다",
  "components/shared/ui/TextBox.tsx": "DevExtreme 폼 검증 메시지다 — API 오류가 아니다",
};

function walk(dir: string): string[] {
  const entries = fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true }) : [];
  return entries.flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return walk(full);
    return /\.tsx?$/.test(entry.name) ? [full] : [];
  });
}

describe("#224 예외 원문이 화면 문구로 실리지 않는다", () => {
  it("훑은 파일이 0건이면 실패한다 — 경로가 바뀌면 조용히 초록이 되지 않게", () => {
    const files = SCANNED_DIRS.flatMap((dir) => walk(path.join(FRONTEND_ROOT, dir)));

    expect(files.length).toBeGreaterThan(50);
  });

  it("원문을 그대로 싣는 자리는 허용 목록에 적힌 것뿐이다", () => {
    const files = SCANNED_DIRS.flatMap((dir) => walk(path.join(FRONTEND_ROOT, dir)));
    const offenders: string[] = [];

    for (const file of files) {
      const rel = path.relative(FRONTEND_ROOT, file);
      if (ALLOWED[rel]) continue;

      const lines = fs.readFileSync(file, "utf8").split("\n");
      lines.forEach((line, i) => {
        if (line.includes("getApiErrorMessage")) return;
        if (RAW_MESSAGE.test(line)) offenders.push(`${rel}:${i + 1} — ${line.trim()}`);
      });
    }

    expect(offenders).toEqual([]);
  });
});
