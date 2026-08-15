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
import { fetchNavigation } from "@/services/common/menuService";
import { useNavStore } from "@/stores/shared/navStore";
import { BENCH_PATH } from "@/constants/shell";
import { collectNavPaths, findFirstNavPath, type NavItem } from "@/lib/shell/nav";

/**
 * 로그인 후 착지점 — **실험대가 홈이다**(화면 설계 §20.2).
 *
 * 그래도 메뉴에 있는지를 먼저 본다. 메뉴 게이트가 fail-closed 라, 실험대 메뉴를 못 받은
 * 사용자를 그리로 보내면 셸이 곧바로 로그인 화면으로 되튕겨 "로그인이 안 된다"로 보인다.
 * 그 경우에는 예전처럼 접근 가능한 첫 화면으로 간다.
 */
const resolveLandingPath = (items: NavItem[]): string | null =>
  collectNavPaths(items).includes(BENCH_PATH) ? BENCH_PATH : findFirstNavPath(items);

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
            const nav = await fetchNavigation();
            const landingPath = resolveLandingPath(nav.items);
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
    <>
      <div className="relative h-[100dvh] w-screen">
        <div className="auth-backdrop auth-backdrop--hero absolute left-1/2 transform -translate-x-1/2 z-10 m-auto w-full h-full min-h-[667px] px-4 py-4 sm:py-8">
          <PolicyPopup additionalClassName="!text-white" />

          <div className="grid grid-flow-col grid-rows-1 h-[calc(100%-2rem)]">
            {/* Hero Section - 왼쪽 영역 */}
            <div className="absolute top-[10%] left-[100px] z-50 col-span-9 hidden xl:block w-full max-w-[600px]">
              <div className="text-left">
                <h1 className="font-bold text-5xl text-white leading-tight mb-2">ACME</h1>
                <p className="mt-4 text-xl text-white/90 font-normal leading-relaxed max-w-[520px]">
                  Next.js 16 + React 19 + FastAPI + Prisma
                  <br />
                  하이브리드 풀스택 아키텍처
                </p>
                <div className="mt-8 space-y-3 text-white/85">
                  <div className="flex items-start gap-3">
                    <svg className="w-6 h-6 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="text-lg">🔐 Better Auth + Prisma 공통 기능</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <svg className="w-6 h-6 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="text-lg">⚡ FastAPI 고성능 백엔드</span>
                  </div>
                  <div className="flex items-start gap-3">
                    <svg className="w-6 h-6 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="text-lg">🎨 Radix UI + Tailwind CSS</span>
                  </div>
                </div>
                <p className="mt-6 text-base text-white/70">트레이딩 봇을 만들고, 검증하고, 운용하는 도구입니다.</p>
              </div>
            </div>

            {/* Login Form - 오른쪽 영역 */}
            <div className="col-span-2 flex justify-center xl:justify-end">
              <div className="card lg:card-side rounded-3xl bg-[#F0F1F2] w-full sm:h-full max-h-[780px] min-h-[540px] sm:min-h-[640px] sm:min-w-[460px] max-w-[460px] m-auto sm:m-0">
                <div className="card-body">
                  <h2 className="font-semibold text-5xl sm:text-6xl mt-1 sm:mt-20 text-center tracking-tight text-[#303F67]">
                    Login
                  </h2>
                  <div className="font-medium text-center w-full mt-1 sm:mt-3 text-[#303F67] text-base">
                    서비스를 이용하시려면 로그인해주세요.
                  </div>

                  <div className="border-t-[1px] mt-2 sm:mt-10 mb-2 sm:mb-8 border-t-[#DDE2EC]"></div>
                  <div className="sm:mx-auto sm:w-full sm:max-w-sm">
                    <form action="#" method="POST" className="space-y-4" onSubmit={handleSubmit}>
                      <div className="items-center max-w-sm mx-auto">
                        <label htmlFor="email" className="block text-sm font-medium text-gray-900">
                          이메일 주소
                        </label>
                        <div className="flex mt-1">
                          <div className="relative w-full">
                            <TextBox
                              id="email"
                              name="email"
                              mode="email"
                              placeholder="이메일을 입력해주세요."
                              defaultValue=""
                              width="100%"
                              height={48}
                              className="rounded-2xl"
                            />
                          </div>
                        </div>
                      </div>

                      <div className="items-center max-w-sm mx-auto">
                        <label htmlFor="password" className="block text-sm font-medium text-gray-900">
                          비밀번호
                        </label>
                        <div className="flex mt-1">
                          <div className="relative w-full">
                            <TextBox
                              id="password"
                              name="password"
                              showPasswordToggle
                              placeholder="비밀번호를 입력해주세요."
                              defaultValue=""
                              width="100%"
                              height={48}
                              maxLength={72}
                              className="rounded-2xl"
                            />
                          </div>
                        </div>
                      </div>

                      <div>
                        <Button
                          onClick={() => loginTypeChk("credentials")}
                          useSubmitBehavior={true}
                          disabled={loading}
                          text="로그인"
                          width="100%"
                          height={48}
                          stylingMode="contained"
                          type="default"
                          className="rounded-2xl bg-gradient-to-r from-[#2E3BD0] to-[#2C64F8] text-sm font-bold text-white"
                        />
                        <div className="bg-[#D6DAE4] w-full h-12 rounded-2xl shadow-sm mt-4 text-center font-medium text-[#6B7183] text-sm flex items-center justify-center">
                          처음 방문이세요?
                          <Link
                            href="/signup/agree"
                            className="font-medium text-sm text-[#2D5AEE] hover:text-blue-500 ml-1"
                          >
                            가입하기
                          </Link>
                        </div>
                        <div className="flex justify-center pt-5">
                          <div className="text-sm pr-5">
                            <Link href="/signup/idsearch/" className="font-medium text-[#303F67] hover:text-blue-500">
                              아이디 찾기
                            </Link>
                          </div>
                          <span className="mr-4 ml-4 text-[#DDE2EC]">|</span>
                          <div className="text-sm pl-5">
                            <Link href="/signup/search/" className="font-medium text-[#303F67] hover:text-blue-500">
                              비밀번호 찾기
                            </Link>
                          </div>
                        </div>
                      </div>
                    </form>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
