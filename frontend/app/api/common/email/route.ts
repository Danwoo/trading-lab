import { env } from "@/env";
import { NextRequest, NextResponse } from "next/server";
import nodemailer from "nodemailer";
import crypto from "crypto";
import path from "path";
import dns from "dns/promises";
import { prisma } from "@/lib/prisma/client";
import { getClientIp, rateLimit } from "@/lib/rateLimit";
import { emailVerificationOtpIdentifier, normalizeEmail } from "@/lib/auth/authUtils";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// SMTP 를 설정하지 않은 개발 환경에서는 메일 대신 서버 콘솔에 코드를 찍는다 — 메일 서버 없이 가입까지 도달하게.
// 운영에서는 EMAIL_HOST 가 비어도 이 경로를 타지 않는다 (코드가 콘솔로 새는 것을 막는다).
const isConsoleOtpMode = env.NODE_ENV !== "production" && !env.EMAIL_HOST;

function toFriendlyEmailError(message: string): string {
  if (
    /user.*unavailable|account.*unavailable|no such user|user.*not.*exist|does not exist|unknown user|invalid.*mailbox/i.test(
      message,
    )
  )
    return `존재하지 않는 이메일 주소입니다.\n주소를 다시 확인해주세요.`;
  if (/rejected|denied|not allowed/i.test(message)) return `수신 거부된 이메일 주소입니다.`;
  if (/connect|timeout|ECONNREFUSED|ETIMEDOUT/i.test(message))
    return `메일 서버에 연결할 수 없습니다.\n잠시 후 다시 시도해주세요.`;
  if (/authentication|auth|credentials/i.test(message))
    return `메일 서버 인증에 실패했습니다.\n관리자에게 문의해주세요.`;
  return `이메일 발송에 실패했습니다.\n주소를 확인하거나 잠시 후 다시 시도해주세요.`;
}

// 가입 전(pre-auth) OTP 발송 엔드포인트라 withAuth 미적용 — 세션이 없는 회원가입 흐름에서 호출됨.
// 남용 방어는 (1) 호출자 HTML 주입 제거(서버 템플릿만 렌더 → 피싱 릴레이 차단), (2) 수신자 검증, (3) IP·수신자 rate limit 로 대체.
export async function POST(request: NextRequest) {
  const ip = getClientIp(request);
  if (!rateLimit(`email:ip:${ip}`, 5, 60_000)) {
    return NextResponse.json({ message: `요청이 너무 많습니다.\n잠시 후 다시 시도해주세요.` }, { status: 429 });
  }

  const body = await request.json().catch(() => null);
  // OTP 저장 키(BaVerification.identifier)·이메일로그 수신자가 이 값을 그대로 쓴다 — 검증 라우트도
  // 같은 규칙(normalizeEmail)을 통과시켜야 대문자로 받은 OTP 를 소문자 입력으로 검증할 수 있다 (#250 계열).
  const to = typeof body?.to === "string" ? normalizeEmail(body.to) : "";

  if (!to || to.length > 254 || !EMAIL_REGEX.test(to)) {
    return NextResponse.json(
      { message: `유효하지 않은 이메일 주소입니다.\n주소를 다시 확인해주세요.` },
      { status: 400 },
    );
  }
  if (!rateLimit(`email:to:${to}`, 3, 60_000)) {
    return NextResponse.json({ message: `요청이 너무 많습니다.\n잠시 후 다시 시도해주세요.` }, { status: 429 });
  }

  // 6자리 랜덤 OTP 생성
  const otp = crypto
    .randomBytes(4)
    .toString("base64")
    .replace(/[^a-zA-Z0-9]/g, "")
    .slice(0, 6);

  // SHA-256으로 해싱 (BA emailOtp 플러그인과 동일한 포맷)
  const hashedOTP = crypto.createHash("sha256").update(otp).digest("base64url");

  // MX 레코드 검증
  const domain = to.split("@")[1];
  const subject = `[ACME] 인증 코드: ${otp}`;
  // 콘솔 모드에서는 DNS 를 타지 않는다 — 오프라인 개발에서도 가입이 뚫려야 한다.
  if (!isConsoleOtpMode) {
    try {
      const mxRecords = await dns.resolveMx(domain);
      if (!mxRecords || mxRecords.length === 0) throw new Error(`No MX records found for domain: ${domain}`);
    } catch (e) {
      const rawError = e instanceof Error ? e.message : String(e);
      await prisma.emailLog.create({
        data: { to, subject, status: "FAIL", error_msg: rawError, reg_dt: new Date() },
      });
      return NextResponse.json(
        { message: `유효하지 않은 이메일 도메인입니다.\n이메일 주소를 다시 확인해주세요.` },
        { status: 400 },
      );
    }
  }

  // BaVerification 테이블에 OTP 저장 (BA emailOtp 포맷: `${hash}:${attempts}`)
  const identifier = emailVerificationOtpIdentifier(to);
  await prisma.baVerification.deleteMany({ where: { identifier } });
  await prisma.baVerification.create({
    data: {
      id: crypto.randomUUID(),
      identifier,
      value: `${hashedOTP}:0`,
      expiresAt: new Date(Date.now() + 15 * 60 * 1000),
      createdAt: new Date(),
      updatedAt: new Date(),
    },
  });

  // 발신 메일은 서버 고정 템플릿만 렌더 — 호출자 제공 HTML 은 주입하지 않음
  const instruction = "해당 코드를 복사 후, 붙여넣기 해주세요.";
  let mailTemplate = "";
  mailTemplate +=
    '<table style="width:100%;max-width:800px;background:#F5F7FC;text-align:center;margin:0 auto;padding:30px 0 40px;">';
  mailTemplate += '<tr><td><img src="cid:logo" style="height:100px;margin-top:40px;margin-bottom:40px;"></td></tr>';
  mailTemplate +=
    '<tr><td><div style="border-radius:20px;width:100%;max-width:450px;background:#ffffff;margin:0 auto;padding:24px 20px 28px;">';
  mailTemplate += '<div style="color:#303F67;font-size:52px;font-weight:bold;letter-spacing:6px;">' + otp + "</div>";
  mailTemplate +=
    '<div style="display:inline-block;background:#EEF2FF;color:#303F67;padding:6px 16px;border-radius:8px;margin-top:14px;font-size:14px;">' +
    instruction +
    "</div>";
  mailTemplate += "</div></td></tr>";
  mailTemplate += "</table>";

  const mailOptions = {
    from: env.EMAIL_USER,
    to,
    subject,
    html: mailTemplate,
    attachments: [
      {
        filename: "logo.png",
        path: path.join(process.cwd(), "public/logo.png"),
        cid: "logo",
      },
    ],
  };

  if (isConsoleOtpMode) {
    console.info(`[dev] SMTP 미설정 — ${to} 인증 코드: ${otp}`);
    await prisma.emailLog.create({
      data: { to, subject, status: "CONSOLE", reg_dt: new Date() },
    });
    return NextResponse.json({ message: "Email sent successfully" });
  }

  const transporter = nodemailer.createTransport({
    host: env.EMAIL_HOST,
    port: Number(env.EMAIL_PORT),
    secure: true,
    auth: {
      user: env.EMAIL_USER,
      pass: env.EMAIL_PASSWORD,
    },
  });

  try {
    await transporter.sendMail(mailOptions);
    await prisma.emailLog.create({
      data: { to, subject, status: "SUCCESS", reg_dt: new Date() },
    });
    return NextResponse.json({ message: "Email sent successfully" });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    await prisma.emailLog.create({
      data: { to, subject, status: "FAIL", error_msg: errorMessage, reg_dt: new Date() },
    });
    return NextResponse.json({ message: toFriendlyEmailError(errorMessage) }, { status: 500 });
  }
}
