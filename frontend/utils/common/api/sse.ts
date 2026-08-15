export interface SSEChunk {
  // 옵션 — DevActivity 챗(`{status, content}`)처럼 type 판별자 없이 필드만으로 분기하는
  // 이벤트도 있다. type 이 있는 소비처(research-chat)는 자기 이벤트
  // 타입에서 required 로 좁혀 쓴다.
  type?: string;
  error?: string;
  [key: string]: any;
}

export interface FetchSSEOptions<T extends SSEChunk = SSEChunk> {
  url: string;
  body?: any;
  onChunk: (chunk: T) => void;
  signal?: AbortSignal;
}

export async function fetchSSE<T extends SSEChunk = SSEChunk>({
  url,
  body,
  onChunk,
  signal,
}: FetchSSEOptions<T>): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    // axios-shape 으로 throw 해서 getApiErrorMessage 가 동일 처리
    const err = new Error(`HTTP ${response.status}`) as any;
    err.response = { data: errorData, status: response.status };
    throw err;
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("ReadableStream not supported");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data: ")) continue;

        const jsonStr = trimmed.slice(6);
        try {
          const chunk = JSON.parse(jsonStr) as T;

          if (chunk.type === "error") {
            const err = new Error("HTTP 500") as any;
            err.response = { data: { detail: chunk.error || "스트리밍 중 오류가 발생했습니다." }, status: 500 };
            throw err;
          }

          onChunk(chunk);
        } catch (e) {
          if (e instanceof SyntaxError) {
            console.warn("Failed to parse SSE chunk:", jsonStr);
            continue;
          }
          throw e;
        }
      }
    }

    // Process any remaining data in buffer
    if (buffer.trim() && buffer.trim().startsWith("data: ")) {
      const jsonStr = buffer.trim().slice(6);
      try {
        const chunk = JSON.parse(jsonStr) as T;
        if (chunk.type === "error") {
          const err = new Error("HTTP 500") as any;
          err.response = { data: { detail: chunk.error || "스트리밍 중 오류가 발생했습니다." }, status: 500 };
          throw err;
        }
        onChunk(chunk);
      } catch (e) {
        if (!(e instanceof SyntaxError)) throw e;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * 개행 구분 JSON(NDJSON) 스트림 소비 — `{json}\n`, `data:` 접두사 없음.
 *
 * `fetchSSE` 와 구조는 같지만 줄 파싱만 다르다: `fetchSSE` 는 `data: ` 접두사를 전제하나
 * (multi-agent) `/agent/example-ai` 는 접두사 없는 순수 NDJSON 을 흘린다(agent_router.py).
 * 따라서 fetchSSE 로는 모든 이벤트가 스킵되어(`startsWith("data: ")` 실패) 못 먹는다.
 *
 * 각 비어있지 않은 줄을 그대로 `JSON.parse` 해 `onChunk`. `type === "error"` 이벤트는
 * example-ai 계약상 `{type:"error", message}` 이므로 그 `message` 를 axios-shape 로 throw
 * 해 `getApiErrorMessage` 가 fetchSSE 와 동일하게 처리하도록 한다. 미완성 마지막 줄은 버퍼 보존.
 *
 * 룰6: 이 파일(utils/common/api/sse.ts)은 raw fetch 허용 예외 목록에 포함된다 —
 * 서비스 파일은 raw fetch 를 직접 쓰지 말고 이 헬퍼를 호출한다.
 */
export async function fetchNDJSON<T extends SSEChunk = SSEChunk>({
  url,
  body,
  onChunk,
  signal,
}: FetchSSEOptions<T>): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    // axios-shape 으로 throw 해서 getApiErrorMessage 가 동일 처리
    const err = new Error(`HTTP ${response.status}`) as any;
    err.response = { data: errorData, status: response.status };
    throw err;
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("ReadableStream not supported");

  const decoder = new TextDecoder();
  let buffer = "";

  const handleLine = (raw: string): void => {
    const trimmed = raw.trim();
    if (!trimmed) return; // 빈 줄(개행 구분) 스킵
    let chunk: T;
    try {
      chunk = JSON.parse(trimmed) as T;
    } catch (e) {
      if (e instanceof SyntaxError) {
        console.warn("Failed to parse NDJSON chunk:", trimmed);
        return;
      }
      throw e;
    }
    if (chunk.type === "error") {
      // example-ai error 이벤트는 {type:"error", message} — message 를 detail 로 실어 500 shape throw
      const err = new Error("HTTP 500") as any;
      err.response = {
        data: { detail: (chunk as any).message || "스트리밍 중 오류가 발생했습니다." },
        status: 500,
      };
      throw err;
    }
    onChunk(chunk);
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      // Keep the last incomplete line in the buffer
      buffer = lines.pop() || "";

      for (const line of lines) {
        handleLine(line);
      }
    }

    // Process any remaining data in buffer
    if (buffer.trim()) {
      handleLine(buffer);
    }
  } finally {
    reader.releaseLock();
  }
}
