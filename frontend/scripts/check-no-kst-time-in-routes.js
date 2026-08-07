#!/usr/bin/env node
// #372 — #303 회귀 그물(tests/regressions/303-admin-timestamp.test.tsx)이 실제 라우트 코드를
// import 하지 않고 쓰기·읽기를 지역 람다로 모사해, 라우트가 `getKSTTime()` 을 다시 써도
// 그 테스트는 계속 초록이었다. `getKSTTime`/`getKSTTimestamp` 는 `utils/common/timeUtils.ts`
// 에 여전히 export 로 살아 있고(KST 벽시계가 필요한 화면 밖 용도 — 파일명 타임스탬프 등에
// 정당하게 쓰인다, 예: hooks/shared/tableExport.ts·useExcelExport.ts), 그 재유입을 막는 렉시컬
// 그물이 이제까지 0건이었다.
//
// `verify_no_absolute_dates.py`(backend-service, #269)와 같은 원칙의 자매 스크립트 — 값싼
// 정적 스캔으로 "낡을 값/재유입 위험한 함수가 대상 경로에 들어오는 순간"을 잡는다. #303 이 고친
// 근본 문제(reg_dt·mod_dt 같은 인스턴트 컬럼에 KST 시프트가 섞여 들어가는 것)의 재발 방지가
// 목적이므로, 대상은 그 컬럼들을 쓰는 `app/api/**` 라우트 핸들러다.
//
// 대상: `app/api/**/*.ts`(현재는 route.ts 뿐이지만 헬퍼 파일이 생겨도 따라가도록 확장자로 스캔).
// 검사: `getKSTTime(` 호출 — `getKSTTimestamp(` 은 이름이 겹치지만 뒤에 "stamp"가 더 붙어
// 정규식이 구분한다(별도 함수, 저장 경로 오용 이력이 없어 대상 밖). 라인 단위로 `//` 뒤를 먼저
// 지우고 검사해 주석 속 언급(예시 코드 등)을 오탐으로 잡지 않는다.
//
// fail-closed: 스캔한 파일이 0개면 경로가 옮겨졌거나 사라진 것이므로 통과가 아니라 실패다.
// 스캔한 파일 수를 출력한다 — 초록이 "위반 없음"인지 "아무것도 안 봤음"인지 구분하기 위해서다.

import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SCAN_ROOT = path.join(frontendDir, "app/api");
const EXTENSIONS = [".ts", ".tsx"];

// `getKSTTime(` 호출 — 단어 경계를 앞뒤로 둬 다른 식별자의 일부로 우연히 걸리지 않게 한다.
// `getKSTTimestamp(` 은 "Time" 다음에 바로 "(" 가 오지 않아(그 사이 "stamp" 가 있다) 이 정규식과
// 겹치지 않는다 — 자체 테스트(selfTest)가 이 구분을 실제로 확인한다.
const KST_TIME_CALL_RE = /\bgetKSTTime\s*\(/;

function stripLineComments(src) {
  // 문자열 리터럴 안의 "//" 까지 완벽히 구분하는 토크나이저는 아니다 — 이 레포 코드 스타일상
  // route.ts 안에 "//" 를 포함한 문자열 리터럴이 거의 없고(URL 은 대개 "://" 형태로 // 앞에
  // ":" 가 붙어 있어 이 라인 전체가 주석으로 잘려도 검사 목적(코드 호출 탐지)엔 영향이 없다),
  // 목적은 "주석 속 함수명 언급"을 오탐에서 빼는 것뿐이라 이 근사로 충분하다.
  return src
    .split("\n")
    .map((line) => {
      const idx = line.indexOf("//");
      return idx === -1 ? line : line.slice(0, idx);
    })
    .join("\n");
}

function listFiles(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const abs = path.join(dir, name);
    const st = statSync(abs);
    if (st.isDirectory()) {
      out.push(...listFiles(abs));
    } else if (EXTENSIONS.includes(path.extname(name))) {
      out.push(abs);
    }
  }
  return out;
}

function selfTest() {
  const cases = [
    ["const x = getKSTTime(new Date());", true, "직접 호출"],
    ["const x = getKSTTime (new Date());", true, "괄호 앞 공백"],
    ["const x = getKSTTimestamp(new Date());", false, "getKSTTimestamp 는 다른 함수 — 오탐 아님"],
    ["// getKSTTime(d) 를 쓰면 안 된다 — 예시", false, "주석 속 언급은 제외"],
    [
      "import { getKSTTime } from '@/utils/common/timeUtils';",
      false,
      "import 단독은 호출이 아니므로 이 그물의 대상 밖(호출부만 본다)",
    ],
  ];
  const failed = [];
  for (const [src, expected, label] of cases) {
    const stripped = stripLineComments(src);
    const got = KST_TIME_CALL_RE.test(stripped);
    if (got !== expected) failed.push(`${label} — 기대 ${expected}, 실제 ${got}`);
  }
  if (failed.length > 0) {
    console.error(
      "[check-no-kst-time-in-routes] 자체 그물 실패 — 정규식이 기대와 다르게 동작합니다:\n" +
        failed.map((l) => `  - ${l}`).join("\n"),
    );
    process.exit(1);
  }
  console.log(`[check-no-kst-time-in-routes] 자체 그물 — 케이스 ${cases.length}건 전부 확인.`);
}

selfTest();

if (!statSync(SCAN_ROOT, { throwIfNoEntry: false })?.isDirectory()) {
  console.error(`[check-no-kst-time-in-routes] 대상 디렉터리가 없습니다: ${path.relative(frontendDir, SCAN_ROOT)}`);
  process.exit(1);
}

const files = listFiles(SCAN_ROOT);
if (files.length === 0) {
  console.error(
    `[check-no-kst-time-in-routes] 검사 대상 파일 0개 — app/api 경로 구조가 바뀌었거나 확장자 필터(${EXTENSIONS.join(", ")})가 어긋났습니다.`,
  );
  process.exit(1);
}

const violations = [];
for (const file of files) {
  const src = readFileSync(file, "utf-8");
  const stripped = stripLineComments(src);
  const lines = stripped.split("\n");
  lines.forEach((line, idx) => {
    if (KST_TIME_CALL_RE.test(line)) {
      violations.push(`${path.relative(frontendDir, file)}:${idx + 1}: ${lines[idx].trim()}`);
    }
  });
}

if (violations.length > 0) {
  console.error(
    `\n[check-no-kst-time-in-routes] app/api 라우트에서 getKSTTime() 호출 ${violations.length}건 발견 (스캔 ${files.length}개 파일) — #303 재발 위험:\n`,
  );
  console.error(violations.map((v) => `  - ${v}`).join("\n"));
  console.error(
    "\n  reg_dt·mod_dt 등 인스턴트 컬럼에는 new Date() 를 그대로 쓰세요 — getKSTTime() 은 KST",
    "벽시계 값이 필요한 화면 밖 용도(파일명 타임스탬프 등) 전용입니다",
    "(utils/common/timeUtils.ts 의 getKSTTime 문서 주석 참고).\n",
  );
  process.exit(1);
}

console.log(`[check-no-kst-time-in-routes] app/api getKSTTime() 호출 0건 — 통과 (${files.length}개 파일 스캔).`);
