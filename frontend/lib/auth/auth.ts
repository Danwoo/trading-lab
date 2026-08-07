import { betterAuth, APIError } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { jwt } from "better-auth/plugins";
import { prisma } from "@/lib/prisma/client";
import jsonwebtoken from "jsonwebtoken";
import nodemailer from "nodemailer";
import path from "path";
import { env } from "@/env";
import { SYS_ADMIN_AUTHOR_ID, AUTHOR_PRIORITY } from "@/constants/protected";
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
          const user = await prisma.user.findUnique({
            where: { id: session.userId },
            select: {
              use_at: true,
              appr_at: true,
              email: true,
              workspace_id: true,
              workspace: { select: { use_at: true } },
              // 기본 멤버십은 사용자당 1행이어야 하지만 DB 가 강제하지 못한다 (Prisma 스키마로
              // partial unique index 를 표현할 수 없어 `prisma db push` 경로에 심을 자리가 없다 — #253).
              // 그래서 정렬을 못 박는다: 불변식이 깨져도 로그인마다 테넌트가 바뀌지는 않게 한다.
              workspace_members: {
                where: { is_default: true },
                select: { workspace_id: true, workspace: { select: { use_at: true } } },
                orderBy: { workspace_id: "asc" },
                take: 1,
              },
            },
          });
          if (user?.appr_at === "R") throw new APIError("FORBIDDEN", { message: "RejectedUser" });
          if (user?.appr_at !== "Y") throw new APIError("FORBIDDEN", { message: "PendingApproval" });
          if (user?.use_at === "N") throw new APIError("FORBIDDEN", { message: "InactiveUser" });

          const memberships = await prisma.authorMember.findMany({
            where: { user_id: user.email },
            select: { author_id: true },
          });
          const authorIds = memberships.map((m) => m.author_id);

          // 대표 권한: 행동 권한 우선순위로 먼저 집고 없으면 자유 권한 fallback (숫자 정렬 비의존)
          const authorId = AUTHOR_PRIORITY.find((a) => authorIds.includes(a)) ?? authorIds[0] ?? null;

          // 세션이 담는 것은 "소속"이 아니라 "지금 선택된 워크스페이스" — 기본 멤버십이 결정하고,
          // 아직 멤버십이 없는 계정은 사용자 행의 워크스페이스로 떨어진다.
          const defaultMembership = user.workspace_members[0];
          const selectedWorkspace = defaultMembership
            ? { id: defaultMembership.workspace_id, use_at: defaultMembership.workspace.use_at }
            : user.workspace
              ? { id: user.workspace_id, use_at: user.workspace.use_at }
              : null;

          // 워크스페이스 비활성 시 사용자도 접근 불가 — 단 시스템관리자(admin)는 무관하게 통과
          const isSysAdmin = authorId === SYS_ADMIN_AUTHOR_ID;
          if (!isSysAdmin && selectedWorkspace && selectedWorkspace.use_at !== "Y") {
            throw new APIError("FORBIDDEN", { message: "InactiveWorkspace" });
          }

          return {
            data: {
              ...session,
              authorId,
              workspaceId: selectedWorkspace?.id ?? null,
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
