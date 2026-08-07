// utils/common/locale/ko/zod.ts
// Zod 한국어 로케일 + 커스텀(자연스러운 한국어) 에러 메시지.
import { z } from "zod";
import { ko } from "zod/locales";

const customError = (issue: any): string | undefined => {
  switch (issue.code) {
    case "too_small": {
      const min = issue.minimum;
      const adj = issue.inclusive ? "이상" : "초과";
      if (issue.origin === "string") {
        if (typeof issue.input === "string" && issue.input.trim() === "") return "필수 입력 항목입니다";
        return min === 1 ? "필수 입력 항목입니다" : `최소 ${min}자 이상 입력해주세요`;
      }
      if (issue.origin === "number") return `${min} ${adj} 값을 입력해주세요`;
      if (issue.origin === "array") return `최소 ${min}개 이상 선택해주세요`;
      if (issue.origin === "set") return `최소 ${min}개 이상 선택해주세요`;
      if (issue.origin === "file") return `최소 ${min}바이트 이상이어야 합니다`;
      if (issue.origin === "date") return `${min} ${adj}의 날짜를 입력해주세요`;
      return `${min} ${adj}의 값을 입력해주세요`;
    }
    case "too_big": {
      const max = issue.maximum;
      const adj = issue.inclusive ? "이하" : "미만";
      if (issue.origin === "string") return `최대 ${max}자까지 입력 가능합니다`;
      if (issue.origin === "number") return `${max} ${adj} 값을 입력해주세요`;
      if (issue.origin === "array") return `최대 ${max}개까지 선택 가능합니다`;
      if (issue.origin === "set") return `최대 ${max}개까지 선택 가능합니다`;
      if (issue.origin === "file") return `최대 ${max}바이트까지 가능합니다`;
      if (issue.origin === "date") return `${max} ${adj}의 날짜를 입력해주세요`;
      return `${max} ${adj}의 값을 입력해주세요`;
    }
    case "invalid_type": {
      if (issue.input === undefined || issue.input === null) return "필수 입력 항목입니다";
      if (issue.expected === "string") return "문자열을 입력해주세요";
      if (issue.expected === "number") return "숫자를 입력해주세요";
      if (issue.expected === "boolean") return "참/거짓 값을 입력해주세요";
      if (issue.expected === "date") return "올바른 날짜를 입력해주세요";
      if (issue.expected === "array") return "배열 형식이어야 합니다";
      if (issue.expected === "object") return "객체 형식이어야 합니다";
      return "올바르지 않은 데이터 타입입니다";
    }
    case "invalid_format": {
      if (typeof issue.input === "string" && issue.input.trim() === "") return "필수 입력 항목입니다";
      const f = issue.format;
      if (f === "starts_with") return `"${issue.prefix}"(으)로 시작해야 합니다`;
      if (f === "ends_with") return `"${issue.suffix}"(으)로 끝나야 합니다`;
      if (f === "includes") return `"${issue.includes}"을(를) 포함해야 합니다`;
      if (f === "regex") return "형식이 올바르지 않습니다";
      if (f === "email") return "올바른 이메일 형식이 아닙니다";
      if (f === "url") return "올바른 URL 형식이 아닙니다";
      if (f === "uuid" || f === "uuidv4" || f === "uuidv6" || f === "guid") return "올바른 UUID 형식이 아닙니다";
      if (f === "datetime") return "올바른 날짜시간 형식이 아닙니다";
      if (f === "date") return "올바른 날짜 형식이 아닙니다";
      if (f === "time") return "올바른 시간 형식이 아닙니다";
      if (f === "ipv4" || f === "ipv6") return "올바른 IP 주소가 아닙니다";
      if (f === "base64" || f === "base64url") return "올바른 base64 형식이 아닙니다";
      if (f === "jwt") return "올바른 JWT 형식이 아닙니다";
      return "올바르지 않은 형식입니다";
    }
    case "invalid_value": {
      if (issue.values?.length === 1) return `허용된 값: ${String(issue.values[0])}`;
      return `허용된 값 중 하나여야 합니다 (${(issue.values ?? []).join(", ")})`;
    }
    case "not_multiple_of":
      return `${issue.divisor}의 배수여야 합니다`;
    case "unrecognized_keys":
      return `허용되지 않은 필드가 포함되어 있습니다: ${(issue.keys ?? []).join(", ")}`;
    case "invalid_key":
      return "허용되지 않은 키입니다";
    case "invalid_element":
      return "허용되지 않은 항목이 포함되어 있습니다";
    case "invalid_union":
      return "올바르지 않은 입력입니다";
    default:
      return undefined;
  }
};

/** Zod 한글 로케일 + 커스텀 메시지 적용. */
export function apply(): void {
  z.config(ko());
  z.config({ customError });
}
