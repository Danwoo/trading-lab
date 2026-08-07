// app/api/common/system/adminuser/[email]/session/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";

const parseUserAgent = (ua: string): string => {
  if (!ua || ua === "-") return "-";

  const browser = /Edg\/(\d+)/.exec(ua)?.[1]
    ? `Edge ${/Edg\/(\d+)/.exec(ua)![1]}`
    : /OPR\/(\d+)/.exec(ua)?.[1]
      ? `Opera ${/OPR\/(\d+)/.exec(ua)![1]}`
      : /Firefox\/(\d+)/.exec(ua)?.[1]
        ? `Firefox ${/Firefox\/(\d+)/.exec(ua)![1]}`
        : /Chrome\/(\d+)/.exec(ua)?.[1]
          ? `Chrome ${/Chrome\/(\d+)/.exec(ua)![1]}`
          : /Safari\/(\d+)/.exec(ua)?.[1]
            ? `Safari`
            : "Unknown";

  const os = /Windows NT 10/.test(ua)
    ? "Windows 10"
    : /Windows NT 11/.test(ua)
      ? "Windows 11"
      : /Windows NT/.test(ua)
        ? "Windows"
        : /Mac OS X/.test(ua)
          ? "macOS"
          : /Android/.test(ua)
            ? "Android"
            : /iPhone|iPad/.test(ua)
              ? "iOS"
              : /Linux/.test(ua)
                ? "Linux"
                : "Unknown";

  return `${browser} / ${os}`;
};

/**
 * [GET] /api/system/adminuser/[email]/session
 * 특정 사용자의 활성 세션 목록 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { email } = params;

  try {
    const user = await prisma.user.findUnique({ where: { email }, select: { id: true } });
    if (!user) return createErrorResponse({ message: "사용자를 찾을 수 없습니다." }, operation);

    const sessions = await prisma.baSession.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "desc" },
    });

    // raw token 은 쿠키 값 그 자체라 응답에서 절대 노출 금지 (impersonation 방지). revoke 는 id 로.
    const items = sessions.map((s, index) => ({
      rn: index + 1,
      id: s.id,
      ipAddress: s.ipAddress ?? "-",
      userAgent: parseUserAgent(s.userAgent ?? "-"),
      createdAt: s.createdAt,
      expiresAt: s.expiresAt,
    }));

    return createSuccessResponse({ items, total_count: items.length });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { scopeEmailParam: "email", requireOperatorOrAdmin: true });

/**
 * [DELETE] /api/system/adminuser/[email]/session?id=xxx
 * 특정 세션 강제 종료. id 는 BA_Session PK (UUID) — raw token 은 클라에 노출하지 않는다.
 */
const deleteHandler = async (req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";
  const { email } = params;
  const { searchParams } = new URL(req.url);
  const id = searchParams.get("id");

  try {
    if (!id) return createErrorResponse({ message: "세션 ID 가 필요합니다." }, operation);

    const targetSession = await prisma.baSession.findUnique({
      where: { id },
      include: { user: { select: { email: true } } },
    });

    if (!targetSession || targetSession.user.email !== email) {
      return createErrorResponse({ message: "세션을 찾을 수 없습니다." }, operation);
    }

    await prisma.baSession.delete({ where: { id } });

    return createSuccessResponse({ message: "세션이 강제 종료되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, { scopeEmailParam: "email", requireOperatorOrAdmin: true });
