// stores/shared/messageStore.ts
import { create } from "zustand";

/**
 * 큐에 들어가는 메시지 한 건. `MessagePopup` 이 닫힘 애니메이션 동안 그릴 내용을 로컬에
 * 캐시하려고 이 타입을 쓴다(#394) — 그래서 export 한다.
 */
export interface MessageItem {
  id: string;
  title: string;
  content: React.ReactNode;
  type: "alert" | "confirm";
  confirmText?: string;
  cancelText?: string;
  resolve?: (value: boolean) => void;
  onConfirm?: () => void | Promise<void>;
  onCancel?: () => void | Promise<void>;
  width?: number | string;
  height?: number | string;
  confirmButtonType?: "default" | "success" | "danger" | "normal";
  cancelButtonType?: "default" | "success" | "danger" | "normal";
  confirmButtonStyle?: "text" | "outlined" | "contained";
  cancelButtonStyle?: "text" | "outlined" | "contained";
}

interface MessageOptions {
  type?: "alert" | "confirm";
  confirmText?: string;
  cancelText?: string;
  width?: number | string;
  height?: number | string;
  confirmButtonType?: "default" | "success" | "danger" | "normal";
  cancelButtonType?: "default" | "success" | "danger" | "normal";
  confirmButtonStyle?: "text" | "outlined" | "contained";
  cancelButtonStyle?: "text" | "outlined" | "contained";
  callback?: {
    onConfirm?: () => void | Promise<void>;
    onCancel?: () => void | Promise<void>;
  };
}

/**
 * 한 메시지가 닫힌 뒤 다음 메시지를 꺼내기까지의 여백(ms).
 *
 * `MessagePopup` 의 닫힘 애니메이션(`dialog-scale-out`/`dialog-fade-out`, `tailwind.config.mjs`
 * 에서 **150ms**)이 끝난 뒤에 다음 메시지가 열리게 맞춘 값이다. 종전 값 100ms 는 애니메이션보다
 * 짧아, 큐에 두 건이 연달아 있으면 닫히는 중에 다음 팝업이 열려 상태가 겹쳤다
 * (#394 — 종전엔 `MessagePopup` 이 즉시 언마운트돼 애니메이션 자체가 없어서 안 보이던 문제다).
 * 애니메이션 시간을 바꾸면 이 값도 함께 바꾼다 — 값이 갈리면 겹침이 되돌아온다.
 */
export const MESSAGE_CLOSE_ANIMATION_MS = 150;

// 기본값 상수 정의
const DEFAULT_MESSAGE_CONFIG = {
  type: "alert" as const,
  confirmText: "확인",
  cancelText: "취소",
  width: 400,
  height: "auto" as const,
  confirmButtonType: "default" as const,
  cancelButtonType: "normal" as const,
  confirmButtonStyle: "contained" as const,
  cancelButtonStyle: "outlined" as const,
};

interface MessageStore {
  messages: MessageItem[];
  currentMessage: MessageItem | null;

  showMessage: (title: string, content: React.ReactNode, options?: MessageOptions) => Promise<boolean>;

  processNext: () => void;
  resolveMessage: (result: boolean) => void;
  handleConfirm: () => void;
  handleCancel: () => void;
}

export const useMessageStore = create<MessageStore>((set, get) => ({
  messages: [],
  currentMessage: null,

  showMessage: (title: string, content: React.ReactNode, options: MessageOptions = {}): Promise<boolean> => {
    return new Promise((resolve) => {
      const id = Date.now().toString() + Math.random();
      const newMessage: MessageItem = {
        id,
        title,
        content,
        type: options.type || DEFAULT_MESSAGE_CONFIG.type,
        confirmText: options.confirmText || DEFAULT_MESSAGE_CONFIG.confirmText,
        cancelText: options.cancelText || DEFAULT_MESSAGE_CONFIG.cancelText,
        width: options.width || DEFAULT_MESSAGE_CONFIG.width,
        height: options.height || DEFAULT_MESSAGE_CONFIG.height,
        confirmButtonType: options.confirmButtonType || DEFAULT_MESSAGE_CONFIG.confirmButtonType,
        cancelButtonType: options.cancelButtonType || DEFAULT_MESSAGE_CONFIG.cancelButtonType,
        confirmButtonStyle: options.confirmButtonStyle || DEFAULT_MESSAGE_CONFIG.confirmButtonStyle,
        cancelButtonStyle: options.cancelButtonStyle || DEFAULT_MESSAGE_CONFIG.cancelButtonStyle,
        resolve,
        onConfirm: options.callback?.onConfirm,
        onCancel: options.callback?.onCancel,
      };

      set((state) => ({
        messages: [...state.messages, newMessage],
      }));

      if (!get().currentMessage) {
        setTimeout(() => get().processNext(), 0);
      }
    });
  },

  /**
   * 큐에서 다음 메시지를 꺼내 화면에 올린다. **이미 떠 있는 메시지가 있으면 아무것도 하지
   * 않는다(멱등)** — 이 가드가 #408 의 뿌리를 막는다.
   *
   * 예약은 두 곳에서 걸리고 둘 다 중복될 수 있다:
   * - `showMessage` 는 `!currentMessage` 일 때 0ms 예약을 건다. 같은 tick 에 두 번 호출되면
   *   두 호출 모두 조건을 만족해(아직 아무것도 안 떴다) **예약이 두 번** 걸린다.
   * - `resolveMessage` 는 큐가 비어 있어도 150ms 예약을 건다. 그 창 안에 새 메시지가 뜨면
   *   **뒤늦은 타이머**가 남는다.
   *
   * 가드가 없으면 그 여분의 실행이 떠 있는 메시지를 다음 건으로 덮어썼고, 덮인 메시지의
   * `resolve` 는 아무도 부르지 않아 `await showMessage(...)` 한 호출부가 영영 멈췄다.
   * 덮이지 않은 메시지는 큐에 그대로 남아 다음 `resolveMessage` 때 정상적으로 열린다.
   */
  processNext: () => {
    const { messages, currentMessage } = get();
    if (currentMessage) return;
    if (messages.length > 0) {
      set({
        currentMessage: messages[0],
        messages: messages.slice(1),
      });
    }
  },

  resolveMessage: (result: boolean) => {
    const { currentMessage } = get();
    if (currentMessage?.resolve) {
      currentMessage.resolve(result);
    }
    set({ currentMessage: null });
    setTimeout(() => get().processNext(), MESSAGE_CLOSE_ANIMATION_MS);
  },

  handleConfirm: async () => {
    const { currentMessage } = get();

    if (currentMessage?.onConfirm) {
      try {
        await currentMessage.onConfirm();
      } catch (error) {
        console.error("Confirm callback error:", error);
      }
    }

    get().resolveMessage(true);
  },

  handleCancel: async () => {
    const { currentMessage } = get();

    if (currentMessage?.onCancel) {
      try {
        await currentMessage.onCancel();
      } catch (error) {
        console.error("Cancel callback error:", error);
      }
    }

    get().resolveMessage(false);
  },
}));

export const showMessage = (title: string, content: React.ReactNode, options?: MessageOptions): Promise<boolean> => {
  return useMessageStore.getState().showMessage(title, content, options);
};
