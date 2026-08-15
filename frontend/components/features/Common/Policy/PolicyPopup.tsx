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

    const finalClassName = `${buttonClassName} ${additionalClassName}`.trim();

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
