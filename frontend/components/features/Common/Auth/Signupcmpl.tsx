"use client";

import { FC, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import PolicyPopup from "@/components/features/Common/Policy/PolicyPopup";

interface Props {}

export const Signupcmpl: FC<Props> = () => {
  const [count, setCount] = useState(5);
  const router = useRouter();

  useEffect(() => {
    const timerId = setInterval(() => {
      setCount((prevCount) => prevCount - 1);
      if (count === 1) {
        clearInterval(timerId);
        router.push("/");
      }
    }, 1000);

    return () => clearInterval(timerId);
  }, [count, router]); // count 상태가 변경될 때마다 useEffect 실행

  return (
    <div className="relative h-[100dvh] w-screen bg-bg-base">
      <div className="auth-backdrop absolute z-10 m-auto w-full px-4 py-8 h-full min-h-[667px]">
        <PolicyPopup additionalClassName="pointer-events-none" />

        {/* 라이트 카드 — 어두운 `.auth-backdrop` 안의 밝은 섬이라 자기 모드를 선언한다
            (Signup.tsx 와 같은 이유). */}
        <div
          data-theme="light"
          className="card lg:card-side rounded-3xl bg-[#F0F1F2] w-full h-full sm:max-h-[700px] sm:max-w-[800px] m-auto"
        >
          <div className="card-body">
            <div className="w-full lg:max-w-3xl sm:mx-auto sm:w-full sm:max-w-sm sm:pt-10">
              <h2 className="font-bold text-2xl sm:text-4xl mt-10 text-center tracking-tight text-[#303F67]">
                가입을 환영합니다.
              </h2>
              <div className="text-center mt-3 text-[#303F67] text-sm font-semibold">
                투자 리서치에 특화된 최고의 성능을 제공합니다.
              </div>
              <div className="font-semibold text-base text-[#2C64F8] text-center mt-16">
                {count} 초 후 로그인 창으로 이동합니다...
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
