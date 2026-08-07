// app/api/common/system/workspace/[workspace_id]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { workspaceScopedUserWhere } from "@/lib/auth/authUtils";

/**
 * [GET] /api/common/system/workspace/[workspace_id]
 * 워크스페이스 상세 조회
 */
const getHandler = async (req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const id = Number(params.workspace_id);

  try {
    const workspace = await prisma.workspace.findUnique({ where: { id } });
    if (!workspace) {
      return createErrorResponse({ message: "워크스페이스를 찾을 수 없습니다." }, operation);
    }

    return createSuccessResponse(workspace);
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireSysAdmin: true });

/**
 * [PUT] /api/common/system/workspace/[workspace_id]
 * 워크스페이스 수정
 */
const putHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "PUT";
  const id = Number(params.workspace_id);
  const data = await req.json();

  try {
    // 마지막 활성 공용 워크스페이스 비활성화 차단 — OEM 단일워크스페이스 self-lock(가입·사용자생성 전면 중단) 방지.
    // 개인 워크스페이스는 가입이 배정 대상으로 세지 않으므로(resolveOemSharedWorkspace) 여기서도 제외한다.
    if (data.use_at === "N") {
      const otherActive = await prisma.workspace.count({
        where: { use_at: "Y", is_personal: false, id: { not: id } },
      });
      if (otherActive === 0) {
        return createErrorResponse({ message: "마지막 활성 워크스페이스는 비활성화할 수 없습니다." }, operation);
      }
    }

    const workspace = await prisma.workspace.update({
      where: { id },
      data: {
        workspace_nm: data.workspace_nm,
        use_at: data.use_at,
        mod_id: session.user.email,
        mod_dt: new Date(),
      },
    });

    // 워크스페이스 비활성화 시 소속 사용자 전원 세션 무효화 → 다음 요청에서 로그인 차단됨.
    // 소속 판정은 관리 화면의 가드·목록과 같은 술어를 쓴다 — 스칼라만 훑으면 멤버십으로만 이 워크스페이스를
    // 보던 사용자의 세션이 살아남는다.
    if (data.use_at === "N") {
      const targets = await prisma.user.findMany({ where: workspaceScopedUserWhere(id), select: { id: true } });
      if (targets.length > 0) {
        await prisma.baSession.deleteMany({ where: { userId: { in: targets.map((u) => u.id) } } });
      }
    }

    return createSuccessResponse({ message: "워크스페이스 정보가 수정되었습니다.", data: workspace });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const PUT = withAuth(putHandler, { requireSysAdmin: true });

// DELETE 차단: 워크스페이스는 영구 보존. 폐쇄 시 use_at='N' 으로 soft delete — 그 워크스페이스 사용자 세션 자동 무효화 + 로그인 차단.
