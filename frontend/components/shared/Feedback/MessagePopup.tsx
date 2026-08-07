"use client";

import React, { useEffect, useState } from "react";
// 배럴(`@/components/shared/ui`)이 아니라 파일을 직접 import 한다 — 이 컴포넌트는 RootLayout
// (app/layout.tsx)이 **모든 라우트**에 렌더하므로, 배럴을 거치면 그 배럴이 물고 있는
// 프리미티브 9개 + `ui/index.ts` 의 locale 부수효과가 전 라우트 번들에 딸려 들어온다
// (#381 — 실측: RootLayout 진입점 기준 devextreme 도달 14건 중 10건이 이 한 줄이었다.
// devextreme 자체는 #341 로 사라졌지만, 전 라우트에 실리는 진입점이라는 성질은 그대로다).
import { Popup } from "@/components/shared/ui/Popup";
import { Button } from "@/components/shared/ui/Button";
import { useMessageStore, type MessageItem } from "@/stores/shared/messageStore";

/**
 * 전역 확인·알림 팝업. `showMessage`(messageStore)가 채운 큐를 구독해 한 번에 하나씩 띄운다.
 *
 * **`currentMessage` 를 그대로 렌더에 쓰지 않는다 (#394).** `resolveMessage` 는 사용자가 확인/
 * 취소를 누르는 즉시 `currentMessage` 를 `null` 로 비우는데, 그 값으로 `return null` 하면 React 가
 * `<Popup>` 서브트리를 그 자리에서 뽑아버려 Radix `Presence` 가 닫힘 애니메이션을 재생할 기회
 * 자체가 없어진다(`ui/primitives/dialog.tsx` 불변식 (3) 주석 참고). 그래서 **마지막으로 보여준
 * 메시지를 로컬에 남겨 두고**(`displayed`) `Popup` 은 계속 마운트한 채 `visible` 만 토글한다 —
 * `FormModal`·`SelectGridPanel` 이 이미 쓰는 패턴이다.
 *
 * `displayed` 가 아직 없을 때(= 앱 시작 후 메시지가 한 번도 안 뜬 상태)만 `null` 을 반환한다.
 * 그 시점엔 애니메이션할 대상 자체가 없으므로 #394 의 함정에 해당하지 않는다.
 */
export function MessagePopup() {
  const { currentMessage, handleConfirm, handleCancel } = useMessageStore();
  const [displayed, setDisplayed] = useState<MessageItem | null>(null);

  useEffect(() => {
    if (currentMessage) setDisplayed(currentMessage);
  }, [currentMessage]);

  useEffect(() => {
    if (!currentMessage) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleConfirm();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentMessage, handleConfirm]);

  if (!displayed) return null;

  return (
    <Popup
      visible={currentMessage !== null}
      onHiding={handleCancel}
      dragEnabled={false}
      hideOnOutsideClick={false}
      shading={true}
      showTitle={true}
      title={displayed.title}
      width={displayed.width}
      height={displayed.height}
    >
      <div className="text-base" style={{ whiteSpace: "pre-line" }}>
        {displayed.content}
      </div>
      <div className="flex justify-end gap-2 pt-10">
        {displayed.type === "confirm" ? (
          <>
            <Button
              text={displayed.confirmText}
              onClick={handleConfirm}
              width="auto"
              height={40}
              stylingMode={displayed.confirmButtonStyle}
              type={displayed.confirmButtonType}
              className="min-w-[60px]"
            />
            <Button
              text={displayed.cancelText}
              onClick={handleCancel}
              width="auto"
              height={40}
              stylingMode={displayed.cancelButtonStyle}
              type={displayed.cancelButtonType}
              className="min-w-[60px]"
            />
          </>
        ) : (
          <Button
            text={displayed.confirmText}
            onClick={handleConfirm}
            width="auto"
            height={40}
            stylingMode={displayed.confirmButtonStyle}
            type={displayed.confirmButtonType}
            className="min-w-[60px]"
          />
        )}
      </div>
    </Popup>
  );
}
