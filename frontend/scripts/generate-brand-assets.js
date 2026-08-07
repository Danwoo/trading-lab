#!/usr/bin/env node
// #361 — 브랜드 자산(로고·파비콘)을 소스 SVG 에서 생성한다.
//
//   node scripts/generate-brand-assets.js           # public/ 에 다시 쓴다
//   node scripts/generate-brand-assets.js --check   # 커밋된 것과 바이트 대조만 한다 (CI 게이트)
//
// PR #359 가 두 자산을 "코드로 생성"했다고 적었지만 생성 SVG 도 래스터화 명령도 커밋되지
// 않아 아무도 재현할 수 없었다(#361). 여기서 소스와 명령을 함께 커밋해 "코드로 생성"이
// 검증 가능한 주장이 되게 한다.
//
// **워드마크는 폰트가 아니라 아웃라인 path 다** (scripts/brand/logo.svg). <text> 로 두면
// 결과가 렌더 머신에 설치된 폰트와 freetype 버전에 좌우돼 같은 소스에서 다른 PNG 가 나온다 —
// 커밋 시점의 logo.png 가 정확히 그 상태였다(#361 PR 본문의 실측 참조).
//
// sharp 는 **devDependency** 다. 런타임 코드는 이 자산을 정적 파일로 읽을 뿐 다시 만들지
// 않으므로, 빌드·서버 번들에 네이티브 이미지 라이브러리를 끌고 들어갈 이유가 없다.
//
// fail-closed: 대상이 0건이면 실패한다. 검사한 자산 수를 항상 출력해, 통과가 "일치했다"인지
// "아무것도 안 봤다"인지 읽는 사람이 구분할 수 있게 한다.

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// ICO 컨테이너 사양은 교체 전 파일(#359)과 같게 유지한다 — 단일 32×32 RGBA PNG-in-ICO.
const ASSETS = [
  { source: "scripts/brand/logo.svg", output: "public/logo.png", container: "png" },
  { source: "scripts/brand/favicon.svg", output: "public/favicon.ico", container: "ico", size: 32 },
];

/** 단일 이미지 ICO 로 감싼다 (6바이트 헤더 + 16바이트 엔트리 + PNG 페이로드). */
function wrapIco(png, size) {
  const header = Buffer.alloc(22);
  header.writeUInt16LE(0, 0); // reserved
  header.writeUInt16LE(1, 2); // type: 1 = icon
  header.writeUInt16LE(1, 4); // image count
  header.writeUInt8(size % 256, 6); // width (256 은 0 으로 적는 사양)
  header.writeUInt8(size % 256, 7); // height
  header.writeUInt8(0, 8); // palette color count (0 = 팔레트 없음)
  header.writeUInt8(0, 9); // reserved
  header.writeUInt16LE(1, 10); // color planes
  header.writeUInt16LE(32, 12); // bits per pixel
  header.writeUInt32LE(png.length, 14);
  header.writeUInt32LE(header.length, 18);
  return Buffer.concat([header, png]);
}

async function render(asset) {
  const svg = readFileSync(path.join(frontendDir, asset.source));
  const png = await sharp(svg).png().toBuffer();
  return asset.container === "ico" ? wrapIco(png, asset.size) : png;
}

const check = process.argv.includes("--check");
const problems = [];
let done = 0;

if (ASSETS.length === 0) {
  console.error("[brand-assets] 생성 대상이 0건이다 — 목록 지정이 현실과 어긋났다");
  process.exit(1);
}

for (const asset of ASSETS) {
  const outputPath = path.join(frontendDir, asset.output);
  const built = await render(asset);
  if (check) {
    let committed;
    try {
      committed = readFileSync(outputPath);
    } catch {
      problems.push(`${asset.output}: 커밋된 파일이 없다`);
      continue;
    }
    if (!built.equals(committed)) {
      problems.push(
        `${asset.output}: 소스에서 생성한 것과 커밋된 것이 다르다 ` +
          `(생성 ${built.length} B / 커밋 ${committed.length} B). ` +
          `node scripts/generate-brand-assets.js 로 다시 만들어 커밋하라`,
      );
      continue;
    }
  } else {
    writeFileSync(outputPath, built);
  }
  done += 1;
  console.log(`  ${check ? "일치" : "생성"}: ${asset.output} (${built.length} B) ← ${asset.source}`);
}

console.log(`[brand-assets] ${check ? "대조" : "생성"} ${done}/${ASSETS.length}건`);

if (problems.length > 0) {
  console.error("\n[brand-assets] 실패:");
  for (const problem of problems) console.error(`  - ${problem}`);
  process.exit(1);
}
if (done !== ASSETS.length) {
  console.error(`[brand-assets] 처리한 자산이 ${done}건 — 기대치 ${ASSETS.length}건과 다르다`);
  process.exit(1);
}
