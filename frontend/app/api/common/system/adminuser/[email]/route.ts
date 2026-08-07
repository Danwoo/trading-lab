// app/api/common/system/adminuser/[email]/route.ts
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { createSuccessResponse, createErrorResponse } from "@/utils/common/api/responses";
import {
  assertAssignableWorkspace,
  hashPassword,
  invalidateUserSessions,
  checkLastActiveSysAdmin,
  deleteUserCascade,
  syncDefaultWorkspaceMembership,
} from "@/lib/auth/authUtils";
import { GENERAL_ADMIN_AUTHOR_ID, DEFAULT_USER_AUTHOR_ID } from "@/constants/protected";
import { AdminUserUpdateInSchema } from "@/schemas/common/adminUser";

/**
 * [GET] /api/system/adminuser/[email]
 * 사용자 상세 조회
 */
const getHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "GET";
  const { email } = params;

  try {
    const user = await prisma.user.findUnique({
      where: { email },
      select: {
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
        workspace: { select: { workspace_nm: true } },
      },
    });

    if (!user) {
      return createErrorResponse({ message: "사용자를 찾을 수 없습니다." }, operation);
    }

    return createSuccessResponse({
      ...user,
      workspace_nm: user.workspace?.workspace_nm ?? null,
      workspace: undefined,
    });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler, { scopeEmailParam: "email", requireOperatorOrAdmin: true });

/**
 * [PUT] /api/system/adminuser/[email]
 * 사용자 수정 (관리자용)
 *
 * **PUT = 전체 표현**이다 (#400). 본문을 `AdminUserUpdateInSchema`(클라이언트 `adminUserService`
 * 가 보내기 전에 쓰는 것과 **같은 스키마**)로 경계에서 파싱하고, 그 결과만 `update` 에 싣는다.
 * 필수 필드(`use_at`·`appr_at`)가 빠진 본문은 400 이고, 선택 필드(`name`·`dept`·`workspace_id`)의
 * 생략은 **명시적 null**(값 지움)이다 — 한 update 안에서 어떤 필드는 생략=무시(Prisma undefined),
 * 어떤 필드는 생략=삭제(`?? null`)로 갈리던 것을 한 계약으로 모은다.
 *
 * 부분 갱신(PATCH)이 아니라 전체 교체(PUT)를 고른 근거:
 * - 라우트도 클라이언트(`adminUserService.updateAdminUser`)도 이미 PUT 이고, 폼은 `formData` 를
 *   통째로 보낸다.
 * - `lib/zod/helpers.ts` 의 `Optional` 이 빈 값(`null`·`""`)을 `undefined` 로 바꾸고 `JSON.stringify`
 *   가 그 키를 떨어뜨리므로, **클라이언트는 명시적 null 을 표현할 수단이 없다** — "생략 = 값 없음"
 *   이 실제 계약이다. 여기서 PATCH 의미(생략=건드리지 않음)를 택하면 화면에서 워크스페이스·부서를
 *   비우는 조작이 조용히 무시된다.
 * - 이슈가 지적한 사고 경로("이름만 고치려던 PUT 이 배정 해제 + 권한 강등 + 강제 로그아웃")는
 *   이 경계 검증이 닫는다: `{name}` 만 담은 본문은 `use_at`·`appr_at` 누락으로 **400** 이라
 *   `workspace_id` 연쇄까지 가지 못한다.
 *
 * 파싱은 `workspace_id` 의 타입 검증도 겸한다 — 예전엔 요청 본문의 값이 검증 없이
 * `assertAssignableWorkspace` 를 거쳐 `where.id` 에 들어가, Prisma 필터 객체(`{gt:0}`)를 넣으면
 * 존재 확인이 "요청한 그 워크스페이스"가 아니라 "조건에 맞는 아무 워크스페이스"를 찾았다
 * (#400 코멘트 — 종단은 Prisma 가 우연히 막고 있었다).
 */
const putHandler = async (req: NextRequest, session: any, params: any) => {
  const operation = "PUT";
  const { email } = params;

  try {
    // 본문 읽기를 try 안으로 넣는다 — 예전엔 try 밖이라 JSON 이 아닌 본문 하나가 그대로 500 이 됐다.
    let body: unknown;
    try {
      body = await req.json();
    } catch {
      return createErrorResponse({ message: "요청 본문을 읽을 수 없습니다." }, operation);
    }

    const parsed = AdminUserUpdateInSchema.safeParse(body);
    if (!parsed.success) {
      const issue = parsed.error.issues[0];
      return createErrorResponse(
        { message: `요청 본문이 올바르지 않습니다: ${issue.path.join(".") || "body"} — ${issue.message}` },
        operation,
      );
    }
    const data: Record<string, any> = { ...parsed.data };

    const existing = await prisma.user.findUnique({
      where: { email },
      select: { workspace_id: true, use_at: true, appr_at: true },
    });

    // 워크스페이스 격리 + 시스템관리자 계정 보호는 withAuth(scopeEmailParam/protectSysAdminTarget) 가 처리.
    // 여기선 워크스페이스 이동을 시스템관리자 전용으로 묶는다 — 운영자에겐 대상의 현재 값을 그대로 쓴다.
    // (요청자 워크스페이스로 "고정"하면 수정 한 번이 사용자를 요청자 쪽으로 끌어오는 수단이 된다.)
    if (!session.user.isSysAdmin) {
      if (data.workspace_id != null && data.workspace_id !== existing?.workspace_id) {
        return createErrorResponse({ message: "다른 워크스페이스로 이동할 수 없습니다." }, operation);
      }
      data.workspace_id = existing?.workspace_id ?? null;
    }

    // 워크스페이스를 **옮기는** 경우에만 대상 워크스페이스를 검증한다 — 생성 라우트와 같은 구멍이
    // 이 수정 경로에도 있었다: 시스템관리자가 본문에 남의 개인 워크스페이스 id 를 넣으면 기존
    // 사용자를 그리로 끌어갈 수 있었다 (#362 의 같은 클래스). 값이 그대로면 검증하지 않는다 —
    // 이미 비활성화된 워크스페이스에 있는 계정의 이름·승인 상태 수정까지 막을 이유는 없다.
    if ((data.workspace_id ?? null) !== (existing?.workspace_id ?? null)) {
      const workspaceMsg = await assertAssignableWorkspace(data.workspace_id ?? null);
      if (workspaceMsg) return createErrorResponse({ message: workspaceMsg }, operation);
    }

    const willBeInactive = (data.use_at && data.use_at !== "Y") || (data.appr_at && data.appr_at !== "Y");
    if (willBeInactive) {
      const guardMsg = await checkLastActiveSysAdmin(email);
      if (guardMsg) return createErrorResponse({ message: guardMsg }, operation);
    }

    // 비밀번호 변경 시 BA_Account 업데이트
    if (data.password) {
      const existingUser = await prisma.user.findUnique({ where: { email } });
      if (existingUser) {
        await prisma.baAccount.updateMany({
          where: { userId: existingUser.id, providerId: "credential" },
          data: { password: await hashPassword(data.password) },
        });
      }
    }

    const user = await prisma.user.update({
      where: { email },
      data: {
        // 전체 표현 — 선택 필드의 생략은 명시적 null 이다 (위 PUT 계약 주석).
        name: data.name ?? null,
        dept: data.dept ?? null,
        workspace_id: data.workspace_id ?? null,
        use_at: data.use_at,
        appr_at: data.appr_at,
        mod_id: session.user.email,
        mod_dt: new Date(),
      },
      select: {
        id: true,
        email: true,
        name: true,
        dept: true,
        workspace_id: true,
        use_at: true,
        appr_at: true,
        reg_dt: true,
        mod_dt: true,
      },
    });

    await syncDefaultWorkspaceMembership(user.id, user.workspace_id, session.user.email);

    // 워크스페이스 변경 시 이전 워크스페이스 종속인 일반관리자(002) 제거 (시스템관리자(001)는 워크스페이스 무관 유지).
    const workspaceChanged = existing && existing.workspace_id !== user.workspace_id;
    if (workspaceChanged) {
      await prisma.authorMember.deleteMany({
        where: { user_id: email, author_id: GENERAL_ADMIN_AUTHOR_ID },
      });
    }

    // 워크스페이스 배정(SaaS) 또는 승인 전환(OEM, appr_at N→Y) 시 일반사용자(003) 권한이 없으면 부여 → 즉시 사용 가능.
    const approvedNow = existing && existing.appr_at !== "Y" && user.appr_at === "Y";
    if (workspaceChanged || approvedNow) {
      const hasDefault = await prisma.authorMember.count({
        where: { user_id: email, author_id: DEFAULT_USER_AUTHOR_ID },
      });
      if (!hasDefault) {
        await prisma.authorMember.create({
          data: {
            author_id: DEFAULT_USER_AUTHOR_ID,
            user_id: email,
            reg_id: session.user.email,
            reg_dt: new Date(),
            mod_id: session.user.email,
            mod_dt: new Date(),
          },
        });
      }
    }

    // 워크스페이스 변경 or 비활성 처리 시 기존 세션 무효화 (JWT/BaSession stale 방지)
    const becameInactive = data.use_at === "N" || data.appr_at !== "Y";
    if (workspaceChanged || becameInactive) {
      await invalidateUserSessions(email);
    }

    const { id: _id, ...responseUser } = user;
    return createSuccessResponse({ message: "사용자 정보가 수정되었습니다.", data: responseUser });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const PUT = withAuth(putHandler, {
  scopeEmailParam: "email",
  protectSysAdminTarget: true,
  requireOperatorOrAdmin: true,
});

/**
 * [DELETE] /api/system/adminuser/[email]
 * 사용자 삭제 (관련 세션, 권한 멤버 연쇄 삭제)
 */
const deleteHandler = async (_req: NextRequest, _session: any, params: any) => {
  const operation = "DELETE";
  const { email } = params;

  try {
    // 워크스페이스 격리 + 시스템관리자 계정 보호는 withAuth(scopeEmailParam/protectSysAdminTarget) 가 처리.
    const guardMsg = await checkLastActiveSysAdmin(email);
    if (guardMsg) return createErrorResponse({ message: guardMsg }, operation);

    // 자식 행(멤버십·세션·계정·권한)까지의 삭제 순서는 회원탈퇴 경로와 공유한다 — 두 벌로 두면 갈린다.
    await deleteUserCascade(email);

    return createSuccessResponse({ message: "사용자가 삭제되었습니다." });
  } catch (error: any) {
    console.error(`[${operation}] Error:`, error);
    return createErrorResponse(error, operation);
  }
};

export const DELETE = withAuth(deleteHandler, {
  scopeEmailParam: "email",
  protectSysAdminTarget: true,
  requireOperatorOrAdmin: true,
});
