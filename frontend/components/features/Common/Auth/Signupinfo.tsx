// components/features/Common/Auth/Signupinfo.tsx
"use client";

import { FC, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useParams } from "next/navigation";
import Link from "next/link";

// 배럴이 아니라 직접 경로로 가져온다 — `@/components/shared/ui` 배럴은 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { Button } from "@/components/shared/ui/Button";
import { TextBox } from "@/components/shared/ui/TextBox";

import PolicyPopup from "@/components/features/Common/Policy/PolicyPopup";
import { showMessage } from "@/stores/shared/messageStore";
import { signup } from "@/services/common/authService";
import { signupSchema } from "@/schemas/common/signup";

interface Props {}

export const SignupInfo: FC<Props> = () => {
  const params = useParams<{ email: string }>();
  const router = useRouter();
  const decodedEmail = decodeURIComponent(params.email);

  useEffect(() => {
    const verifiedEmail = sessionStorage.getItem("verifiedSignupEmail");
    if (verifiedEmail !== decodedEmail) {
      router.push("/signup");
    }
  }, [decodedEmail, router]);

  const handleSubmit = async (e: any) => {
    e.preventDefault();

    const parsed = signupSchema.safeParse({
      password: e.target.password.value,
      name: e.target.name.value,
      dept: e.target.dept.value,
    });

    if (!parsed.success) {
      showMessage("알림", <div>{parsed.error.issues[0].message}</div>);
      return;
    }

    try {
      const data = await signup(decodedEmail, parsed.data.password, parsed.data.name, parsed.data.dept ?? "");
      sessionStorage.removeItem("verifiedSignupEmail");
      if (!data?.result) {
        if (data?.name === "password") {
          showMessage("알림", <div>비밀번호 8자리 이상 입력해주세요.</div>);
        } else if (data?.name === "email") {
          showMessage("알림", <div>이미 가입된 이메일 입니다.</div>);
        }
        return;
      }
      router.push("/signup/complete");
    } catch (error) {
      console.error("Error sending email:", error);
      showMessage("오류", <div>회원가입 중 오류가 발생했습니다.</div>);
    }
  };

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
                비밀번호 만들기
              </h2>
              <div className="text-center mt-3 text-[#303F67] text-sm font-semibold">
                비밀번호는 한 번만 입력하니 신중하게 입력해주세요.
              </div>
            </div>

            <div className="border-t-[1px] mt-10 mb-8 border-t-[#DDE2EC] w-full "></div>

            <div className="sm:mx-auto sm:w-full sm:max-w-sm">
              <form action="#" method="POST" className="space-y-4" onSubmit={handleSubmit}>
                <div className="items-center max-w-sm mx-auto hidden">
                  <label htmlFor="email" className="block text-sm text-gray-900">
                    이메일 주소
                  </label>
                  <TextBox
                    id="email"
                    name="email"
                    mode="email"
                    width="100%"
                    height={48}
                    readOnly={true}
                    defaultValue={decodedEmail}
                    className="rounded-xl"
                  />
                </div>

                <div className="items-center max-w-sm mx-auto">
                  <label htmlFor="password" className="block text-sm font-medium text-gray-900">
                    비밀번호를 입력해주세요.
                  </label>
                  <div className="flex mt-1">
                    <div className="relative w-full">
                      <TextBox
                        id="password"
                        name="password"
                        showPasswordToggle
                        width="100%"
                        height={48}
                        maxLength={72}
                        defaultValue=""
                        className="rounded-2xl"
                      />
                    </div>
                  </div>
                </div>

                <div className="items-center max-w-sm mx-auto">
                  <label htmlFor="name" className="block text-sm font-medium text-gray-900">
                    사용하실 이름을 입력해주세요.
                  </label>
                  <TextBox id="name" name="name" defaultValue="" width="100%" height={48} className="rounded-2xl" />
                </div>

                <div className="items-center max-w-sm mx-auto">
                  <label htmlFor="dept" className="block text-sm font-medium text-gray-900">
                    소속을 입력해주세요. / (없는경우: 없음)
                  </label>
                  <TextBox id="dept" name="dept" defaultValue="" width="100%" height={48} className="rounded-2xl" />
                </div>

                <div className="items-center max-w-sm mx-auto">
                  <Button
                    useSubmitBehavior={true}
                    text="계속 (2/2)"
                    width="100%"
                    height={48}
                    stylingMode="contained"
                    type="default"
                    className="rounded-2xl bg-gradient-to-r from-[#2E3BD0] to-[#2C64F8] text-sm font-bold text-white"
                  />
                </div>
              </form>

              <p className="mt-5 text-center text-sm text-gray-500">
                <Link href="/" className="font-medium text-[#192850] hover:text-blue-500">
                  다른 계정으로 로그인
                </Link>
              </p>
            </div>

            <ul className="mt-5 sm:mt-10 max-w-md w-full hidden sm:flex m-auto list-none justify-between p-0 transition-[height] duration-200 ease-in-out">
              <li className="flex-auto">
                <div
                  className="flex items-center pl-2 leading-[1.3rem] no-underline after:ml-2 after:h-px after:w-full after:flex-1
                after:bg-[#e0e0e0] dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none"
                >
                  <span className="text-[#192850] my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DFE1E8] text-sm font-medium">
                    1
                  </span>
                  <span className="font-medium text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-300">
                    이메일 인증
                  </span>
                </div>
              </li>

              <li className="flex-auto">
                <div className="flex items-center leading-[1.3rem] no-underline before:mr-2 before:h-px before:w-full before:flex-1 before:bg-[#e0e0e0] before:content-[''] after:ml-2 after:h-px after:w-full after:flex-1 after:bg-[#e0e0e0] after:content-[''] focus:outline-none dark:before:bg-neutral-600 dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none">
                  <span className="my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DCE4FF] text-sm font-medium text-[#40464f]">
                    2
                  </span>
                  <span className="font-semibold text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-700">
                    비밀번호 만들기
                  </span>
                </div>
              </li>

              <li className="flex-auto">
                <div className="flex items-center pr-2 leading-[1.3rem] no-underline before:mr-2 before:h-px before:w-full before:flex-1 before:bg-[#e0e0e0] before:content-[''] focus:outline-none dark:before:bg-neutral-600 dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none">
                  <span className="text-[#192850] my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DFE1E8] text-sm font-medium">
                    3
                  </span>
                  <span className="font-medium text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-300">
                    완료
                  </span>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
