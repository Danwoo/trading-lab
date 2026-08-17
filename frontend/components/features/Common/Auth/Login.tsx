"use client";

import { useState } from "react";
import { signIn } from "@/lib/auth/auth-client";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

import PolicyPopup from "@/components/features/Common/Policy/PolicyPopup";
// 배럴(@/components/shared/ui, @/components/shared/Feedback)이 아니라 직접 경로로 가져온다 —
// 배럴은 FileListDisplay 를 거쳐 services/common/fileService → env.ts 까지 끌고 온다(#341 ②).
import { Button } from "@/components/shared/ui/Button";
import { TextBox } from "@/components/shared/ui/TextBox";
import { showMessage } from "@/stores/shared/messageStore";
import { useNavStore } from "@/stores/shared/navStore";
import { POST_LOGIN_PATH } from "@/constants/routes";

const findFirstPath = (items: { path?: string; items?: any[] }[]): string | null => {
  for (const item of items) {
    if (item.path) return item.path;
    if (item.items) {
      const found = findFirstPath(item.items);
      if (found) return found;
    }
  }
  return null;
};

const hasPath = (items: { path?: string; items?: any[] }[], target: string): boolean =>
  items.some((item) => item.path === target || (item.items ? hasPath(item.items, target) : false));

/**
 * 로그인 후 착지점.
 *
 * 예전에는 「접근 가능한 첫 메뉴」였다 — 메뉴 정렬 순서가 곧 홈이라, 메뉴 하나를 위로
 * 올리면 홈이 조용히 바뀌었다. 실험대가 홈이 되면서(화면 결정 §20.2) 착지점을 상수로
 * 못박는다. 다만 **메뉴 게이트가 fail-closed** 라 그 경로 권한이 없는 사용자를 그리로 보내면
 * 셸이 곧바로 로그인 화면으로 되돌려 왕복한다 — 그래서 네비게이션에 있을 때만 쓰고,
 * 없으면 종전대로 첫 메뉴로 내려간다.
 */
const resolveLandingPath = (items: { path?: string; items?: any[] }[]): string | null =>
  hasPath(items, POST_LOGIN_PATH) ? POST_LOGIN_PATH : findFirstPath(items);

export const Login = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl");
  const [loginT, setLoginT] = useState("credentials");
  const [loading, setLoading] = useState(false);

  const loginTypeChk = async (btnt: string) => {
    setLoginT(btnt);
  };

  const handleSubmit = async (e: any) => {
    e.preventDefault();

    if (loginT == "credentials") {
      const username = e.target.email.value;
      const password = e.target.password.value;

      if (username && password && !loading) {
        setLoading(true);
        try {
          const { data, error } = await signIn.email({
            email: username,
            password,
          });

          if (data && !error) {
            // 이전 세션의 nav 캐시 무효화 (사용자 권한/워크스페이스 바뀌면 옛 캐시 반영됨)
            useNavStore.getState().reset();
            if (callbackUrl) {
              router.replace(callbackUrl);
              return;
            }
            // **스토어를 태워 받는다.** 스토어 밖에서 받으면 그 결과가 캐시에 안 남아,
            // 착지 화면의 셸이 같은 API 를 한 번 더 왕복한다 (`fetchNav` 는 `loaded` 면 건너뛴다).
            await useNavStore.getState().fetchNav();
            const landingPath = resolveLandingPath(useNavStore.getState().items);
            if (!landingPath) {
              // 접근 가능한 메뉴 없음 — 비정상 상태, 안내 후 admin 밖으로
              await showMessage(
                "알림",
                <div>
                  접근 가능한 메뉴가 없습니다.
                  <br />
                  관리자에게 문의해 주세요.
                </div>,
              );
              router.replace("/");
              return;
            }
            router.replace(landingPath);
            return;
          } else if (error?.message?.includes("RejectedUser")) {
            await showMessage(
              "로그인 불가",
              <div>
                가입이 거부된 계정입니다.
                <br />
                관리자에게 문의해 주세요.
              </div>,
            );
          } else if (error?.message?.includes("PendingApproval")) {
            await showMessage(
              "로그인 불가",
              <div>
                관리자 승인 대기 중인 계정입니다.
                <br />
                관리자에게 문의해 주세요.
              </div>,
            );
          } else if (error?.message?.includes("InactiveUser")) {
            await showMessage(
              "로그인 불가",
              <div>
                비활성화된 계정입니다.
                <br />
                관리자에게 문의해 주세요.
              </div>,
            );
          } else if (error?.message?.includes("InactiveWorkspace")) {
            await showMessage(
              "로그인 불가",
              <div>
                소속 워크스페이스가 비활성화되었습니다.
                <br />
                관리자에게 문의해 주세요.
              </div>,
            );
          } else if (error?.status === 429) {
            await showMessage(
              "알림",
              <div>
                로그인 시도가 너무 많습니다.
                <br />
                1분 후 다시 시도해주세요.
              </div>,
            );
          } else if (error?.status === 401) {
            await showMessage("알림", <div>이메일 또는 패스워드가 틀립니다.</div>);
          } else {
            throw error;
          }
        } catch (error) {
          console.log(error);
          await showMessage("오류", <div>로그인 중 오류가 발생했습니다.</div>);
        } finally {
          setLoading(false);
          // `#password` 자체가 <input> 이다 — 이관 전(DevExtreme)엔 id 가 위젯 루트 div 에 붙어
          // `#password input` 이어야 했다(#341 ⑤ 이관으로 한 단계 사라짐).
          setTimeout(() => document.querySelector<HTMLInputElement>("#password")?.focus(), 100);
        }
      }
    }
  };

  return (
    <div className="auth-backdrop auth-backdrop--hero relative min-h-[100dvh] w-full">
      {/* 상단 띠 — 시안(bench-shell)의 상태 바와 같은 자리·같은 말투. 로그인 전에도
          「실제 주문이 나가지 않는다」를 먼저 말한다. 이 제품에서 그것이 가장 먼저 알아야 할 사실이다. */}
      <header className="flex items-center gap-3 border-b border-hairline px-6 py-3.5 sm:px-10">
        <span className="text-2xs font-semibold uppercase tracking-[0.22em] text-ink-strong">Trading Lab</span>
        <span className="inline-flex items-center gap-1.5 rounded-badge border border-line px-2 py-0.5 text-2xs text-ink-muted">
          <span aria-hidden className="size-1.5 rounded-full bg-signal-warn" />
          모의
        </span>
        <span className="hidden text-2xs text-ink-muted sm:inline">실제 주문이 나가지 않습니다</span>
        <div className="ml-auto">
          <PolicyPopup buttonClassName="!text-2xs" additionalClassName="!text-ink-muted hover:!text-ink" />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-12 px-6 py-12 sm:px-10 lg:flex-row lg:items-center lg:gap-20 lg:py-20">
        {/* 왼쪽 — 제품이 무엇인가. 스택 자랑이 아니라 이 도구가 하는 일을 적는다. */}
        <section className="flex-1">
          <h1 className="text-[clamp(1.6rem,1.1rem+2.2vw,2.25rem)] font-semibold leading-[1.15] tracking-tight text-ink-strong">
            개인 투자 지휘소
          </h1>
          <p className="mt-3 max-w-[46ch] text-sm leading-relaxed text-ink">
            트레이딩 봇을 만들고, 과거 데이터로 검증하고, 굴리면서 성과를 비교합니다.
          </p>

          <dl className="mt-9 max-w-[44ch] divide-y divide-hairline border-y border-hairline">
            {[
              ["전략은 파일로 남는다", "git 에 남아 「왜 이렇게 샀지」를 나중에 코드로 되짚습니다."],
              ["장중에는 LLM 이 돌지 않는다", "봇은 결정론적으로 돌고, 연구는 저녁 배치에서만 돕니다."],
              ["자기 컴퓨터에서 자기 계좌로", "오픈소스 로컬 배포판입니다. 데이터도 키도 밖으로 나가지 않습니다."],
            ].map(([term, desc]) => (
              <div key={term} className="py-3.5">
                <dt className="text-sm font-medium text-ink-strong">{term}</dt>
                <dd className="mt-1 text-2xs leading-relaxed text-ink-muted">{desc}</dd>
              </div>
            ))}
          </dl>
        </section>

        {/* 오른쪽 — 폼. 흰 카드가 아니라 터미널과 같은 패널이다(로그인 직후 색이 뒤집히지 않게). */}
        <section className="w-full shrink-0 lg:w-[26rem]">
          <div className="rounded-panel border border-line bg-bg-panel/95 p-7 shadow-e1 sm:p-8">
            <h2 className="text-base font-semibold tracking-tight text-ink-strong">로그인</h2>
            <p className="mt-1 text-2xs text-ink-muted">계정으로 들어가면 실험대가 열립니다.</p>

            <form action="#" method="POST" className="mt-7 flex flex-col gap-5" onSubmit={handleSubmit}>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="email" className="text-2xs font-medium uppercase tracking-[0.1em] text-ink-muted">
                  이메일
                </label>
                <TextBox
                  id="email"
                  name="email"
                  mode="email"
                  placeholder="you@example.com"
                  defaultValue=""
                  width="100%"
                  height="2.75rem"
                  className="!bg-bg-raised !border-line !text-ink placeholder:!text-ink-faint focus:!ring-line-strong/30"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="password" className="text-2xs font-medium uppercase tracking-[0.1em] text-ink-muted">
                  비밀번호
                </label>
                <TextBox
                  id="password"
                  name="password"
                  showPasswordToggle
                  placeholder="비밀번호"
                  defaultValue=""
                  width="100%"
                  height="2.75rem"
                  maxLength={72}
                  className="!bg-bg-raised !border-line !text-ink placeholder:!text-ink-faint focus:!ring-line-strong/30"
                />
              </div>

              <div className="mt-1 flex flex-col gap-3">
                <Button
                  onClick={() => loginTypeChk("credentials")}
                  useSubmitBehavior={true}
                  disabled={loading}
                  text={loading ? "확인 중" : "로그인"}
                  width="100%"
                  height="2.75rem"
                  stylingMode="contained"
                  type="default"
                  className="!border-btn-line !bg-gradient-to-b !from-btn-from !to-btn-to !text-ink-strong hover:!brightness-110"
                />
                <p className="text-center text-2xs text-ink-muted">
                  처음 방문이세요?{" "}
                  <Link
                    href="/signup/agree"
                    className="font-medium text-ink underline decoration-line-strong underline-offset-4 hover:text-ink-strong"
                  >
                    가입하기
                  </Link>
                </p>
              </div>
            </form>
          </div>
        </section>
      </main>
    </div>
  );
};
