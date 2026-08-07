import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest, NextResponse } from "next/server";
import { deleteUserCascade, hashPassword } from "@/lib/auth/authUtils";
import { prisma } from "@/lib/prisma/client";
import { SYS_ADMIN_AUTHOR_ID } from "@/constants/protected";

// DELETE 핸들러 (회원탈퇴)
const deleteHandler = async (req: NextRequest, session: any, params?: any) => {
  try {
    const userEmail = session.user.email;

    const isSysAdmin = await prisma.authorMember.findFirst({
      where: { author_id: SYS_ADMIN_AUTHOR_ID, user_id: userEmail },
      include: { user: { select: { use_at: true, appr_at: true } } },
    });
    if (isSysAdmin?.user?.use_at === "Y" && isSysAdmin?.user?.appr_at === "Y") {
      const activeCount = await prisma.authorMember.count({
        where: { author_id: SYS_ADMIN_AUTHOR_ID, user: { use_at: "Y", appr_at: "Y" } },
      });
      if (activeCount <= 1) {
        return NextResponse.json(
          { error: "시스템관리자 권한에는\n승인된 활성 사용자가 최소 1명 있어야 합니다." },
          { status: 400 },
        );
      }
    }

    // 자식 행(멤버십·세션·계정·권한)까지의 삭제 순서는 관리자 삭제 경로와 공유한다 — 두 벌로 두면 갈린다.
    await deleteUserCascade(userEmail);

    return NextResponse.json({
      message: "회원탈퇴가 완료되었습니다.",
      success: true,
    });
  } catch (error) {
    return NextResponse.json({ error: "회원탈퇴 처리 중 오류가 발생했습니다." }, { status: 500 });
  }
};

// GET 핸들러 (사용자 정보 조회)
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  try {
    // 세션에서 직접 이메일 추출
    const email = session.user.email;

    if (!email) {
      return NextResponse.json({ error: "세션에서 사용자 이메일을 찾을 수 없습니다." }, { status: 400 });
    }

    const resultList = await prisma.user.findMany({
      where: {
        email: email,
      },
      select: {
        email: true,
        name: true,
        dept: true,
        workspace_id: true,
        workspace: { select: { workspace_nm: true } },
        // 민감한 정보는 제외
      },
      take: 1,
    });

    if (resultList.length === 0) {
      return NextResponse.json({
        result: false,
        message: "사용자를 찾을 수 없습니다.",
      });
    } else {
      const items = resultList.map(({ workspace, ...rest }) => ({
        ...rest,
        workspace_nm: workspace?.workspace_nm ?? null,
      }));
      return NextResponse.json({
        result: true,
        resultList: items,
      });
    }
  } catch (error) {
    console.error("GET user error:", error);
    return NextResponse.json({ error: "서버 내부 오류가 발생했습니다." }, { status: 500 });
  }
};

// PATCH 핸들러 (사용자 정보 수정)
//
// 이름은 PATCH 지만 본문 계약은 **전체 표현**이다 (#400 — `adminuser/[email]/route.ts` 의 PUT
// 주석과 같은 결정): 클라이언트 타입 `UpdateUserIn` 이 `email`·`name`·`dept` 를 모두 필수로 두고,
// 화면(`Mypage.tsx`)도 셋을 항상 싣는다. 그래서 `dept` 생략은 "건드리지 않음"이 아니라 값 지움인데,
// 검증이 `name` 에만 있어 계약이 필드마다 갈려 있었다 — `dept` 가 빠진 본문은 조용히 부서를
// 지우는 대신 거절한다. 빈 문자열(`""`)은 정상 입력이고 null 로 저장된다("부서 없음").
const patchHandler = async (req: NextRequest, session: any, params?: any) => {
  try {
    const { email, password, name, dept } = await req.json();

    // 세션에서 이메일 추출
    const sessionEmail = session.user.email;

    // 입력 검증
    if (typeof dept !== "string") {
      return NextResponse.json({
        result: false,
        name: "dept",
        message: "부서는 문자열로 함께 보내야 합니다 (비우려면 빈 문자열).",
      });
    }

    if (!name || typeof name !== "string" || name.trim().length < 2) {
      return NextResponse.json({
        result: false,
        name: "name",
        message: "이름은 2자 이상이어야 합니다.",
      });
    }

    // 타입 가드가 먼저다 — 숫자를 보내면 `password.trim` 이 없어 TypeError 가 나고 그게 500 으로
    // 샌다 (#388 이 signup 에서 고친 것과 같은 축).
    if (password && (typeof password !== "string" || password.trim().length < 8)) {
      return NextResponse.json({
        result: false,
        name: "password",
        message: "비밀번호는 8자 이상이어야 합니다.",
      });
    }

    // 권한 체크 (자신의 정보만 수정 가능) - 세션 이메일과 요청 이메일 비교
    if (sessionEmail !== email) {
      return NextResponse.json({ error: "권한이 없습니다." }, { status: 403 });
    }

    // 사용자 존재 확인 (세션 이메일로)
    const existingUser = await prisma.user.findUnique({
      where: {
        email: sessionEmail,
      },
    });

    if (!existingUser) {
      return NextResponse.json({
        result: false,
        message: "사용자를 찾을 수 없습니다.",
      });
    }

    // 업데이트 데이터 준비
    const updateData: any = {
      name: name.trim(),
      dept: dept.trim() || null,
      mod_dt: new Date(),
      mod_id: sessionEmail,
    };

    // 비밀번호가 제공된 경우 BA_Account 업데이트
    if (password) {
      const hashedPassword = await hashPassword(password);
      await prisma.baAccount.updateMany({
        where: { userId: existingUser.id, providerId: "credential" },
        data: { password: hashedPassword },
      });
    }

    // 사용자 정보 업데이트 (세션 이메일로)
    const updatedUser = await prisma.user.update({
      where: { email: sessionEmail },
      data: updateData,
    });

    if (updatedUser) {
      return NextResponse.json({
        result: true,
        message: "사용자 정보가 성공적으로 업데이트되었습니다.",
      });
    } else {
      return NextResponse.json({
        result: false,
        message: "사용자 정보 업데이트에 실패했습니다.",
      });
    }
  } catch (error) {
    console.error("PATCH user error:", error);
    return NextResponse.json({ error: "서버 내부 오류가 발생했습니다." }, { status: 500 });
  }
};

export const GET = withAuth(getHandler);
export const PATCH = withAuth(patchHandler);
export const DELETE = withAuth(deleteHandler);
