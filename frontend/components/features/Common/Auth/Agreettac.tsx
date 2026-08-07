"use client";

import { FC, useState, useRef } from "react";
import { useRouter } from "next/navigation";

import Link from "next/link";
import PolicyPopup, { PolicyPopupRef } from "@/components/features/Common/Policy/PolicyPopup";
// 배럴이 아니라 직접 경로로 가져온다 — `@/components/shared/ui` 배럴은 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { showMessage } from "@/stores/shared/messageStore";
import { Button } from "@/components/shared/ui/Button";

interface Props {}

// 약관 동의 체크 한 칸. `components/shared/ui/CheckBox` 래퍼는 `fieldName` +
// `onValueChanged(fieldName, value)` 의 객체 state 폼 계약이라(anti-patterns-frontend.md 룰4)
// 단일 값 바인딩인 이 화면에는 맞지 않는다 — 네이티브 `<input type="checkbox">` 를 쓴다.
// `<label>` 로 감싸 텍스트 클릭도 토글되고, 체크박스 자체가 Tab 순회·Space 토글을 갖는다.
function AgreeCheck({ id, checked, onChange }: { id: string; checked: boolean; onChange: (next: boolean) => void }) {
  return (
    <label
      htmlFor={id}
      className={`flex w-[120px] cursor-pointer items-center gap-2 rounded-2xl py-1 pl-4 text-sm text-white ${
        checked ? "bg-blue-500" : "bg-gray-500"
      }`}
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-white focus:outline-none focus:ring-2 focus:ring-blue-500/40"
      />
      동의합니다
    </label>
  );
}

export const Agreettac: FC<Props> = () => {
  const [isChecked, setIsChecked] = useState(false);
  const [isChecked2, setIsChecked2] = useState(false);
  const router = useRouter();
  const policyPopupRef = useRef<PolicyPopupRef>(null);

  const handleSubmit = (e: any) => {
    e.preventDefault();
    //체크 상태 확인
    if (isChecked && isChecked2) {
      router.push("/signup");
    } else {
      showMessage("알림", <div>필수 약관을 동의 하셔야 서비스 이용이 가능합니다.</div>);
    }
  };

  const allChecked = () => {
    setIsChecked(true);
    setIsChecked2(true);
  };

  return (
    <div className="relative h-[100dvh] w-screen">
      <div className="auth-backdrop absolute z-10 m-auto w-full px-4 py-8 h-full min-h-[667px]">
        <PolicyPopup ref={policyPopupRef} />
        <div className="card lg:card-side rounded-3xl bg-[#F0F1F2] w-full h-full sm:max-h-[700px] sm:max-w-[800px] m-auto">
          <div className="card-body">
            <div className="w-full lg:max-w-3xl sm:mx-auto sm:w-full sm:max-w-sm sm:pt-10">
              <h2 className="font-bold text-2xl sm:text-4xl mt-10 text-center tracking-tight text-[#303F67]">
                이용약관 동의
              </h2>
              <div className="text-center mt-3 text-[#303F67] text-sm font-semibold">
                더 좋은 서비스 제공을 위한 정보를 수집하고 있습니다.
              </div>
            </div>

            <div className="border-t-[1px] mt-10 mb-8 border-t-[#DDE2EC] w-full "></div>

            <div className="sm:mx-auto sm:w-full sm:max-w-sm">
              <form action="#" method="POST" className="space-y-4" onSubmit={handleSubmit}>
                <div className="flex items-center w-full rounded-2xl bg-gray-300 h-12 px-2 pr-5">
                  <div className="flex justify-start w-full">
                    <Button
                      stylingMode="text"
                      className="text-sm sm:text-base w-full"
                      render={() => (
                        <div className="text-left w-full">
                          <span className="whitespace-nowrap">
                            <span className="font-bold">(필수)</span> 이용약관
                          </span>
                        </div>
                      )}
                      onClick={() => policyPopupRef.current?.showTerms()}
                    />
                  </div>

                  <div className="flex justify-end w-full">
                    <AgreeCheck id="agree" checked={isChecked} onChange={setIsChecked} />
                  </div>
                </div>

                <div className="flex items-center w-full rounded-2xl bg-gray-300 h-12 px-2 pr-5">
                  <div className="flex justify-start w-full">
                    <Button
                      stylingMode="text"
                      className="text-sm sm:text-base w-full"
                      render={() => (
                        <div className="text-left w-full">
                          <span className="whitespace-nowrap">
                            <span className="font-bold">(필수)</span> 개인정보처리방침
                          </span>
                        </div>
                      )}
                      onClick={() => policyPopupRef.current?.showPrivacy()}
                    />
                  </div>

                  <div className="flex justify-end w-full">
                    <AgreeCheck id="agree2" checked={isChecked2} onChange={setIsChecked2} />
                  </div>
                </div>

                <div className="w-full flex gap-4">
                  <Button
                    text="전체선택"
                    onClick={allChecked}
                    width={144}
                    height={48}
                    stylingMode="contained"
                    type="default"
                    className="rounded-md bg-black text-white text-sm font-semibold"
                  />
                  <Button
                    useSubmitBehavior={true}
                    text="동의하기"
                    width="100%"
                    height={48}
                    stylingMode="contained"
                    type="default"
                    className="rounded-md bg-[#2C64F8] text-sm font-semibold text-white"
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
                <div className="flex items-center pl-2 leading-[1.3rem] no-underline after:ml-2 after:h-px after:w-full after:flex-1 after:bg-[#e0e0e0] dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none">
                  <span className="my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#e0e0e0] text-sm font-medium text-[#40464f]">
                    1
                  </span>
                  <span className="font-semibold text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-700">
                    이메일 인증
                  </span>
                </div>
              </li>

              <li className="flex-auto">
                <div className="flex items-center pr-2 leading-[1.3rem] no-underline before:mr-2 before:h-px before:w-full before:flex-1 before:bg-[#e0e0e0] before:content-[''] focus:outline-none dark:before:bg-neutral-600 dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none">
                  <span className="text-[#192850] my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DFE1E8] text-sm font-medium ">
                    2
                  </span>
                  <span className="font-semibold text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-300">
                    비밀번호만들기
                  </span>
                </div>
              </li>

              <li className="flex-auto">
                <div className="flex items-center pr-2 leading-[1.3rem] no-underline before:mr-2 before:h-px before:w-full before:flex-1 before:bg-[#e0e0e0] before:content-[''] focus:outline-none dark:before:bg-neutral-600 dark:after:bg-neutral-600 dark:hover:bg-[#3b3b3b] pointer-events-none select-none">
                  <span className="text-[#192850] my-6 mr-2 flex h-[1.938rem] w-[1.938rem] items-center justify-center rounded-full bg-[#DFE1E8] text-sm font-medium ">
                    3
                  </span>
                  <span className="font-semibold text-xs sm:text-base text-[#192850] after:flex after:text-[0.8rem] after:content-[data-content] dark:text-neutral-300">
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
