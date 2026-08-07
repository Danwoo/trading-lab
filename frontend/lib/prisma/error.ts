// lib/prisma/error.ts

import { Prisma } from "@/prisma/generated/client";
import { Error, ErrorResponse } from "@/schemas/common/error";

function extractFieldFromPrismaError(message: string): string {
  // 1. 가장 구체적인 패턴부터 시도: Argument `field_name` is missing
  let match = message.match(/Argument\s+`([^`]+)`\s+is\s+missing/i);
  if (match && !match[1].includes("$") && !match[1].includes("TURBOPACK")) {
    return match[1];
  }

  // 2. 일반적인 Argument 패턴: Argument `field_name`
  match = message.match(/Argument\s+`([^`]+)`/i);
  if (match && !match[1].includes("$") && !match[1].includes("TURBOPACK")) {
    return match[1];
  }

  // 3. 백틱 패턴 (Turbopack 관련 제외)
  const backtickMatches = message.match(/`([^`]+)`/g);
  if (backtickMatches) {
    for (const backtickMatch of backtickMatches) {
      const field = backtickMatch.replace(/`/g, "");
      if (!field.includes("$") && !field.includes("[") && !field.includes("TURBOPACK") && !field.includes(".")) {
        return field;
      }
    }
  }

  // 4. 따옴표 패턴
  match = message.match(/"([^"]+)"/);
  if (match && !match[1].includes("$") && !match[1].includes("[")) {
    return match[1];
  }

  return "";
}

// Prisma 에러 → { type, loc, msg }. type 은 번역 키:
// - KnownRequestError → 실제 Prisma 코드(P2002 등), - 그 외 클래스 → prisma_* (Zod/Pydantic type 과 충돌 회피)
// 번역은 utils/common/locale/*/apierrors.ts 의 PRISMA_ERROR_MAP 가 type 으로 1:1 매칭.
export function convertPrismaErrorToValidation(error: any, context: string = "body"): ErrorResponse {
  let type: string;
  let field = "";

  if (error instanceof Prisma.PrismaClientKnownRequestError) {
    type = error.code;
    const target = error.meta?.target;
    field =
      (Array.isArray(target) ? String(target[0] ?? "") : typeof target === "string" ? target : "") ||
      extractFieldFromPrismaError(error.message);
  } else if (error instanceof Prisma.PrismaClientValidationError) {
    type = "prisma_validation_error";
    field = extractFieldFromPrismaError(error.message);
  } else if (error instanceof Prisma.PrismaClientInitializationError) {
    type = "prisma_initialization_error";
  } else if (error instanceof Prisma.PrismaClientRustPanicError) {
    type = "prisma_rust_panic_error";
  } else if (error instanceof Prisma.PrismaClientUnknownRequestError) {
    type = "prisma_unknown_error";
  } else {
    type = "prisma_general_error";
  }

  const detail: Error[] = [{ type, loc: field ? [context, field] : [context], msg: type }];
  return { detail };
}
