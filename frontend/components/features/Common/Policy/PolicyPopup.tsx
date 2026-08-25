// components/features/Common/Policy/PolicyPopup.tsx
"use client";

import { useImperativeHandle, forwardRef } from "react";
import { Button } from "@/components/shared/ui/Button";
import { Terms } from "./Terms";
import { Privacy } from "./Privacy";
// 배럴이 아니라 직접 경로로 가져온다 — `@/components/shared/ui` 배럴은 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { showMessage } from "@/stores/shared/messageStore";

interface Props {
  showButtons?: boolean;
  buttonClassName?: string;
  additionalClassName?: string;
}

// 약관 링크의 색은 이 컴포넌트가 정한다 — 호출부에 맡기면 색을 넘긴 한 곳(로그인)만 맞고
// 나머지는 `Button` 의 기본 파랑(`text-blue-600`, 어두운 인증 배경 위 3.74:1)으로 떨어진다.
// 이 목록은 늘 `.auth-backdrop` 위에 있으므로 다크 잉크 사다리의 `--ink-muted`(5.4:1)를 쓴다.
// `!` 는 `Button` 이 박는 `text-blue-600`·`hover:bg-blue-50` 을 덮기 위한 것이다 — `cn()` 은
// 단순 join 이라 뒤에 온 클래스가 이기지 않는다(primitives/cn.ts). 호버 바탕을 지우는 이유:
// 밝은 파랑 바탕 위에 밝은 잉크가 얹히면 1.17:1 이 된다.
const LINK_COLOR = "!text-ink-muted hover:!text-ink hover:!bg-transparent";

export interface PolicyPopupRef {
  showTerms: () => void;
  showPrivacy: () => void;
}

const PolicyPopup = forwardRef<PolicyPopupRef, Props>(
  ({ showButtons = true, buttonClassName = "text-sm sm:text-base", additionalClassName = "" }, ref) => {
    // ref를 통해 메서드 노출
    useImperativeHandle(ref, () => ({
      showTerms: () => showTermsPopup(),
      showPrivacy: () => showPrivacyPopup(),
    }));

    const showTermsPopup = async () => {
      await showMessage("이용약관", <Terms />, {
        width: 1000,
        height: 700,
      });
    };

    const showPrivacyPopup = async () => {
      await showMessage("개인정보처리방침", <Privacy />, {
        width: 1000,
        height: 700,
      });
    };

    const finalClassName = `${LINK_COLOR} ${buttonClassName} ${additionalClassName}`.trim();

    return (
      <>
        {showButtons && (
          <ul className="hidden sm:flex justify-end text-ink-strong pb-5">
            <li className="mr-5">
              <Button text="이용약관" onClick={showTermsPopup} stylingMode="text" className={finalClassName} />
            </li>
            <li className="mr-0">
              <Button
                text="개인정보처리방침"
                onClick={showPrivacyPopup}
                stylingMode="text"
                className={finalClassName}
              />
            </li>
          </ul>
        )}
      </>
    );
  },
);

PolicyPopup.displayName = "PolicyPopup";

export default PolicyPopup;
