#!/usr/bin/env node
// THIRD-PARTY-NOTICES.md §3 Pretendard woff 재검증용 — verify-woff2-name-table.js 와 짝을 이룬다.
// WOFF(1) 은 테이블별 zlib(raw deflate) 압축이라 woff2(brotli, 전체 스트림 하나)와 파싱 방식이
// 다르다. Node 표준 라이브러리(zlib.inflateSync)만 사용, 외부 의존성 없음.
//
// 사용법: node scripts/verify-woff-name-table.js public/font/woff/*.woff
//   전부 일치하면 exit 0, 하나라도 어긋나거나 대상이 0건이면 exit 1(fail-closed).
import { readFileSync } from "node:fs";
import { inflateSync } from "node:zlib";

function decodeNameString(raw, platformID) {
  if (platformID === 3 || platformID === 0) {
    // Windows(3) 또는 Unicode(0) 플랫폼 — UTF-16BE
    return Buffer.from(raw).swap16().toString("utf16le");
  }
  return raw.toString("latin1");
}

function extractNameStrings(nameBuf) {
  const count = nameBuf.readUInt16BE(2);
  const stringOffset = nameBuf.readUInt16BE(4);
  const wanted = { 0: "Copyright", 5: "Version", 13: "License", 14: "LicenseURL" };
  const found = {};
  for (let i = 0; i < count; i++) {
    const base = 6 + i * 12;
    const platformID = nameBuf.readUInt16BE(base);
    const nameID = nameBuf.readUInt16BE(base + 6);
    const length = nameBuf.readUInt16BE(base + 8);
    const strOffset = nameBuf.readUInt16BE(base + 10);
    if (!(nameID in wanted)) continue;
    const dataStart = stringOffset + strOffset;
    const raw = nameBuf.subarray(dataStart, dataStart + length);
    if (!(nameID in found)) found[nameID] = decodeNameString(raw, platformID);
  }
  return found;
}

function readWoffNameTable(buf) {
  // 헤더 44바이트: signature(4) flavor(4) length(4) numTables(2) reserved(2) totalSfntSize(4)
  // majorVersion(2) minorVersion(2) metaOffset(4) metaLength(4) metaOrigLength(4)
  // privOffset(4) privLength(4)
  const signature = buf.toString("ascii", 0, 4);
  if (signature !== "wOFF") throw new Error(`시그니처 불일치: ${signature}`);
  const numTables = buf.readUInt16BE(12);
  let pos = 44;
  for (let i = 0; i < numTables; i++) {
    const tag = buf.toString("ascii", pos, pos + 4);
    const offset = buf.readUInt32BE(pos + 4);
    const compLength = buf.readUInt32BE(pos + 8);
    const origLength = buf.readUInt32BE(pos + 12);
    pos += 20;
    if (tag === "name") {
      const raw = buf.subarray(offset, offset + compLength);
      // compLength === origLength 면 비압축 저장(WOFF1 스펙) — 그대로 쓴다.
      return compLength < origLength ? inflateSync(raw) : raw;
    }
  }
  throw new Error("name 테이블 없음");
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("사용법: node scripts/verify-woff-name-table.js <woff-file> [...]");
  process.exit(1);
}

const EXPECTED = {
  copyright: "Copyright © 2023 Kil Hyung-jin",
  license: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
  licenseUrl: "http://scripts.sil.org/OFL",
};

let allOk = true;
let checked = 0;
for (const file of files) {
  const buf = readFileSync(file);
  const nameBuf = readWoffNameTable(buf);
  const strings = extractNameStrings(nameBuf);
  const copyrightOk = (strings[0] || "").includes(EXPECTED.copyright);
  const licenseOk = (strings[13] || "").includes(EXPECTED.license);
  const urlOk = (strings[14] || "").includes(EXPECTED.licenseUrl);
  const version = strings[5] || "(nameID 5 없음)";
  const ok = copyrightOk && licenseOk && urlOk;
  checked += 1;
  if (!ok) allOk = false;
  console.log(
    `${file}: copyright=${copyrightOk ? "OK" : "FAIL(" + strings[0] + ")"} ` +
      `license=${licenseOk ? "OK" : "FAIL(" + strings[13] + ")"} ` +
      `licenseUrl=${urlOk ? "OK" : "FAIL(" + strings[14] + ")"} ` +
      `version="${version}"`,
  );
}
console.log(`\n검사 대상: ${checked}개 파일 / 전부 일치: ${allOk ? "예" : "아니오"}`);
if (checked === 0) {
  console.error("검사 대상 0건 — 실패로 처리한다 (fail-closed).");
  process.exit(1);
}
if (!allOk) process.exit(1);
