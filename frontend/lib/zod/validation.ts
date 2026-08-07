// lib/zod/validation.ts
import { z } from "zod";

/**
 * 검증 에러 상세 타입
 */
export interface ValidationErrorDetail {
  loc: string[];
  msg: string;
  type: string;
}

/**
 * Client 검증 에러 클래스
 */
export class ClientValidationError extends Error {
  constructor(public detail: ValidationErrorDetail[]) {
    super("Client validation failed");
    this.name = "ClientValidationError";
  }
}

/**
 * Zod 에러를 FastAPI 형식으로 변환
 */
export function formatZodErrorToFastAPI(zodError: z.ZodError): Array<{ loc: string[]; msg: string; type: string }> {
  return zodError.issues.map((error) => ({
    loc: ["body", ...error.path.map(String)],
    msg: error.message,
    type: error.code || "validation_error",
  }));
}

/**
 * Client Zod 검증 에러 처리 공통 함수
 */
export function handleZodValidationError(error: unknown): never {
  if (error instanceof ClientValidationError) {
    const clientError = new Error("Client validation failed");
    (clientError as any).response = {
      status: 422,
      data: { detail: error.detail },
    };
    throw clientError;
  }
  throw error;
}

/**
 * Zod 스키마 검증 및 FastAPI 에러 변환 헬퍼
 */
export function validateWithZod<T>(schema: z.ZodSchema<T>, data: unknown): T {
  const validationResult = schema.safeParse(data);
  if (!validationResult.success) {
    const fastApiErrors = formatZodErrorToFastAPI(validationResult.error);
    throw new ClientValidationError(fastApiErrors);
  }
  return validationResult.data;
}
