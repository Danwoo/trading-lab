// utils/common/form/unchanged.ts
//
// 「저장했는데 아무것도 안 바뀌었다」를 가른다 (#446 F33).
//
// 「수정이 완료되었습니다」는 **무언가 달라졌다**는 말이다. 안 달라졌을 때 같은 말을 하면
// 진짜 변경의 신호가 값을 잃는다 — 사용자는 그 문장으로 저장 여부를 판단하는데, 늘 뜨는
// 문장은 아무것도 말하지 않는다.
//
// **판정은 한쪽으로만 틀린다.** 「안 바뀌었다」를 잘못 말하면 사용자의 진짜 편집이 저장되지
// 않고 사라진다 — 지금의 거짓말보다 나쁘다. 그래서 **확실히 같을 때만** 참이고, 조금이라도
// 비교할 수 없으면 거짓(=저장한다)이다:
//
//   · 비교 대상이 없다(현재 값 자체를 모른다)        → 저장한다
//   · 보낸 값에 원시값이 아닌 것이 섞였다(객체·배열) → 저장한다
//   · 키가 현재 레코드에 없다                        → 저장한다
//
// 폼 컨트롤은 빈 칸을 `""` 로 주고 서버는 같은 자리를 `null` 로 주므로, 그 둘만 같은 것으로
// 본다. 숫자·불리언은 문자열로 접지 않는다 — `"0"` 과 `0` 을 같다고 하면 실제 편집을 삼킬 수
// 있는 쪽으로 틀린다.

/** 빈 칸의 두 표기(`null`·`undefined`·`""`)만 하나로 접는다. */
function normalizeBlank(value: unknown): unknown {
  return value === null || value === undefined ? "" : value;
}

function isPrimitive(value: unknown): boolean {
  return value === null || value === undefined || ["string", "number", "boolean"].includes(typeof value);
}

/**
 * 보낸 값이 현재 레코드와 **모든 칸에서 같은가.**
 *
 * `submitted` 의 키만 본다 — 폼이 레코드의 일부만 담는 것이 보통이고, 담지 않은 칸은
 * 이 저장이 건드리지 않는 칸이다.
 */
export function isUnchanged(submitted: unknown, current: unknown): boolean {
  if (!submitted || typeof submitted !== "object" || Array.isArray(submitted)) return false;
  if (!current || typeof current !== "object" || Array.isArray(current)) return false;

  const record = current as Record<string, unknown>;
  const entries = Object.entries(submitted as Record<string, unknown>);
  if (entries.length === 0) return false; // 빈 폼을 「안 바뀜」으로 접지 않는다

  for (const [key, value] of entries) {
    if (!isPrimitive(value)) return false;
    if (!(key in record)) return false;
    if (!isPrimitive(record[key])) return false;
    if (normalizeBlank(value) !== normalizeBlank(record[key])) return false;
  }
  return true;
}

/** 안 바뀐 저장에 내는 말 — 화면마다 다르게 쓰지 않는다. */
export const NOTHING_CHANGED = "바뀐 것이 없습니다.";
