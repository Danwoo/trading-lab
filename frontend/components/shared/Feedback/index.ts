// components/shared/Feedback/index.ts
//
// **이 배럴은 devextreme 을 (전이로도) 물지 않는다** — #381 이 세운 불변식이고, #341 로
// devextreme 이 레포에서 통째로 사라진 지금은 자동으로 성립한다. 그래도 이 배럴의 다른
// 성질은 그대로 지켜라: 27개 파일이 `showToast`/`showMessage` 하나 때문에 이걸 import 하고,
// RootLayout(app/layout.tsx)이 여기서 `MessagePopup`·`ToastNotification` 을 가져와 **모든
// 라우트**에 렌더한다. 여기 재수출된 것 하나가 무거워지면 전 라우트 번들이 함께 무거워진다.
// 회귀 그물: `scripts/check-terminal-devextreme-transitive.js`(frontend 전체 스코프).
//
// `Loading` 은 여기서 재수출하지 않는다 — 소비자 1개(`DataPanel/DetailPanel.tsx`)가
// `@/components/shared/Feedback/Loading` 을 직접 import 한다. (#381 당시엔 devextreme
// load-panel 이라 뺐고, #341 로 자체 구현이 된 지금은 소비자가 하나뿐이라 그대로 둔다.)
export { MessagePopup } from "./MessagePopup";
export { ToastNotification } from "./ToastNotification";
export { Alert } from "./Alert";

export { showMessage } from "@/stores/shared/messageStore";
export { showToast } from "./ToastNotification";
