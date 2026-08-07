#!/usr/bin/env node
// THIRD-PARTY-NOTICES.md §3 Pretendard woff2 재검증용 — woff2 는 brotli 압축이라 이름·크기만으로는
// woff 형제 파일과의 라이선스 동일성을 확인할 수 없다(woff2 는 brotli 라 항상 더 작다. woff 는
// zlib 이라 다른 압축이다). 이 스크립트는 WOFF2 테이블 디렉터리를 직접 파싱하고
// Node 표준 라이브러리(zlib.brotliDecompressSync, Node 11+)로 brotli 스트림을 풀어 OpenType
// `name` 테이블에서 저작권·라이선스·버전 문자열을 읽는다. 외부 의존성 없음 — npm install 불필요.
//
// 사용법: node scripts/verify-woff2-name-table.js public/font/woff2/*.woff2
//   전부 일치하면 exit 0, 하나라도 어긋나거나 대상이 0건이면 exit 1(fail-closed).
import { readFileSync } from "node:fs";
import { brotliDecompressSync } from "node:zlib";

// WOFF2 스펙(known table tags, index 0~62)
const KNOWN_TAGS = [
  "cmap",
  "head",
  "hhea",
  "hmtx",
  "maxp",
  "name",
  "OS/2",
  "post",
  "cvt ",
  "fpgm",
  "glyf",
  "loca",
  "prep",
  "CFF ",
  "VORG",
  "EBDT",
  "EBLC",
  "gasp",
  "hdmx",
  "kern",
  "LTSH",
  "PCLT",
  "VDMX",
  "vhea",
  "vmtx",
  "BASE",
  "GDEF",
  "GPOS",
  "GSUB",
  "EBSC",
  "JSTF",
  "MATH",
  "CBDT",
  "CBLC",
  "COLR",
  "CPAL",
  "SVG ",
  "sbix",
  "acnt",
  "avar",
  "bdat",
  "bloc",
  "bsln",
  "cvar",
  "fdsc",
  "feat",
  "fmtx",
  "fvar",
  "gvar",
  "hsty",
  "just",
  "lcar",
  "mort",
  "morx",
  "opbd",
  "prop",
  "trak",
  "Zapf",
  "Silf",
  "Glat",
  "Gloc",
  "Feat",
  "Sill",
];

function readUIntBase128(buf, pos) {
  let value = 0;
  let p = pos;
  for (let i = 0; i < 5; i++) {
    const b = buf[p];
    p += 1;
    if (i === 0 && b === 0x80) throw new Error("UIntBase128: 선행 0 바이트 금지");
    value = (value << 7) | (b & 0x7f);
    if ((b & 0x80) === 0) return [value >>> 0, p];
  }
  throw new Error("UIntBase128: 5바이트 초과");
}

function parseWoff2TableDirectory(buf) {
  // 헤더 48바이트: signature(4) flavor(4) length(4) numTables(2) reserved(2)
  // totalSfntSize(4) totalCompressedSize(4) majorVersion(2) minorVersion(2)
  // metaOffset(4) metaLength(4) metaOrigLength(4) privOffset(4) privLength(4)
  const signature = buf.toString("ascii", 0, 4);
  if (signature !== "wOF2") throw new Error(`시그니처 불일치: ${signature}`);
  const numTables = buf.readUInt16BE(12);
  const totalCompressedSize = buf.readUInt32BE(20);

  let pos = 48;
  const tables = [];
  for (let i = 0; i < numTables; i++) {
    const flags = buf[pos];
    pos += 1;
    const tagIndex = flags & 0x3f;
    let tag;
    if (tagIndex === 0x3f) {
      tag = buf.toString("ascii", pos, pos + 4);
      pos += 4;
    } else {
      tag = KNOWN_TAGS[tagIndex];
    }
    let origLength;
    [origLength, pos] = readUIntBase128(buf, pos);

    const transformVersion = (flags >> 6) & 0x03;
    let transformLength = null;
    // glyf(=10)/loca(=11) 만 transformVersion 0 일 때 변환 적용(길이 별도 필드).
    // name 테이블은 대상이 아니므로 origLength 를 그대로 스트림 길이로 쓴다.
    if ((tag === "glyf" || tag === "loca") && transformVersion === 0) {
      [transformLength, pos] = readUIntBase128(buf, pos);
    }
    tables.push({ tag, origLength, transformLength });
  }

  const compressedStart = pos;
  const compressed = buf.subarray(compressedStart, compressedStart + totalCompressedSize);
  return { tables, compressed };
}

function decompressTables(tables, compressed) {
  const decompressed = brotliDecompressSync(compressed);
  const result = {};
  let offset = 0;
  for (const t of tables) {
    const len = t.transformLength !== null ? t.transformLength : t.origLength;
    result[t.tag] = decompressed.subarray(offset, offset + len);
    offset += len;
  }
  return result;
}

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
    const text = decodeNameString(raw, platformID);
    if (!(nameID in found)) found[nameID] = text;
  }
  return found;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  console.error("사용법: node scripts/verify-woff2-name-table.js <woff2-file> [...]");
  process.exit(1);
}

// §3 이 인용하는 3문자열은 각 name 레코드 전문의 부분 문자열이다(예: 라이선스 설명은
// "...Version 1.1." 뒤에 FAQ 안내가 더 이어진다) — 포함 여부로 대조한다.
const EXPECTED = {
  copyright: "Copyright © 2023 Kil Hyung-jin",
  license: "This Font Software is licensed under the SIL Open Font License, Version 1.1.",
  licenseUrl: "http://scripts.sil.org/OFL",
};

let allOk = true;
let checked = 0;
for (const file of files) {
  const buf = readFileSync(file);
  const { tables, compressed } = parseWoff2TableDirectory(buf);
  const decoded = decompressTables(tables, compressed);
  const nameBuf = decoded["name"];
  if (!nameBuf) {
    console.log(`${file}: name 테이블 없음`);
    allOk = false;
    continue;
  }
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
