// @vitest-environment node
//
// #439 F21 — 참여 멤버 추가가 **구조적으로 불가능했다.**
//
// 프론트는 `accountId` 값을 `git_id` 라는 이름의 필드에 담아 보냈고, 백엔드는 `account_id` 를
// 필수로 받는다(`SchedulerMemberIn`). 화면에 있는 기능이 원리적으로 422 였다:
//
//   {"loc":["body","account_id"],"msg":"Field required","hint":"계정 id — 100자까지."}
//
// **백엔드가 SoT 다** (루트 `CLAUDE.md`: 「backend 가 SoT, 경로 변경 시 frontend lockstep」).
//
// **런타임 호출로는 이 결함을 못 잡는다** — 타입은 실행 시점에 사라지므로, 테스트가 옳은 모양을
// 넘겨 주면 그대로 통과한다(실제로 처음엔 그렇게 헛초록이 났다). 그래서 **양쪽 소스를 읽어
// 대조한다** — 이름이 한쪽에서 바뀌면 여기서 걸린다.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const BACKEND_SCHEMA = "../backend-service/app/schemas/scheduler/scheduler_schema.py";
const FRONTEND_SERVICE = "services/scheduler/schedulerService.ts";

const read = (path: string) => readFileSync(resolve(process.cwd(), path), "utf8");

/** 백엔드 `SchedulerMemberIn` 의 **필수** 필드 이름 — `Field(...` 로 시작하는 것. */
function backendRequired(): string[] {
  const source = read(BACKEND_SCHEMA);
  const start = source.indexOf("class SchedulerMemberIn");
  expect(start, "SchedulerMemberIn 을 못 찾았다 — 스키마가 옮겨졌다면 이 그물을 고쳐라").toBeGreaterThan(-1);
  const next = source.indexOf("\nclass ", start + 1);
  const body = source.slice(start, next === -1 ? undefined : next);
  return [...body.matchAll(/^\s{4}(\w+):[^=]+=\s*Field\(\s*\.\.\./gm)].map((m) => m[1]);
}

/** 프론트 `addSchedulerMember` 가 **선언한** 본문 필드 이름 (`?` 는 선택). */
function frontendDeclared(): { name: string; optional: boolean }[] {
  const source = read(FRONTEND_SERVICE);
  const start = source.indexOf("export const addSchedulerMember");
  expect(start, "addSchedulerMember 를 못 찾았다 — 서비스가 옮겨졌다면 이 그물을 고쳐라").toBeGreaterThan(-1);
  const shape = source.slice(start, source.indexOf("=> {", start));
  const inner = shape.slice(shape.indexOf("data: {") + 7, shape.indexOf("}", shape.indexOf("data: {")));
  return inner
    .split(";")
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const [left] = part.split(":");
      return { name: left.replace("?", "").trim(), optional: left.includes("?") };
    });
}

describe("멤버 추가 계약이 백엔드와 맞는다", () => {
  const required = backendRequired();
  const declared = frontendDeclared();

  it("양쪽을 읽었다 — 0건이면 그물이 죽은 것이다", () => {
    expect(required.length).toBeGreaterThan(0);
    expect(declared.length).toBeGreaterThan(0);
    expect(required).toContain("account_id");
  });

  it("백엔드의 필수 필드를 프론트가 **필수로** 선언한다", () => {
    for (const field of required) {
      const found = declared.find((d) => d.name === field);
      expect(found, `프론트가 「${field}」 를 선언하지 않는다 — 백엔드는 필수로 받는다`).toBeTruthy();
      expect(found!.optional, `「${field}」 는 백엔드가 필수인데 프론트가 선택으로 뒀다`).toBe(false);
    }
  });

  it("백엔드가 모르는 필드를 선언하지 않는다", () => {
    const source = read(BACKEND_SCHEMA);
    const start = source.indexOf("class SchedulerMemberIn");
    const next = source.indexOf("\nclass ", start + 1);
    const body = source.slice(start, next === -1 ? undefined : next);
    const known = [...body.matchAll(/^\s{4}(\w+):/gm)].map((m) => m[1]);

    for (const field of declared) {
      expect(known, `프론트가 보내는 「${field.name}」 를 백엔드가 모른다`).toContain(field.name);
    }
  });
});
