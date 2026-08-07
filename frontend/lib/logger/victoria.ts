import { env } from "@/env";

const VICTORIALOGS_URL = env.VICTORIALOGS_URL?.replace(/\/+$/, "");

if (VICTORIALOGS_URL) {
  const PUSH_URL = `${VICTORIALOGS_URL}/insert/jsonline?_msg_field=message&_time_field=timestamp&_stream_fields=service,level`;

  const serializeArg = (arg: unknown): string => {
    if (arg instanceof Error) return arg.stack ?? `${arg.name}: ${arg.message}`;
    if (typeof arg === "string") return arg;
    try {
      return JSON.stringify(arg);
    } catch {
      return String(arg);
    }
  };

  const push = async (level: "ERROR" | "WARNING", message: string): Promise<void> => {
    try {
      await fetch(PUSH_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          timestamp: new Date().toISOString(),
          service: env.SERVICE_NAME,
          level,
          message,
        }),
      });
    } catch {
      // never let logging crash the app
    }
  };

  const originalError = console.error;
  const originalWarn = console.warn;

  console.error = (...args: unknown[]) => {
    void push("ERROR", args.map(serializeArg).join(" "));
    originalError(...args);
  };
  console.warn = (...args: unknown[]) => {
    void push("WARNING", args.map(serializeArg).join(" "));
    originalWarn(...args);
  };

  // process.env.NEXT_RUNTIME 직접 사용 (Edge build dead code elimination 위해 — env 객체로는 안 됨)
  if (process.env.NEXT_RUNTIME === "nodejs") {
    process.on("uncaughtException", (err) => {
      void push("ERROR", `uncaughtException: ${err.stack ?? err.message}`);
    });
    process.on("unhandledRejection", (reason) => {
      void push(
        "ERROR",
        `unhandledRejection: ${reason instanceof Error ? (reason.stack ?? reason.message) : String(reason)}`,
      );
    });
  }
}

export {};
