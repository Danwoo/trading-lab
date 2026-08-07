"use client";

import { FC } from "react";
import Link from "next/link";

// 배럴이 아니라 직접 경로로 가져온다 — `@/components/shared/ui` 배럴은 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { Button } from "@/components/shared/ui/Button";
import { TextBox } from "@/components/shared/ui/TextBox";

import PolicyPopup from "@/components/features/Common/Policy/PolicyPopup";
import { showMessage } from "@/stores/shared/messageStore";
import { checkEmail } from "@/services/common/authService";

interface Props {}

export const Idsearch: FC<Props> = () => {
  const handleSubmit = async (e: any) => {
    e.preventDefault();
    const email = e.target.email.value;

    if (email) {
      try {
        const data = await checkEmail(email);

        // MessagePopup 컴포넌트 사용
        if (!data?.result) {
          showMessage("알림", <div>존재하지 않는 이메일 입니다.</div>);
        } else {
          showMessage("알림", <div>[{email}] 은 존재하는 이메일 입니다.</div>);
        }
      } catch (error) {
        console.error("Error sending email:", error);
        showMessage("오류", <div>오류가 발생했습니다. 다시 시도해주세요.</div>);
        return false;
      }
    }

    return false;
  };

  return (
    <div className="relative h-[100dvh] w-screen">
      <div className="auth-backdrop absolute z-10 m-auto w-full px-4 py-8 h-full min-h-[667px]">
        <PolicyPopup additionalClassName="pointer-events-none" />

        <div className="card lg:card-side rounded-3xl bg-[#F0F1F2] w-full h-full sm:max-h-[700px] sm:max-w-[800px] m-auto">
          <div className="card-body">
            <div className="w-full lg:max-w-3xl sm:mx-auto sm:w-full sm:max-w-sm sm:pt-10">
              <h2 className="font-bold text-2xl sm:text-4xl mt-10 text-center tracking-tight text-[#303F67]">
                아이디 찾기
              </h2>
              <div className="text-center mt-3 text-[#303F67] text-sm font-semibold">
                이메일을 입력하여 가입여부를 확인하세요.
              </div>
            </div>

            <div className="border-t-[1px] mt-10 mb-8 border-t-[#DDE2EC] w-full "></div>

            <div className="sm:mx-auto sm:w-full sm:max-w-sm">
              <form action="#" method="POST" className="space-y-4" onSubmit={handleSubmit}>
                <div className="items-center max-w-sm mx-auto">
                  <label htmlFor="email" className="font-medium block text-sm text-gray-900">
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
                <div className="card-actions justify-center max-w-sm mx-auto">
                  <Button
                    useSubmitBehavior={true}
                    text="아이디 찾기"
                    width="100%"
                    height={48}
                    stylingMode="contained"
                    type="default"
                    className="rounded-2xl bg-gradient-to-r from-[#2E3BD0] to-[#2C64F8] text-sm font-bold text-white"
                  />
                </div>
              </form>

              <p className="mt-5 text-center text-sm text-gray-500">
                <Link href="/signup/search/" className="font-medium text-[#192850] hover:text-blue-500">
                  비밀번호 찾기
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
