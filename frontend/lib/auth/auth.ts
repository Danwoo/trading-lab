import { betterAuth, APIError } from "better-auth";
import { createAuthMiddleware } from "better-auth/api";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { jwt } from "better-auth/plugins";
import { prisma } from "@/lib/prisma/client";
import jsonwebtoken from "jsonwebtoken";
import nodemailer from "nodemailer";
import path from "path";
import { env } from "@/env";
import { resolveAccountContext } from "@/lib/auth/accountContext";
import { v7 as uuidv7 } from "uuid";

const JWT_SECRET = env.JWT_SECRET || "";
const JWT_EXPIRES_IN = 60; // 1분

export const auth = betterAuth({
  secret: env.BETTER_AUTH_SECRET,
  database: prismaAdapter(prisma, {
    provider: "postgresql",
  }),

  trustedOrigins: [
    "http://localhost:*",
    "http://127.0.0.1:*",
    env.BETTER_AUTH_URL,
    ...(env.BETTER_AUTH_TRUSTED_ORIGINS?.split(",")
      .map((o: string) => o.trim())
      .filter(Boolean) ?? []),
  ].filter(Boolean) as string[],

  advanced: {
    cookiePrefix: env.APP_KEY,
    database: {
      generateId: () => uuidv7(),
    },
  },

  emailAndPassword: {
    enabled: true,
    autoSignIn: false,
    minPasswordLength: 8,
    revokeSessionsOnPasswordReset: true,
    sendResetPassword: async ({ user, url }) => {
      const transporter = nodemailer.createTransport({
        host: env.EMAIL_HOST,
        port: Number(env.EMAIL_PORT),
        secure: true,
        auth: {
          user: env.EMAIL_USER,
          pass: env.EMAIL_PASSWORD,
        },
      });

      let mailTemplate = "";
      mailTemplate +=
        '<table style="width:100%;max-width:800px;background:#F5F7FC;text-align:center;margin:0 auto;padding:30px 0 40px;">';
      mailTemplate += '<tr><td><img src="cid:logo" style="height:100px;margin-top:40px;margin-bottom:40px;"></td></tr>';
      mailTemplate +=
        '<tr><td><div style="border-radius:20px;width:100%;max-width:450px;background:#ffffff;margin:0 auto;padding:24px 20px 28px;">';
      mailTemplate +=
        '<div style="color:#303F67;font-size:18px;font-weight:bold;margin-bottom:20px;">비밀번호 재설정을 요청하셨나요?</div>';
      mailTemplate += `<a href="${url}" style="display:inline-block;background:#303F67;color:#ffffff;padding:12px 32px;border-radius:8px;font-size:15px;font-weight:bold;text-decoration:none;">비밀번호 재설정</a>`;
      mailTemplate += '<div style="color:#7582A5;font-size:12px;margin-top:16px;">이 링크는 1시간 후 만료됩니다.</div>';
      mailTemplate += "</div></td></tr>";
      mailTemplate += "</table>";

      const subject = "[ACME] 비밀번호 재설정";
      try {
        await transporter.sendMail({
          from: env.EMAIL_USER,
          to: user.email,
          subject,
          html: mailTemplate,
          attachments: [
            {
              filename: "logo.png",
              path: path.join(process.cwd(), "public/logo.png"),
              cid: "logo",
            },
          ],
        });
        await prisma.emailLog.create({
          data: { to: user.email, subject, status: "SUCCESS", reg_dt: new Date() },
        });
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        await prisma.emailLog.create({
          data: { to: user.email, subject, status: "FAIL", error_msg: errorMessage, reg_dt: new Date() },
        });
      }
    },
  },

  user: {
    modelName: "User",
    fields: {
      createdAt: "reg_dt",
      updatedAt: "mod_dt",
    },
    additionalFields: {
      dept: { type: "string", required: false },
      workspace_id: { type: "number", required: false },
      use_at: { type: "string", required: false, defaultValue: "Y" },
      appr_at: { type: "string", required: false, defaultValue: "N" },
    },
  },

  databaseHooks: {
    user: {
      create: {
        before: async (user) => {
          const { createdAt, updatedAt, ...rest } = user as any;
          return { data: { ...rest, reg_dt: new Date(), mod_dt: new Date() } };
        },
      },
      update: {
        before: async (user) => {
          const { updatedAt, ...rest } = user as any;
          return { data: { ...rest, mod_dt: new Date() } };
        },
      },
    },
    session: {
      create: {
        before: async (session) => {
          // 로그인 시점의 판정도 요청마다 도는 판정(`withAuth`)과 **같은 함수**를 쓴다 — 두 벌로
          // 두면 갈린다 (#354). 여기서는 사유를 그대로 로그인 거절로 올린다.
          const account = await resolveAccountContext(session.userId);
          if (account.block) throw new APIError("FORBIDDEN", { message: account.block });

          return {
            data: {
              ...session,
              authorId: account.authorId,
              workspaceId: account.workspaceId,
            },
          };
        },
      },
    },
  },

  account: {
    modelName: "BaAccount",
  },

  session: {
    modelName: "BaSession",
    expiresIn: 7 * 24 * 60 * 60, // 7일
    updateAge: 5 * 60, // 5분마다 갱신
    cookieCache: {
      enabled: true,
      maxAge: 5 * 60, // 5분
      strategy: "jwe",
    },
    additionalFields: {
      authorId: { type: "string", required: false },
      workspaceId: { type: "number", required: false },
    },
  },

  verification: {
    modelName: "BaVerification",
    storeIdentifier: "hashed",
  },

  rateLimit: {
    enabled: true,
    window: 60,
    max: 100,
    customRules: {
      "/sign-in/email": { window: 60, max: 5 },
      "/sign-up/email": { window: 60, max: 3 },
      "/forget-password": { window: 60, max: 3 },
    },
  },

  /**
   * **Better Auth 의 가입 엔드포인트는 바깥에 열지 않는다** (#343).
   *
   * `emailAndPassword.enabled` 는 `POST /api/auth/sign-up/email` 을 함께 노출하는데, 그 경로는
   * 이 제품의 가입 절차(이메일 OTP → `POST /api/common/signup`)를 통째로 건너뛴다. 실제로
   * 로그인하지 않은 호출자가 임의 주소로 `tn_user` 행을 만들 수 있었고, 그러면 진짜 주인은
   * 「이미 사용 중인 이메일」로 막혀 가입하지 못했다(주소 선점).
   *
   * `emailAndPassword.disableSignUp` 은 쓸 수 없다 — 그 스위치는 엔드포인트 핸들러 안에서
   * 검사되므로 서버가 직접 부르는 `auth.api.signUpEmail`(가입 라우트가 쓰는 그 호출)까지 같이
   * 막는다. 그래서 **HTTP 요청으로 들어온 호출만** 막는다: `ctx.request` 는 라우터가 넘겨주는
   * 실제 Request 이고, 서버 내부 호출(`auth.api.*` 에 body 만 넘김)에는 없다.
   */
  hooks: {
    before: createAuthMiddleware(async (ctx) => {
      if (ctx.path === "/sign-up/email" && ctx.request) {
        throw new APIError("NOT_FOUND", { message: "Not found" });
      }
    }),
  },

  plugins: [
    jwt({
      jwt: {
        definePayload: ({ user, session }) => ({
          role: (session as any).authorId ?? null,
          workspace_id: (session as any).workspaceId ?? null,
          email: user.email,
        }),
        getSubject: ({ user }) => user.id,
        expirationTime: JWT_EXPIRES_IN,
        // 커스텀 sign: JWKS DB 접근 우회, HS256으로 직접 서명
        sign: (payload) => {
          const { sub, role, workspace_id, email } = payload as Record<string, any>;
          return jsonwebtoken.sign({ sub, role, workspace_id, email }, JWT_SECRET, {
            algorithm: "HS256",
            expiresIn: JWT_EXPIRES_IN,
          });
        },
      },
      jwks: {
        remoteUrl: "none", // 커스텀 sign 사용 시 필수 (실제로 호출되지 않음)
        keyPairConfig: { alg: "ES256" as const },
      },
    }),
  ],
});

export type Session = typeof auth.$Infer.Session;
