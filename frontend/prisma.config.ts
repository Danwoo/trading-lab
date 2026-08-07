import { defineConfig } from "prisma/config";

// prisma generate 는 스키마만 필요하므로 env.ts 전체 검증을 트리거하지 않도록
// process.env 를 직접 읽는다 (db push 는 env-cmd 가 DATABASE_URL 을 주입).
export default defineConfig({
  schema: "prisma/schema.prisma",
  datasource: {
    url: process.env.DATABASE_URL ?? "",
  },
});
