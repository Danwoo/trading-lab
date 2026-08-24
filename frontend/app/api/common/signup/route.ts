import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma/client";
import { auth } from "@/lib/auth/auth";
import { GUEST_AUTHOR_ID, SIGNUP_AUTHOR_ID } from "@/constants/protected";
import { isOEM } from "@/utils/common/edition";
import { getClientIp, rateLimit } from "@/lib/rateLimit";
import { SIGNUP_EMAIL_PATTERN, signupRequestSchema } from "@/schemas/common/signup";
import {
  deleteHalfCreatedUser,
  ensurePersonalWorkspace,
  normalizeEmail,
  resolveOemSharedWorkspace,
  syncDefaultWorkspaceMembership,
} from "@/lib/auth/authUtils";
import { consumeSignupVerificationGrant } from "@/lib/auth/signupVerificationGrant";

export async function GET(req: NextRequest) {
  try {
    // 공개 이메일 존재 확인 — 열거(enumeration) 남용 방어를 위해 IP rate limit
    if (!rateLimit(`signup:check:${getClientIp(req)}`, 20, 60_000)) {
      return NextResponse.json({ result: false, name: "email" }, { status: 429 });
    }

    const { searchParams } = req.nextUrl;
    const getP1 = searchParams.get("p1");
    // Better Auth 는 저장·조회를 소문자로 맞춘다 — 여기도 같은 규칙을 통과시켜야 대문자 입력이
    // "존재하지 않음"으로 잘못 응답하지 않는다 (#250).
    const email = normalizeEmail(getP1 ?? "");

    if (!email || !SIGNUP_EMAIL_PATTERN.test(email)) {
      return NextResponse.json({ result: false, name: "email" });
    }

    // 이미 존재하는 이메일인지 확인
    const data = await prisma.user.findUnique({
      where: { email },
    });

    if (data) {
      return NextResponse.json({ result: true });
    } else {
      return NextResponse.json({ result: false });
    }
  } catch (error) {
    console.error("Email check error:", error);
    return new NextResponse("Internal Server Error!", { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const { headers } = req;
  const forwardedFor = headers.get("x-forwarded-for");
  const clientIp = forwardedFor ? forwardedFor.split(",")[0] : "unknown";

  // 본문 파싱은 try 안에 둔다 — 밖에 두면 깨진 JSON 이 그대로 빠져나가 Next 가 500 으로
  // 응답했다(#388). 본문이 JSON null·배열이어도 구조분해가 던졌다.
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ result: false, name: "body" }, { status: 400 });
  }
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ result: false, name: "body" }, { status: 400 });
  }

  const { email: rawEmail, password, name, dept: rawDept, verificationToken } = body as Record<string, unknown>;
  // 이후 이메일은 저장·조회·감사컬럼 전부 이 정규화 값만 쓴다 — Better Auth 가 저장하는 값과
  // 같은 규칙이라야 방금 만든 사용자를 바로 다음 줄에서 찾을 수 있다 (#250).
  const email = normalizeEmail(typeof rawEmail === "string" ? rawEmail : "");

  if (!email || !SIGNUP_EMAIL_PATTERN.test(email)) {
    return NextResponse.json({ result: false, name: "email" });
  }
  // 타입 가드가 먼저다 — 숫자를 보내면 `password.trim` 이 없어 TypeError 가 났고, 이 줄이
  // try 밖이라 그대로 500 이 됐다(#388).
  if (typeof password !== "string" || password.trim().length < 8) {
    return NextResponse.json({ result: false, name: "password" });
  }

  // 클라이언트 signupSchema 를 **필드 제외 없이** 요청 경계에서도 통과시킨다 — 규칙을 두 벌
  // 만들지 않는다. 클라이언트를 거치지 않고 API 를 직접 호출하면 이 검증이 없어 DB 가 P2000 을
  // (email·name·dept 길이), better-auth 가 PASSWORD_TOO_LONG 을(password 73자 이상) 던지고
  // 그게 전부 500 으로 샜다(#266·#388). 예전엔 `.omit({ password: true })` 로 password 를 빼고
  // `min 8` 만 위에서 손으로 재구현해 `max(72)` 가 버려져 있었다.
  // name 이 비어 있으면 기존과 같이 이메일로 대체한 뒤 검증한다.
  const resolvedName = typeof name === "string" && name.trim() ? name : email;
  const boundaryCheck = signupRequestSchema.safeParse({ email, password, name: resolvedName, dept: rawDept });
  if (!boundaryCheck.success) {
    const field = String(boundaryCheck.error.issues[0]?.path[0] ?? "name");
    return NextResponse.json({ result: false, name: field }, { status: 400 });
  }
  // 이후 저장에는 **검증을 통과한 값**만 쓴다 — 경계에서 확인한 것과 DB 로 나가는 것이 같아야 한다.
  const dept = boundaryCheck.data.dept;

  try {
    const data = await prisma.user.findUnique({
      where: { email },
    });

    if (data) {
      return NextResponse.json({ result: false, name: "email" });
    }

    // **이메일 소유 증명이 여기서 강제된다** (#343). 마법사 1단계는 리액트 상태일 뿐이라
    // 가입 API 를 직접 부르면 인증을 한 번도 통과하지 않고 계정이 만들어졌다. 검사를 화면이
    // 아니라 **계정을 만드는 자리**에 두어야, 마법사를 고쳐도 구멍이 다시 열리지 않는다.
    // 증거는 한 번만 쓰이고 여기서 소비된다 — 아래가 실패해 보상 삭제로 접히면 인증부터 다시 한다.
    if (!(await consumeSignupVerificationGrant(email, verificationToken))) {
      return NextResponse.json({ result: false, name: "verification" }, { status: 403 });
    }

    const oem = isOEM();
    // 에디션·도메인이 배정하는 공용 워크스페이스. 개인 워크스페이스와 별개다.
    let sharedWorkspaceId: number | null;
    let appr_at: string;
    let autoGrantRole: boolean;

    if (oem) {
      // OEM: 단일 워크스페이스 배포. 도메인 매핑 없이 DB 의 유일 활성 공용 워크스페이스로 배정, 항상 승인 대기.
      const shared = await resolveOemSharedWorkspace();
      if ("error" in shared) {
        return NextResponse.json({ message: shared.error }, { status: 500 });
      }
      sharedWorkspaceId = shared.id;
      appr_at = "N"; // 운영자 승인 대기
      autoGrantRole = false; // 권한은 운영자가 승인 시 부여
    } else {
      // SaaS: 이메일 도메인 → 공용 워크스페이스 자동 매핑 (워크스페이스 use_at='Y' 만 매칭).
      // 매핑 여부와 무관하게 개인 워크스페이스를 갖고 즉시 활성이므로, 배정 대기 경로는 없다.
      // email 이 이미 normalizeEmail 을 거쳤으므로 도메인도 소문자다 — 다시 낮출 필요 없다.
      const domain = email.split("@")[1] ?? "";
      const workspaceDomain = domain
        ? await prisma.workspaceDomain.findFirst({
            where: { domain, workspace: { use_at: "Y" } },
            select: { workspace_id: true },
          })
        : null;

      sharedWorkspaceId = workspaceDomain?.workspace_id ?? null;
      appr_at = "Y";
      autoGrantRole = true;
    }

    // Better Auth로 사용자 생성 (TN_User + BA_Account). Better Auth 는 자기 어댑터로 쓰므로
    // 아래 트랜잭션에 넣을 수 없다 — 뒤가 실패하면 이 조각은 보상 삭제(deleteHalfCreatedUser)로 되돌린다.
    let signedUp;
    try {
      signedUp = await auth.api.signUpEmail({
        body: { email, password, name: resolvedName },
      });
    } catch (error) {
      // Better Auth 는 사용자 생성 실패 원인을 구분해 주지 않고 전부 같은 FAILED_TO_CREATE_USER
      // 봉투(422)로 던진다(better-auth/dist/api/routes/sign-up.mjs) — 길이는 위에서 이미 걸렀으니
      // 남는 흔한 원인은 방금 findUnique 와 이 호출 사이 동시 가입 경합(email unique violation)이다
      // (#266). 다만 "그 이메일의 tn_user 행이 지금 존재하는가"만으로는 두 상황을 못 가른다 —
      // (A) 남이 경합에서 이겨 정상 가입을 마쳤다 / (B) 이 요청의 signUpEmail 자신이 tn_user 는
      // 만들고 그다음 내부 단계(ba_account 삽입 등)에서 던졌다. (B) 를 (A) 로 오인해 그대로
      // 접으면 그 행은 자격증명 없는 반쪽 계정으로 남고, 그 이메일은 로그인도 재가입도 영구히
      // 막힌다(#250 의 두 번째 증상 — 아래 트랜잭션 실패 블록이 deleteHalfCreatedUser 로 방어하는
      // 그 실패 부류를 여기서도 반복하는 셈이었다).
      // 판별자: 정상 가입이면 ba_account 행이 함께 있다 — 없으면 (B) 로 보고 기존 보상 삭제
      // 경로로 접는다. (경합 폭이 아주 좁을 때 남의 진행 중인 가입을 (B) 로 오판할 이론적 여지는
      // 남지만, better-auth 가 user·account 를 같은 호출 안에서 만들므로 그 창은 매우 좁다 —
      // better-auth 내부 실패 순서 자체는 이 환경에서 실행 검증하지 못했다.)
      const raceWinner = await prisma.user.findUnique({
        where: { email },
        select: { id: true, accounts: { select: { id: true }, take: 1 } },
      });
      if (raceWinner) {
        if (raceWinner.accounts.length === 0) {
          await deleteHalfCreatedUser(raceWinner.id).catch((rollbackError) =>
            console.error(
              "Signup rollback failed (signUpEmail 단계), half-created user left:",
              raceWinner.id,
              rollbackError,
            ),
          );
          throw error;
        }
        return NextResponse.json({ result: false, name: "email" });
      }
      throw error;
    }
    const userId = signedUp.user.id;

    // 이미 가입된 이메일이면 Better Auth 는 (계정 열거 방지) 행을 만들지 않고 가짜 사용자를 돌려준다.
    // 위 중복 확인과 이 사이 경합으로 같은 이메일이 들어온 경우가 여기 걸린다 — 남의 계정을 건드리지 않고 끝낸다.
    const createdUser = await prisma.user.findUnique({ where: { id: userId }, select: { id: true } });
    if (!createdUser) {
      return NextResponse.json({ result: false, name: "email" });
    }

    // 여기서부터 가입의 나머지(커스텀 필드·워크스페이스·멤버십·권한)는 전부이거나 전무다 — 도중에
    // 실패하면 워크스페이스도 승인도 없는 반쪽 계정이 남고, 그 이메일은 중복으로 막혀 재시도조차
    // 그것을 치울 수 없다 (#250 의 두 번째 증상).
    try {
      await prisma.$transaction(async (tx) => {
        // SaaS 는 가입하면 누구나 자기 개인 워크스페이스를 갖는다. OEM 은 구성원 전원이 고객사 공용
        // 워크스페이스 하나를 쓰는 배포 형태라 개인 워크스페이스를 만들지 않는다 (제품 형태의 차이).
        const personalWorkspaceId = oem ? null : await ensurePersonalWorkspace(userId, email, tx);

        // 도메인이 매핑되면 그 워크스페이스가 기본, 아니면 개인 워크스페이스가 기본이다.
        const workspace_id = sharedWorkspaceId ?? personalWorkspaceId;

        // 커스텀 필드 업데이트 (Better Auth가 모르는 필드)
        await tx.user.update({
          where: { id: userId },
          data: {
            dept: dept,
            workspace_id,
            appr_at,
            emailVerified: true,
            reg_id: email,
            reg_ip: clientIp.replace(/^::ffff:/, ""),
            reg_pid: "signup",
            mod_id: email,
            mod_ip: clientIp.replace(/^::ffff:/, ""),
            mod_pid: "signup",
          },
        });

        // 기본 워크스페이스 멤버십 — 세션이 이 행에서 "지금 선택된 워크스페이스"를 읽는다.
        await syncDefaultWorkspaceMembership(userId, workspace_id, email, "member", tx);

        // 즉시 활성인 가입자는 **자기** 워크스페이스의 운영자다 (리드 결정 2026-08-23, #341) —
        // 게스트를 주면 실험대·시세·관심종목의 저장·실행이 전부 403 이다.
        //
        // 도메인 매핑으로 **남의 공용 워크스페이스**에 들어간 가입은 그 전제(주인)가 서지 않는다.
        // 그 계정은 초대받은 손님이라 게스트를 주고, 쓰기를 열지는 그 워크스페이스 운영자가
        // 권한관리에서 판단한다 (결정 보완 2026-08-24 — `adminuser/[email]/route.ts` 가 남의
        // 워크스페이스에 사람을 넣을 때와 같은 원칙). 운영자를 주면 그 워크스페이스의 쓰기와
        // 사용자관리(같은 워크스페이스 계정의 수정·삭제)가 초대 없이 열린다.
        // OEM 은 승인 시 운영자가 부여.
        if (autoGrantRole) {
          await tx.authorMember.create({
            data: {
              author_id: sharedWorkspaceId === null ? SIGNUP_AUTHOR_ID : GUEST_AUTHOR_ID,
              user_id: email,
              reg_id: email,
              reg_dt: new Date(),
              mod_id: email,
              mod_dt: new Date(),
            },
          });
        }
      });
    } catch (error) {
      await deleteHalfCreatedUser(userId).catch((rollbackError) =>
        console.error("Signup rollback failed, half-created user left:", userId, rollbackError),
      );
      throw error;
    }

    return NextResponse.json({ result: true });
  } catch (error) {
    console.error("Signup error:", error);
    return new NextResponse("Internal Server Error!", { status: 500 });
  }
}
