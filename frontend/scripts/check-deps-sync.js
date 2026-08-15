#!/usr/bin/env node
// #317 — package-lock.json 과 실제 설치 상태(node_modules)가 어긋나면 시끄럽게 실패한다.
//
// 의존성을 추가한 PR 이 머지돼도 로컬 node_modules 는 자동으로 따라오지 않는다. 그 상태로
// 개발 서버·테스트를 돌리면 "특정 페이지에서만 500"·"vitest: not found" 처럼 원인이 한눈에
// 안 보이는 실패가 난다. 여기서 미리 잡아 실행할 명령까지 알려준다 — 자동 설치는 하지 않는다
// (조용한 자동 복구는 "왜 낡았는지"를 숨기고, npm ci 는 네트워크·시간이 드는 재설치라 predev/
// pretest 안에서 말없이 돌리면 그 자체로 새로운 지연·네트워크 의존을 심는다).
//
// 검사는 두 단으로 한다 (둘 다 합쳐도 실측 40ms 안팎 — npm ls 류 전수 스캔 없이 끝난다):
//
// 1) package-lock.json 의 "packages" 맵과 node_modules/.package-lock.json(npm 이 설치 직후
//    실제 트리를 그대로 적어 두는 스냅샷 파일)을 대조한다. "머지로 새 의존성이 들어왔는데
//    npm install 을 안 돌린" 케이스(전이 의존성 포함 전수)를 잡는다 — 디스크 접근 없이 두
//    파일만 읽으면 끝난다.
// 2) package.json 의 **직접** 의존성만 골라 node_modules/<pkg>/package.json 을 실제로 열어
//    버전을 대조한다. 1번은 두 잠금 파일끼리만 비교하므로 node_modules 에서 디렉터리를 통째로
//    지워도(스냅샷 파일 자체는 그대로이므로) 못 잡는다 — 직접 의존성 수(수십 개)만 이렇게
//    실물 확인해 그 구멍을 막는다. 전이 의존성까지 전부 실물 확인하지 않는 이유는 수백 개를
//    매번 열어보는 비용 대비, "새 패키지 import 가 즉시 500" 실패는 거의 항상 직접 의존성에서
//    난다(#317 실사례: @tanstack/react-table·vitest 등 모두 직접 의존성).
//
// 플랫폼별 optional 의존성(os/cpu/libc 불일치)은 애초에 이 머신에 설치되지 않는 게 정상이라
// 대조에서 제외한다 — 안 그러면 다른 OS/아키텍처/libc 에서 잠긴 패키지가 매번 오탐을 낸다.
// os/cpu/libc 필드가 전혀 없는 optional(다른 optional 패키지 밑에서만 전이적으로 필요한
// 패키지, 예: sharp 의 wasm 폴백 런타임)도 설치 여부가 npm 버전·상황에 따라 갈릴 수 있어
// 검사에서 제외한다 — 이런 패키지는 런타임 코드가 직접 import 하지 않는다.

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const lockPath = path.join(frontendDir, "package-lock.json");
const installedLockPath = path.join(frontendDir, "node_modules/.package-lock.json");

function fail(reason, detailLines) {
  console.error(`\n[check-deps-sync] ${reason}`);
  if (detailLines?.length) {
    console.error(detailLines.join("\n"));
  }
  console.error("\n  다음을 실행하세요:\n    cd frontend && npm ci\n");
  process.exit(1);
}

if (!existsSync(installedLockPath)) {
  fail("frontend/node_modules 가 설치돼 있지 않습니다 (node_modules/.package-lock.json 없음).");
}

const lock = JSON.parse(readFileSync(lockPath, "utf8"));
const installed = JSON.parse(readFileSync(installedLockPath, "utf8"));

// glibc 시스템은 process.report 헤더에 glibcVersionRuntime 을 채운다 — musl(alpine 등)은 없다.
const libc = process.report.getReport().header.glibcVersionRuntime !== undefined ? "glibc" : "musl";

function platformMismatch(pkg) {
  if (Array.isArray(pkg.os) && !pkg.os.includes(process.platform)) return true;
  if (Array.isArray(pkg.cpu) && !pkg.cpu.includes(process.arch)) return true;
  if (Array.isArray(pkg.libc) && !pkg.libc.includes(libc)) return true;
  return false;
}

const stale = [];
for (const [key, pkg] of Object.entries(lock.packages ?? {})) {
  if (key === "") continue; // 루트 프로젝트 자신 — node_modules 에 설치되는 대상이 아니다
  if (pkg.optional) {
    const hasPlatformField = Boolean(pkg.os || pkg.cpu || pkg.libc);
    const skip = hasPlatformField ? platformMismatch(pkg) : true;
    if (skip) continue;
  }
  const installedPkg = installed.packages?.[key];
  if (!installedPkg) {
    stale.push(`  - 없음: ${key}@${pkg.version}`);
  } else if (installedPkg.version !== pkg.version) {
    stale.push(`  - 버전 불일치: ${key} (잠금 ${pkg.version} / 설치됨 ${installedPkg.version})`);
  }
}

// 2단계 — 직접 의존성은 스냅샷이 아니라 실제 node_modules 디렉터리를 연다. node_modules
// 에서 디렉터리가 통째로 사라져도 node_modules/.package-lock.json 자체는 그대로일 수 있어
// 1단계만으로는 못 잡는다.
const rootDeps = lock.packages?.[""] ?? {};
const directDeps = { ...rootDeps.dependencies, ...rootDeps.devDependencies };
for (const [name, range] of Object.entries(directDeps)) {
  const key = `node_modules/${name}`;
  const lockedVersion = lock.packages?.[key]?.version;
  if (!lockedVersion) continue; // optional 로만 존재하거나(플랫폼 불일치 등) lock 에 없음 — 1단계에서 이미 다룸
  const pkgJsonPath = path.join(frontendDir, key, "package.json");
  if (!existsSync(pkgJsonPath)) {
    stale.push(`  - 없음(직접 의존성): ${name}@${lockedVersion} (범위 ${range})`);
    continue;
  }
  const installedVersion = JSON.parse(readFileSync(pkgJsonPath, "utf8")).version;
  if (installedVersion !== lockedVersion) {
    stale.push(`  - 버전 불일치(직접 의존성): ${name} (잠금 ${lockedVersion} / 설치됨 ${installedVersion})`);
  }
}

if (stale.length > 0) {
  const shown = stale.slice(0, 20);
  const rest = stale.length - shown.length;
  fail(
    `package-lock.json 과 실제 설치 상태가 어긋납니다 (${stale.length}건).`,
    rest > 0 ? [...shown, `  ... 외 ${rest}건`] : shown,
  );
}
