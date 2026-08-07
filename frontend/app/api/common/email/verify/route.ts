import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { prisma } from "@/lib/prisma/client";
import { emailVerificationOtpIdentifier, normalizeEmail } from "@/lib/auth/authUtils";

export async function POST(request: NextRequest) {
  // 본문 파싱 실패를 그대로 빠져나가게 두면 Next 가 500 으로 응답한다 — 같은 가입 흐름 위의
  // 발송 라우트(email/route.ts)는 이미 `.catch(() => null)` 로 막고 있었다(#388 과 같은 클래스).
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ result: false }, { status: 400 });
  }
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ result: false }, { status: 400 });
  }

  const { otp, email: rawEmail } = body as Record<string, unknown>;
  // 발송 라우트(email/route.ts)가 이 정규화 값으로 identifier 를 저장했다 — 같은 규칙으로
  // 다시 조립해야 대소문자가 다른 재입력도 같은 레코드를 찾는다.
  const email = typeof rawEmail === "string" ? normalizeEmail(rawEmail) : "";

  // otp 타입 가드가 없으면 아래 `createHash(...).update(otp)` 가 문자열 아닌 값에 TypeError 를
  // 던지고(실측: `The "data" argument must be of type string ...`) 그게 500 이 된다.
  if (!email || typeof otp !== "string" || !otp) return NextResponse.json({ result: false });

  const identifier = emailVerificationOtpIdentifier(email);
  const record = await prisma.baVerification.findFirst({ where: { identifier } });

  if (!record) return NextResponse.json({ result: false });

  if (record.expiresAt < new Date()) {
    await prisma.baVerification.delete({ where: { id: record.id } });
    return NextResponse.json({ result: false });
  }

  const [storedHash, attemptsStr] = record.value.split(":");
  const attempts = parseInt(attemptsStr || "0");

  if (attempts >= 3) {
    await prisma.baVerification.delete({ where: { id: record.id } });
    return NextResponse.json({ result: false });
  }

  const inputHash = crypto.createHash("sha256").update(otp).digest("base64url");

  if (inputHash !== storedHash) {
    await prisma.baVerification.update({
      where: { id: record.id },
      data: { value: `${storedHash}:${attempts + 1}` },
    });
    return NextResponse.json({ result: false });
  }

  await prisma.baVerification.delete({ where: { id: record.id } });
  return NextResponse.json({ result: true });
}
