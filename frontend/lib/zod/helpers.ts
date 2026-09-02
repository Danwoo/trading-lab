// lib/zod/helpers.ts
import { z } from "zod";
// Zod i18n 부트스트랩만 필요하다(#352) — "@/utils/common/locale" 는 DevExtreme 부트스트랩도
// 함께 실행해, 이 파일을 거치는 schemas/* 전체가 devextreme 을 전이로 물었다.
import "@/utils/common/locale/zodBootstrap";

/**
 * Zod 헬퍼 라이브러리
 * Zod를 몰라도 헬퍼만으로 모든 유효성 검증 가능
 */

// ================================
// 기본 타입 (9개)
// ================================
export const str = (min_length = 1) => z.string().trim().min(min_length);
export const int = () => z.number().int();
export const float = () => z.number();
export const bool = () => z.boolean();
export const date = () =>
  z
    .string()
    .trim()
    .regex(/^\d{4}-\d{2}-\d{2}$/);
export const phone = () =>
  z
    .string()
    .trim()
    .regex(/^01[0-9]-\d{3,4}-\d{4}$/);
export const email = () => z.email().trim();
export const url = () => z.url().trim();
export const uuid = () => z.uuid();
/** 호스트네임(도메인) 형식 — 프로토콜/경로/@ 비포함. 예: example.com, partner.example.com */
export const domain = (max = 100) =>
  z
    .string()
    .trim()
    .toLowerCase()
    .min(1)
    .max(max)
    .regex(
      /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$/,
      "올바른 도메인 형식이 아닙니다",
    );

// ================================
// 핵심 패턴 (2개)
// ================================
/**
 * `.optional()`·`.nullable()`·`.default()` 같은 래퍼를 벗겨 실제 타입 스키마를 꺼낸다.
 * 깊이 상한을 둬 순환 정의에서 멈추지 않게 한다.
 */
const unwrapSchema = (schema: z.ZodTypeAny): z.ZodTypeAny => {
  let current: any = schema;
  for (let depth = 0; depth < 10 && current?.def?.innerType; depth++) {
    current = current.def.innerType;
  }
  return current;
};

/**
 * 숫자 문자열로 인정하는 표기 — 부호 + 십진수뿐이다(앵커 필수).
 *
 * `Number()` 는 이보다 훨씬 넓다: `"3e2"`→300, `"0x10"`→16, `"0b101"`→5, `"0o17"`→15.
 * 화면에 "3" 처럼 보이는 값이 300 이 되면 **오배정이 조용히 성립한다** — 정수 가드
 * (`z.number().int()`)는 300 도 16 도 정수라 못 잡는다. 폼이 실제로 만들어 내는 표기는
 * 십진수뿐이므로(SelectBox 는 항목의 id, NumberBox 는 숫자를 그대로 낸다) 여기서 자른다.
 * 앞뒤 공백은 허용한다 — `str()` 도 trim 하고, `" 1 "` 은 사람이 읽는 값과 같다.
 */
const DECIMAL_NUMBER_RE = /^[+-]?(\d+(\.\d+)?|\.\d+)$/;

/**
 * Optional 처리: 빈값을 undefined 로 변환, 문자열 타입 자동변환.
 *
 * 자동변환이 필요한 이유 — HTML `<input>`·`<select>` 의 value 는 **항상 문자열**이다.
 * 숫자·불리언 필드가 그 값을 그대로 받으면 변환 없이는 검증이 실패한다.
 *
 * 타입 판정은 zod 가 export 하는 클래스(`z.ZodNumber`·`z.ZodBoolean`)로 한다. 예전엔 v3 의
 * 내부 shape(`_def.typeName`)를 읽었는데 v4 에서 그 값이 `undefined` 라 판정이 항상 "unknown"
 * 이 되어 자동변환이 통째로 죽어 있었다(#382) — 주석만 있고 그물이 없어 조용히 깨졌다.
 * 그물은 tests/lib/zod/helpers.test.ts 다.
 *
 * **「키가 없다」와 「키는 있는데 값이 손상됐다」를 가른다.** 변환에 실패한 값은 `undefined`
 * 로 접지 않고 **원본 그대로 안쪽 스키마에 넘겨 거절**시킨다. 예전엔 손상값이 "값 없음"이
 * 되어, 그 결과를 `?? null` 로 받는 PUT 전체표현 계약(#400)에서 **손상된 요청이 필드를 지우는
 * 정상 요청으로 둔갑**했다 — `workspace_id: "garbage"` 가 200 + 배정 해제 + 일반관리자 권한
 * 삭제 + 세션 무효화까지 연쇄했다. `use_at` 처럼 필수화해서 막을 수 없는 필드(null 이 정상
 * 상태)라 경계는 여기밖에 없다.
 *
 * 빈값(`null`·`undefined`·`""`·공백만)이 `undefined` 로 접히는 것은 그대로 둔다 — 그건 손상이
 * 아니라 **"값을 비웠다"는 신호**이고, 폼의 clear 버튼이 내는 값이다.
 */
export const Optional = <T extends z.ZodTypeAny>(schema: T) => {
  // 판정은 스키마를 만들 때 한 번만 — 파싱마다 다시 볼 이유가 없다.
  const inner = unwrapSchema(schema);
  const isNumber = inner instanceof z.ZodNumber;
  const isBoolean = inner instanceof z.ZodBoolean;
  const isArray = inner instanceof z.ZodArray;

  return z.preprocess((val) => {
    if (val === null || val === undefined || val === "") return undefined;
    if (typeof val === "string" && val.trim() === "") return undefined;
    // 빈 배열이 "선택 없음"인 것은 배열 스키마에서만 참이다. 숫자·문자열 필드에 온 `[]` 는
    // 선택 없음이 아니라 손상값이라 접지 않고 거절시킨다(`workspace_id: []` 도 배정 해제였다).
    if (isArray && Array.isArray(val) && val.length === 0) return undefined;

    if (isNumber && typeof val === "string") {
      const trimmed = val.trim();
      if (!DECIMAL_NUMBER_RE.test(trimmed)) return val;
      const num = Number(trimmed);
      // 십진수라도 자릿수가 넘치면 Infinity 가 된다("1".repeat(400)). zod v4 의 `z.number()` 도
      // Infinity 를 거절하지만, 여기서 자르면 이 헬퍼가 안쪽 스키마의 버전별 동작에 안 기댄다.
      return Number.isFinite(num) ? num : val;
    }
    if (isBoolean && typeof val === "string") {
      const normalized = val.trim().toLowerCase();
      if (normalized === "true") return true;
      if (normalized === "false") return false;
      return val;
    }
    return val;
  }, schema.optional());
};

/** 제약조건 통합 필드 생성기 */
export const Field = (constraints: {
  min_length?: number;
  max_length?: number;
  pattern?: RegExp;
  ge?: number;
  le?: number;
  gt?: number;
  lt?: number;
  gte?: number;
  lte?: number;
  precision?: number;
  scale?: number;
  min_items?: number;
  max_items?: number;
}) => ({
  str: () => {
    let s = z.string().trim();
    if (constraints.min_length !== undefined) s = s.min(constraints.min_length);
    if (constraints.max_length !== undefined) s = s.max(constraints.max_length);
    if (constraints.pattern) s = s.regex(constraints.pattern);
    return s;
  },
  int: () => {
    let s = z.number().int();
    if (constraints.ge !== undefined) s = s.gte(constraints.ge);
    if (constraints.le !== undefined) s = s.lte(constraints.le);
    if (constraints.gt !== undefined) s = s.gt(constraints.gt);
    if (constraints.lt !== undefined) s = s.lt(constraints.lt);
    if (constraints.gte !== undefined) s = s.gte(constraints.gte);
    if (constraints.lte !== undefined) s = s.lte(constraints.lte);
    return s;
  },
  float: () => {
    let s = z.number();
    if (constraints.ge !== undefined) s = s.gte(constraints.ge);
    if (constraints.le !== undefined) s = s.lte(constraints.le);
    if (constraints.gt !== undefined) s = s.gt(constraints.gt);
    if (constraints.lt !== undefined) s = s.lt(constraints.lt);
    if (constraints.gte !== undefined) s = s.gte(constraints.gte);
    if (constraints.lte !== undefined) s = s.lte(constraints.lte);
    return s;
  },
  numeric: () => {
    const precision = constraints.precision || 10;
    const scale = constraints.scale || 0;
    return z.number().refine((value) => {
      const valueStr = Math.abs(value).toString();
      const [intPart, decPart = ""] = valueStr.split(".");
      const intDigits = intPart === "0" ? 0 : intPart.length;
      const scaleDigits = decPart.length;
      return intDigits + scaleDigits <= precision && scaleDigits <= scale;
    });
  },
});

// ================================
// 범위 패턴 (6개)
// ================================
export const StrRange = (min: number, max: number) => Field({ min_length: min, max_length: max }).str();
export const IntRange = (min: number, max: number) => Field({ ge: min, le: max }).int();
export const FloatRange = (min: number, max: number) => Field({ ge: min, le: max }).float();
export const PositiveInt = () => Field({ gte: 0 }).int();
/** 1 이상의 정수 — 「제한 횟수」처럼 0 이 뜻을 잃는 칸. 백엔드의 `gt=0` 과 같은 규칙이다. */
export const CountInt = () => Field({ gt: 0 }).int();
export const PositiveFloat = () => Field({ gte: 0 }).float();
export const Numeric = (precision = 10, scale = 0) => Field({ precision, scale }).numeric();

// ================================
// 컬렉션 (5개)
// ================================
export const object = <T extends z.ZodRawShape>(shape: T) => z.object(shape);
export const array = <T extends z.ZodTypeAny>(itemSchema: T) => z.array(itemSchema);
export const record = <T extends z.ZodTypeAny>(valueSchema?: T) =>
  valueSchema ? z.record(z.string(), valueSchema) : z.record(z.string(), z.any());
export const enums = <T extends readonly [string, ...string[]]>(values: T) => z.enum(values);
export const any = () => z.any().refine((val) => val !== undefined && val !== null);

// ================================
// 특수 타입 (1개)
// ================================
const PASSWORD_PATTERN = /^(?=.*[a-zA-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]/;
export const password = () => Field({ min_length: 8, pattern: PASSWORD_PATTERN }).str();

// ================================
// 파일 (2개)
// ================================
export const files = () => z.array(z.instanceof(File)).min(1);
export const requireFiles = (fileKey: string) => {
  const base = fileKey.replace(/Files$/, "");
  const flagKey = `hasExisting${base[0].toUpperCase()}${base.slice(1)}s`;
  return (val: any, ctx: z.RefinementCtx) => {
    if (val[flagKey]) return;
    const result = files().safeParse(val[fileKey]);
    if (result.success) return;
    result.error.issues.forEach((issue) => ctx.addIssue({ ...issue, path: [fileKey, ...issue.path] }));
  };
};
