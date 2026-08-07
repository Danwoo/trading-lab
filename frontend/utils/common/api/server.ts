// utils/common/api/server.ts
import axios from "axios";
import { NextResponse } from "next/server";

type ProxyMode = "json" | "stream" | "binary" | "passthrough";

/**
 * Backend URL 프록시 호출 — mode 별로 다른 응답 형태 처리.
 *
 * - **json** (default): JSON in/out. axios 사용. `response.data` 반환.
 * - **stream**: SSE 응답 패스스루. `Response(backend.body, { Content-Type: text/event-stream })` 반환.
 * - **binary**: 바이너리 응답 + content-type 보존. `NextResponse(arrayBuffer, ...)` 반환.
 * - **passthrough**: 요청 body 패스스루 (대용량 multipart upload). 호출자가 `body: req.body, duplex: "half"` 지정.
 *
 * `url` 은 항상 호출자가 `BACKEND_SERVICE_URL` 류 환경변수 + 고정 세그먼트로 조립한다 — 이 함수 자체는
 * 호스트를 검증하지 않는다. 과거 `mode: "external"`(사용자 입력 URL 을 검증 없이 그대로 호출하는 용도로
 * 설계됐던 모드)은 호출자 0명으로 제거됐다(#298) — 임의 외부 URL 호출이 필요해지면 허용 호스트
 * 목록·검증을 갖춰 새로 설계할 것.
 */
export async function proxyApiRequest(url: string, options: any = {}, mode: ProxyMode = "json"): Promise<any> {
  switch (mode) {
    case "json": {
      const response = await axios({ url, ...options });
      return response.data;
    }
    case "stream": {
      const resp = await fetch(url, options);
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        return new Response(JSON.stringify(err), {
          status: resp.status,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(resp.body, {
        status: 200,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }
    case "binary": {
      const resp = await fetch(url, options);
      if (!resp.ok) return new NextResponse(null, { status: resp.status });
      const buffer = await resp.arrayBuffer();
      return new NextResponse(buffer, {
        status: 200,
        headers: {
          "Content-Type": resp.headers.get("content-type") || "application/octet-stream",
          "Cache-Control": "public, max-age=3600",
        },
      });
    }
    case "passthrough": {
      const resp = await fetch(url, options);
      const data = await resp.json();
      return NextResponse.json(data, { status: resp.status });
    }
    default: {
      const _exhaustive: never = mode;
      throw new Error(`Unknown proxy mode: ${_exhaustive}`);
    }
  }
}
