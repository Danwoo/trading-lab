import { useState, useEffect, useCallback, useRef } from "react";

/** WebSocket 관련 이벤트 핸들러 타입 정의 */
type MessageHandler = (data: any) => void;
type ErrorHandler = (event: Event) => void;
type OpenHandler = () => void;
type CloseHandler = () => void;

interface Props {
  getUrl: () => Promise<string>;
  onMessage: MessageHandler;
  onError?: ErrorHandler;
  onOpen?: OpenHandler;
  onClose?: CloseHandler;
  shouldReconnect?: boolean;
  reconnectInterval?: number;
  isActive?: boolean;
}

/**
 * WebSocket 연결 및 자동 재연결을 관리하는 커스텀 훅
 * @returns 연결 상태(readyState)와 메시지 전송 함수(sendMessage)
 */
export function useWebSocketService({
  getUrl,
  onMessage,
  onError,
  onOpen,
  onClose,
  shouldReconnect = true,
  reconnectInterval = 3000,
  isActive = true,
}: Props) {
  /** WebSocket 연결 상태 (0:CONNECTING, 1:OPEN, 2:CLOSING, 3:CLOSED) */
  const [readyState, setReadyState] = useState<number>(WebSocket.CLOSED);

  /** 현재 WebSocket 인스턴스 참조 */
  const websocketRef = useRef<WebSocket | null>(null);

  /** 재연결 타이머 ID 관리 */
  const reconnectTimeoutRef = useRef<number | null>(null);

  /** props 콜백을 최신 상태로 유지하기 위한 ref */
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);

  /** 콜백 업데이트 */
  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
  }, [onMessage, onError, onOpen, onClose]);

  /** 재연결 타이머 제거 */
  const clearReconnectTimeout = () => {
    if (reconnectTimeoutRef.current !== null) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  };

  /** WebSocket 연결 및 이벤트 핸들러 등록 */
  const connectWebSocket = useCallback(async () => {
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }

    setReadyState(WebSocket.CONNECTING);
    const url = await getUrl();
    const ws = new WebSocket(url);
    websocketRef.current = ws;

    ws.onopen = () => {
      setReadyState(WebSocket.OPEN);
      onOpenRef.current?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch (error) {
        console.error("WebSocket message parse error:", error);
      }
    };

    ws.onerror = (event) => {
      setReadyState(WebSocket.CLOSED);
      onErrorRef.current?.(event);
    };

    ws.onclose = () => {
      setReadyState(WebSocket.CLOSED);
      onCloseRef.current?.();
      clearReconnectTimeout();

      // 자동 재연결
      if (shouldReconnect && isActive) {
        reconnectTimeoutRef.current = window.setTimeout(() => {
          if (isActive) connectWebSocket();
        }, reconnectInterval);
      }
    };
  }, [getUrl, shouldReconnect, reconnectInterval, isActive]);

  /** 활성 상태(isActive)에 따라 연결/해제 제어 */
  useEffect(() => {
    if (isActive) {
      connectWebSocket();
    } else {
      clearReconnectTimeout();
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
      setReadyState(WebSocket.CLOSED);
    }

    // 언마운트 시 정리
    return () => {
      clearReconnectTimeout();
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
    };
  }, [connectWebSocket, isActive]);

  /** WebSocket 메시지 전송 함수 */
  const sendMessage = useCallback((message: any) => {
    const ws = websocketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    } else {
      console.warn("WebSocket is not open. State:", ws?.readyState);
    }
  }, []);

  /** 수동 재연결 (서버측 끊김 후 동일 isActive 상태에서 재연결 시) */
  const reconnect = useCallback(() => {
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }
    connectWebSocket();
  }, [connectWebSocket]);

  return { readyState, sendMessage, reconnect };
}
