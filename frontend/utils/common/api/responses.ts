// utils/common/api/responses.ts

import axios from "axios";
import { NextResponse } from "next/server";
import { Prisma } from "@/prisma/generated/client";
import { convertPrismaErrorToValidation } from "@/lib/prisma/error";
import { OPERATION_SUCCESS_STATUS_CODES, OPERATION_SUCCESS_MESSAGES, OPERATION_ERROR_MESSAGES } from "./constants";

export function createErrorResponse(error: any, operation: string) {
  const message = OPERATION_ERROR_MESSAGES[operation] || "처리 중 오류가 발생했습니다.";

  // 1. 커스텀 인증 에러 처리 (401 — 토큰 만료/미인증)
  if (error && typeof error === "object" && error.code === "AUTH") {
    return NextResponse.json(
      {
        detail: [
          {
            type: "auth_error",
            loc: ["auth"],
            msg: message,
          },
        ],
      },
      { status: 401 },
    );
  }

  // 1-2. 권한 부족 (403 — 인증은 됐지만 sysAdmin 등 요구권한 미충족)
  if (error && typeof error === "object" && error.code === "FORBIDDEN") {
    return NextResponse.json(
      {
        detail: [
          {
            type: "forbidden",
            loc: ["auth"],
            msg: error.message || "권한이 없습니다.",
          },
        ],
      },
      { status: 403 },
    );
  }

  // 2. Prisma 에러 처리
  if (
    error instanceof Prisma.PrismaClientValidationError ||
    error instanceof Prisma.PrismaClientKnownRequestError ||
    error instanceof Prisma.PrismaClientUnknownRequestError ||
    (error && typeof error === "object" && typeof error.code === "string" && error.code.startsWith("P"))
  ) {
    const validationError = convertPrismaErrorToValidation(error, "body");
    const status = error instanceof Prisma.PrismaClientValidationError ? 422 : 500;
    return NextResponse.json(validationError, { status });
  }

  // 3. Axios 에러 처리
  if (axios.isAxiosError(error)) {
    if (error.response) {
      return NextResponse.json(error.response.data, { status: error.response.status });
    }
    return NextResponse.json({ detail: [{ type: "server_error", loc: ["server"], msg: message }] }, { status: 503 });
  }

  // 4. 커스텀 메시지 ({ message: "..." } plain object)
  if (error && typeof error === "object" && typeof error.message === "string" && !(error instanceof Error)) {
    return NextResponse.json({ message: error.message }, { status: 400 });
  }

  // 5. fallback
  return NextResponse.json(
    {
      detail: [
        {
          type: "server_error",
          loc: ["server"],
          msg: message,
        },
      ],
    },
    { status: 500 },
  );
}

export function createSuccessResponse(data: any, operation?: string, customStatus?: number) {
  if (customStatus) {
    return NextResponse.json(data, { status: customStatus });
  }

  const status = operation ? OPERATION_SUCCESS_STATUS_CODES[operation] || 200 : 200;

  let responseData = data;
  if (operation && data && typeof data === "object" && !data.message) {
    responseData = {
      ...data,
      message: OPERATION_SUCCESS_MESSAGES[operation] || "처리가 완료되었습니다.",
    };
  }

  return NextResponse.json(responseData, { status });
}
