"use client";

import { FC, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";

// 배럴이 아니라 직접 경로로 가져온다 — `@/components/shared/ui` 배럴은 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { Button } from "@/components/shared/ui/Button";
import { TextBox } from "@/components/shared/ui/TextBox";

import PolicyPopup from "@/components/features/Common/Policy/PolicyPopup";
import { showMessage } from "@/stores/shared/messageStore";
import { authClient } from "@/lib/auth/auth-client";

interface Props {}

export const PassSearchinfo: FC<Props> = () => {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams.get("token") ?? "";

  useEffect(() => {
    if (!token) router.push("/signup/search");
  }, [token, router]);

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    const newPassword = e.target.password.value;

    if (!newPassword || newPassword.trim().length < 8) {
      showMessage("알림", <div>비밀번호 8자리 이상 입력해주세요.</div>);
      return;
    }

    const { error } = await authClient.resetPassword({ newPassword, token });

    if (error) {
      if (error.code === "PASSWORD_TOO_SHORT" || error.code === "PASSWORD_TOO_LONG") {
        showMessage("알림", <div>비밀번호 8자리 이상 입력해주세요.</div>);
        return;
      }
      showMessage(
        "알림",
        <div>
          링크가 만료되었거나 유효하지 않습니다.
          <br />
          다시 시도해주세요.
        </div>,
      );
      router.push("/signup/search");
      return;
    }

    showMessage(
      "비밀번호 찾기",
      <div className="text-center">
        비밀번호 변경을 완료 하였습니다. <br />
        로그인페이지로 이동합니다.
      </div>,
      {
        callback: {
          onConfirm: () => router.push("/"),
        },
      },
    );
  };

  return (
    <div className="relative h-[100dvh] w-screen">
      <div className="auth-backdrop absolute z-10 m-auto w-full px-4 py-8 h-full min-h-[667px]">
        <PolicyPopup additionalClassName="pointer-events-none" />

        <div className="card lg:card-side rounded-3xl bg-[#F0F1F2] w-full h-full sm:max-h-[700px] sm:max-w-[800px] m-auto">
          <div className="card-body">
            <div className="w-full lg:max-w-3xl sm:mx-auto sm:w-full sm:max-w-sm sm:pt-10">
              <h2 className="font-bold text-2xl sm:text-4xl mt-10 text-center tracking-tight text-[#303F67]">
                비밀번호 만들기
              </h2>
              <div className="text-center mt-3 text-[#303F67] text-sm font-semibold">
                비밀번호는 한 번만 입력하니 신중하게 입력해주세요.
              </div>
            </div>

            <div className="border-t-[1px] mt-10 mb-8 border-t-[#DDE2EC] w-full "></div>

            <div className="sm:mx-auto sm:w-full sm:max-w-sm">
              <form action="#" method="POST" className="space-y-4" onSubmit={handleSubmit}>
                <div className="items-center max-w-sm mx-auto">
                  <label htmlFor="password" className="font-medium block text-sm text-gray-900">
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

                <div className="items-center max-w-sm mx-auto">
                  <Button
                    useSubmitBehavior={true}
                    text="완료하기"
                    width="100%"
                    height={48}
                    stylingMode="contained"
                    type="default"
                    className="rounded-2xl bg-gradient-to-r from-[#2E3BD0] to-[#2C64F8] text-sm font-bold text-white"
                  />
                </div>
              </form>

              <p className="mt-5 text-center text-sm text-gray-500">
                <Link href="/signup/idsearch/" className="font-medium text-[#192850] hover:text-blue-500">
                  아이디 찾기
                </Link>
                <span className="mr-4 ml-4 text-[#DDE2EC]">|</span>
                <Link href="/" className="font-medium text-[#192850] hover:text-blue-500">
                  다른 계정으로 로그인
                </Link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
