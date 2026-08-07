// app/api/common/system/adminuser/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";
import { auth } from "@/lib/auth/auth";
import { isOEM } from "@/utils/common/edition";
import {
  assertAssignableWorkspace,
  deleteHalfCreatedUser,
  normalizeEmail,
  resolveOemSharedWorkspace,
  syncDefaultWorkspaceMembership,
  workspaceScopedUserWhere,
} from "@/lib/auth/authUtils";

/**
 * [GET] /api/system/adminuser
 * 관리자용 사용자 목록 조회 (서버사이드 페이징)
 */
const getHandler = async (req: NextRequest, session: any) => {
  const operation = "GET";

  try {
    const { searchParams } = new URL(req.url);
    const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
    const skip = searchParams.get("skip") ? parseInt(searchParams.get("skip")!) : undefined;
    const filter = searchParams.get("filter");
    const sort = searchParams.get("sort");

    // 운영자는 자기 워크스페이스 사용자만 조회 가능 (시스템관리자는 전체). workspaceId null 이면 -1 로 fail-closed.
    // 소속 판정은 단건 가드(assertSameWorkspaceOrSysAdmin)와 같은 술어를 쓴다 — 갈리면 목록에는
    // 보이는데 열면 "사용자를 찾을 수 없습니다"가 되는 행이 생긴다.
    // 사용자 필터를 AND 로 묶어 클라가 보낸 filter 키가 tenantWhere 를 덮어쓰지 못하게 한다 (테넌트 격리 우회 방지).
    const tenantWhere = session.user.isSysAdmin ? {} : workspaceScopedUserWhere(session.user.workspaceId ?? -1);
    const userFilter = convertFilterToPrismaWhere(filter);
    const where = Object.keys(userFilter).length > 0 ? { AND: [tenantWhere, userFilter] } : tenantWhere;
    const orderBy = convertSortToPrismaOrderBy(sort) || [{ workspace: { workspace_nm: "asc" } }, { reg_dt: "desc" }];

    const [list, total_count] = await Promise.all([
      prisma.user.findMany({
        where,
        orderBy,
        take,
        skip,
        select: {
          id: true,
          email: true,
          name: true,
          dept: true,
          workspace_id: true,
          use_at: true,
          appr_at: true,
          reg_dt: true,
          reg_id: true,
          mod_dt: true,
          mod_id: true,
          author_members: { select: { author_id: true, author: { select: { author_nm: true } } } },
          workspace: { select: { workspace_nm: true } },
        },
      }),
      prisma.user.count({ where }),
    ]);

    const items = list.map((item, index) => ({
      ...item,
      rn: (skip || 0) + index + 1,
      author_nm: item.author_members.map((m) => m.author.author_nm).join(", "),
      workspace_nm: item.workspace?.workspace_nm ?? null,
      author_members: undefined,
      workspace: undefined,
    }));

    return createSuccessResponse({ items, total_count });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { requireOperatorOrAdmin: true });

/**
 * [POST] /api/system/adminuser
 * 관리자용 사용자 생성
 */
const postHandler = async (req: NextRequest, session: any) => {
  const operation = "POST";
  const data = await req.json();
  const { password, name, dept, use_at, appr_at } = data;
  // 이후 이메일은 저장·조회·감사컬럼 전부 이 정규화 값만 쓴다 — signup 라우트와 같은 규칙 (#250).
  const email = normalizeEmail(typeof data.email === "string" ? data.email : "");

  // workspace_id 결정. OEM 은 단일 활성 공용 워크스페이스로 강제(클라/세션 무시), SaaS 는 운영자만 자기 워크스페이스로 강제.
  let workspace_id: number | null;
  if (isOEM()) {
    // 판정은 signup 과 같은 함수를 쓴다 — 두 벌로 두면 한쪽만 고쳐져 갈린다.
    const shared = await resolveOemSharedWorkspace();
    if ("error" in shared) {
      return createErrorResponse({ message: shared.error }, operation);
    }
    workspace_id = shared.id;
  } else {
    workspace_id = session.user.isSysAdmin ? (data.workspace_id ?? null) : (session.user.workspaceId ?? null);
  }

  try {
    // 클라가 보낸 workspace_id 는 여기서 한 번 검증한다 — 드롭다운은 활성 공용 워크스페이스만
    // 주지만 API 는 그 필터를 안 거쳐, 남의 **개인** 워크스페이스 id 를 그대로 받아 배정했다 (#362).
    const workspaceMsg = await assertAssignableWorkspace(workspace_id);
    if (workspaceMsg) return createErrorResponse({ message: workspaceMsg }, operation);

    const existing = await prisma.user.findUnique({ where: { email }, select: { email: true } });
    if (existing) {
      return createErrorResponse({ message: `이미 사용 중인 이메일입니다. (${email})` }, operation);
    }

    const now = new Date();

    // Better Auth로 사용자 생성 (TN_User + BA_Account). Better Auth 는 자기 어댑터로 쓰므로
    // 아래 트랜잭션에 넣을 수 없다 — 뒤가 실패하면 이 조각은 보상 삭제로 되돌린다 (signup 과 같은 패턴).
    const signedUp = await auth.api.signUpEmail({
      body: { email, password, name: name || email },
    });
    const userId = signedUp.user.id;

    // 이미 가입된 이메일이면 Better Auth 는 (계정 열거 방지) 행을 만들지 않고 가짜 사용자를 돌려준다.
    // 위 중복 확인과 이 사이 경합으로 같은 이메일이 들어온 경우가 여기 걸린다.
    const createdUser = await prisma.user.findUnique({ where: { id: userId }, select: { id: true } });
    if (!createdUser) {
      return createErrorResponse({ message: `이미 사용 중인 이메일입니다. (${email})` }, operation);
    }

    try {
      await prisma.$transaction(async (tx) => {
        // 커스텀 필드 업데이트
        await tx.user.update({
          where: { id: userId },
          data: {
            dept: dept || null,
            workspace_id,
            use_at,
            appr_at,
            reg_dt: now,
            reg_id: session.user.email,
            mod_dt: now,
            mod_id: session.user.email,
          },
        });

        await syncDefaultWorkspaceMembership(userId, workspace_id, session.user.email, "member", tx);
      });
    } catch (error) {
      await deleteHalfCreatedUser(userId).catch((rollbackError) =>
        console.error("Adminuser 생성 롤백 실패, 반쪽 계정이 남았습니다:", userId, rollbackError),
      );
      throw error;
    }

    return createSuccessResponse({ message: "사용자가 생성되었습니다.", data: { email } });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const POST = withAuth(postHandler, { requireOperatorOrAdmin: true });
