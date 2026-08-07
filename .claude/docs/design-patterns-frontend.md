# Frontend CRUD Patterns

신규 CRUD 엔티티 생성 시 따라야 할 코드 패턴 (단일 진실의 원천). 1:1 (단일) / 1:N (parent → children) × Prisma 직접 / Backend 프록시.

## 이 파일의 역할

- **scaffold-frontend 에이전트**: 신규 엔티티 생성 시 1:1 / 1:N 섹션의 코드 블록 그대로 적용 + placeholder 치환. Backend 프록시 시 [Backend → Frontend 매핑](#backend--frontend-매핑-backend-프록시-시) 의 디스커버리 알고리즘으로 Pydantic 추출.
- **평상시 작업 (Claude 메인)**: 도메인 필드 추가/변경 시 Zod schema / 컴포넌트 / Prisma 모델 / Pydantic schema 양쪽 sync. 새 컴포넌트 작성 시 동일 시그니처 패턴 사용.
- **review-frontend Phase C**: 시그니처/네이밍 표준과 다른 구현 발견 시 의심 보고.

UI 컨벤션 / 재사용 훅/컴포넌트 / anti-pattern 룰은 [`frontend/CLAUDE.md`](../../frontend/CLAUDE.md) + [`anti-patterns-frontend.md`](anti-patterns-frontend.md). 여기는 **구조 패턴 (코드 블록)** 만.

## 목차

- [네이밍 컨벤션](#네이밍-컨벤션) — placeholder 치환 규칙
- [생성 파일 목록](#생성-파일-목록) — 1:1 / 1:N × Prisma 직접 / Backend 프록시 별 신규/수정 파일
- [예시 비즈니스 필드](#예시-비즈니스-필드) — UI 타입 다양성 샘플 (도메인에 맞게 교체)
- [Backend → Frontend 매핑 (Backend 프록시 시)](#backend--frontend-매핑-backend-프록시-시) — 디스커버리 알고리즘 + Pydantic → Zod 번역 규칙
- [Schema (Zod-first)](#schema-zod-first) — Zod schema 작성 패턴
- [Prisma 모델 (Prisma 직접 시)](#prisma-모델-prisma-직접-시) — schema.prisma 추가 패턴
- [1:1 단일 엔티티 CRUD](#11-단일-엔티티-crud) — Service / Container / DetailView / DetailForm / Page / API Route
- [1:N (parent → children) CRUD](#1n-parent--children-crud) — 단일 대비 차이 + 자식 패턴
- [패턴 변형 (Variants)](#패턴-변형-variants) — 2-depth 스코프 / 추출 상세 섹션 + editable / 비-CRUD feature / 다중 탭 폼 / 허용 추가 props

## 네이밍 컨벤션

| Placeholder                         | 케이스                                             | 출처 (backend 있을 때)            | 출처 (backend 없을 때) | 예                   |
| ----------------------------------- | -------------------------------------------------- | --------------------------------- | ---------------------- | -------------------- |
| `{prefix}`                          | kebab-case                                         | backend `APIRouter(prefix="...")` (1:N 은 부모 prefix) | `{entity}` (kebab) | `code-group`         |
| `{service}`                         | lowercase                                          | 대상 backend 그룹 폴더 → env `{SERVICE}_SERVICE_URL` | `external` 하위 그룹    | `factor`, `docs`, `market` |
| `{child_route}`                     | kebab-case                                         | backend 자식 nested segment (= backend `{child_route}`) | `{child}` (kebab)      | `order-item`         |
| `{module}`                          | lowercase                                          | backend router 파일 basename      | `{entity}` (camelCase) | `code`               |
| `{Module}`                          | PascalCase                                         | `{module}` 변환                   | `{Entity}`             | `Code`               |
| `{Entity}`, `{Parent}`, `{Child}`   | PascalCase                                         | backend Pydantic class            | 사용자 invocation      | `CodeGroup`, `Code`  |
| `{pk}`, `{parent_pk}`, `{child_pk}` | snake_case                                         | backend path PK segment           | `{entity}` (camelCase) | `group_code`, `code` |
| `{parentPk}`, `{childPk}`           | camelCase                                          | (Props 만) `{parent_pk}` 변환     | 동일                   | `groupCode`          |
| `{path}`                            | `common` (Prisma) 또는 `external` (Backend 프록시) |                                   |                        |                      |

## 생성 파일 목록

**공통 5 파일** (어느 패턴이든)

- `services/{module}/{module}Service.ts`
- `schemas/{module}/{module}.ts` (Zod-first, 두 데이터 흐름 공통)
- `components/features/{Module}/{Module}Container.tsx`
- `components/features/{Module}/{Module}DetailView.tsx`
- `components/features/{Module}/{Module}DetailForm.tsx`

**Page**

- `app/(main)/admin/{service}/{prefix}/page.tsx`

**API Route — 데이터 흐름별**

- Prisma 직접: `app/api/common/{prefix}/route.ts` (+ `[{pk}]/route.ts`)
- Backend 프록시: `app/api/external/{service}/{prefix}/route.ts` (+ `[{pk}]/route.ts`) — proxy `{SERVICE}_SERVICE_URL + "/{prefix}"` (`{prefix}` 는 backend `APIRouter(prefix=...)` 와 byte-identical)

**1:N 추가**

- `components/features/{Module}/{Module}DetailGrid.tsx` (재사용 자식 grid)
- API Route nested: `[{parent_pk}]/{child_route}/route.ts` + `[{child_pk}]/route.ts`

## 예시 비즈니스 필드

스캐폴드가 빈 골조에 채워주는 **예시 placeholder** — UI 타입 다양성을 보여주는 샘플일 뿐, "필수 default" 가 아님. 사용자가 도메인에 맞게 자유롭게 교체/추가/삭제:

| 필드                    | Zod                                 | UI                      |
| ----------------------- | ----------------------------------- | ----------------------- |
| `name`                  | `Field({ max_length: 200 }).str()`  | TextBox                 |
| `category`              | `Field({ max_length: 5 }).str()`    | SelectBox + codeList    |
| `due_date`              | `date()`                            | DateBox                 |
| `amount`                | `PositiveInt()`                     | NumberBox               |
| `description`           | `Field({ max_length: 1000 }).str()` | TextArea                |
| `use_at`                | `enums(["Y", "N"])`                 | SelectBox(Y/N)          |
| `photo_atch_file_id`    | `str()`                             | FileUploader (image)    |
| `document_atch_file_id` | `str()`                             | FileUploader (document) |

**공통 감사 컬럼** (항상 포함, `CommonEntity` 상속): `reg_dt`, `reg_id`, `mod_dt`, `mod_id`. Prisma 직접일 때 Prisma 모델에도 자동 포함. `reg_id`/`mod_id` 는 **email** (`session.user.email`) — backend `get_email()` 규약과 동일 (uuid `session.user.id` 아님).

---

## Backend → Frontend 매핑 (Backend 프록시 시)

backend router/schema 가 이미 존재하면 거기서 실제 정의를 추출.

### 디스커버리 알고리즘

엔티티명 (예: `CodeGroup`) 으로 일치하는 backend router 파일 찾기:

1. `*/app/routers/**/*_router.py` (모든 backend) 에서 `APIRouter(prefix="...")` 의 값 스캔
2. prefix 의 kebab-case 가 entity 의 kebab-case 와 일치하는 파일을 찾음 (예: prefix `/code-group` ↔ entity `CodeGroup`)
3. 그 router 파일의 basename (`code_router` → `code`) 을 **JS module 이름** 으로 사용
4. 같은 basename 의 `code_schema.py` 가 backend Pydantic 정의
5. 그 router 가 속한 backend 폴더 → `{service}` 그룹 폴더명 + `{SERVICE}_SERVICE_URL` env (예: `factor-service` → `factor` / `FACTOR_SERVICE_URL`, `docs-service` → `docs` / `DOCS_SERVICE_URL`). 계층형 prefix (`/market/...`) 는 prefix 첫 segment 가 그룹 (`market`)

### 추출 → 적용 매핑

| 요소                                      | 추출 위치                         | 적용 위치                                                                                                                  |
| ----------------------------------------- | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Route prefix** (`code-group`)           | `APIRouter(prefix="/code-group")` | `app/api/external/{service}/{prefix}/...`, `app/(main)/admin/{service}/{prefix}/page.tsx`, service `BASE_URL`, route `BACKEND_URL` (`{SERVICE}_SERVICE_URL + "/{prefix}"`) |
| **Service 그룹** (`factor`)                | router 가 속한 backend 폴더       | `{service}` 디렉토리 + `{SERVICE}_SERVICE_URL` env                                                                         |
| **JS module 이름** (`code`)               | router 파일 basename              | `services/{module}/`, `schemas/{module}/`, `components/features/{Module}/`                                                 |
| **PK segment** (`{group_code}`, `{code}`) | router path                       | `[{pk}]/route.ts`, `params.{pk}`, schema/service/component PK 필드                                                         |
| **Pydantic class 이름**                   | `{module}_schema.py`              | Zod schema 변수 + TS type 이름 그대로 (`CodeGroupSchema`, `CodeGroup`, `CodeGroupOut`, `CodeSchema`, `Code`, `CodeOut` 등) |
| **Pydantic 필드 + 제약**                  | `{module}_schema.py`              | Zod schema 필드 (아래 번역 규칙)                                                                                           |

> **proxy 가 호출하는 backend prefix 는 그대로(byte-identical) 복제** — case 변환·복수형화·rename·재유도 금지. 보편 불변식: proxy route 의 `{SERVICE}_SERVICE_URL + "<P>"` 의 `<P>` 가 backend `APIRouter(prefix=...)` 와 정확히 같은 문자열. external 디렉토리는 `app/api/external/{service}/{prefix}/` (`{service}` = 대상 backend 그룹 → `{SERVICE}_SERVICE_URL`), admin page 는 `app/(main)/admin/{service}/{prefix}/`, client `BASE_URL` 은 `/api/external/{service}/{prefix}` 로 그 route 경로와 일치. 1:N 자식 nested segment (`{child_route}`) 도 backend 와 동일. backend prefix 가 바뀌면 proxy route + `BASE_URL` + admin page 를 lockstep 으로 수정 ([`anti-patterns-frontend.md`](anti-patterns-frontend.md) 룰 13).

### Pydantic → Zod 번역 규칙

- `str = Field(..., max_length=N)` (required) → `Field({ max_length: N }).str()`
- `str | None = Field(None, max_length=N)` → `Optional(Field({ max_length: N }).str())`
- `int | None` → `Optional(PositiveInt())` 또는 `Optional(Field({...}).numeric())`
- `Decimal | None` (precision/scale) → `Optional(Field({ precision, scale }).numeric())`
- `str = Field(default="Y", max_length=1)` (use_at 류) → `enums(["Y", "N"])`
- PK segment (`{Entity}CreateIn` 의 추가 필드, 예: `group_code: str(max=10)`) → `StrRange(1, 10)`
- `{Entity}Out` 의 join 컬럼 (예: `group_code_nm: str | None`) → TS type 추가 필드로 `?: string` (Pydantic `Optional` 은 TS optional `?` 로 흡수, `| null` 추가 금지)

---

## Schema (Zod-first)

Zod schema 가 단일 source — TypeScript 타입은 `z.infer` 로 파생. 1:N 이면 한 파일에 부모/자식 모두. Backend 프록시면 backend Pydantic 과 필드 동기.

```typescript
// schemas/{entity}/{entity}.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import { str, date, enums, Field, Optional, StrRange, PositiveInt, object } from "@/lib/zod/helpers";

export const {Entity}Schema = object({
  {pk}: StrRange(1, 20),
  name: Optional(Field({ max_length: 200 }).str()),
  category: Optional(Field({ max_length: 5 }).str()),
  due_date: Optional(date()),
  amount: Optional(PositiveInt()),
  description: Optional(Field({ max_length: 1000 }).str()),
  use_at: enums(["Y", "N"]),
  photo_atch_file_id: Optional(str()),
  document_atch_file_id: Optional(str()),
});

export const {Entity}CreateInSchema = {Entity}Schema;
export const {Entity}UpdateInSchema = {Entity}Schema.omit({ {pk}: true });

export type {Entity} = z.infer<typeof {Entity}Schema>;
export type {Entity}Out = {Entity} & CommonEntity;
export interface {Entity}sOut {
  items: {Entity}Out[];
  total_count: number;
}
```

**규칙**

- `@/lib/zod/helpers` 의 `str()`/`date()`/`email()`/`phone()`/`numeric()`/`bool()`/`enums([...])`/`Field({...}).str()`/`StrRange`/`PositiveInt`/`Optional`/`object` 사용 (직접 `z.*` 호출 금지)
- `CommonEntity` 는 `frontend/schemas/common/types.ts` 의 기존 타입 import (재정의 금지)
- Y/N 사용여부 필드 (`use_at` 등) 는 `enums(["Y", "N"])` (semantic — `StrRange(1,1)` 는 임의 1자 통과)
- TS type 의 join 컬럼은 `?: string` (Pydantic Optional 은 TS optional `?` 로 흡수, `| null` 추가 금지)

### 첨부파일이 있을 때

`photo_atch_file_id` / `document_atch_file_id` 같은 첨부파일 필드가 있는 엔티티는 CreateIn/UpdateIn 에 폼-side 파일 필드를 추가. Create 와 Update 는 의미가 달라 비대칭 구조:

```typescript
// schemas/{entity}/{entity}.ts
import { bool, files, requireFiles, ... } from "@/lib/zod/helpers";

// Create — 신규 엔티티라 "기존 파일" 개념 없음. 필드 레벨 required.
export const {Entity}CreateInSchema = {Entity}Schema.extend({
  imageFiles: Optional(files()),
  documentFiles: files(),
});

// Update — 기존 파일 보존 케이스 처리. hasExisting 플래그 기반 conditional required.
export const {Entity}UpdateInSchema = {Entity}Schema.omit({ {pk}: true })
  .extend({
    imageFiles: Optional(files()),
    documentFiles: Optional(files()),
    hasExistingImages: Optional(bool()),
    hasExistingDocuments: Optional(bool()),
  })
  .superRefine(requireFiles("documentFiles"));
```

**규칙**

- 폼-side 파일 필드 (`imageFiles`/`documentFiles`) 는 백엔드에는 보내지 않고 service 에서 destructure 로 분리.
- Create 에서 필수 파일은 `files()` (필드 레벨 `.min(1)`). 다른 필드 에러와 **동시에** 표출됨.
- Update 에서는 `Optional(files())` + `.superRefine(requireFiles("xxxFiles"))` — `hasExistingXxxs` 가 true 면 새 파일 없어도 통과 (기존 파일 보존).
- `hasExistingXxxs` 플래그는 FileUploader 의 `hasExistingFiles()` 결과를 폼이 전달. 이름 컨벤션 (`xxxFiles` ↔ `hasExistingXxxs`) 으로 helper 가 자동 매핑.
- **왜 비대칭?** zod 의 `.superRefine` 은 inner schema 가 통과해야 실행됨. Create 에서 superRefine 으로 file required 를 표현하면 다른 필드 에러 (예: 이름 누락) 시 file 에러가 다음 submit 까지 안 보이는 two-pass UX 발생. 신규 엔티티에 hasExisting 도 의미 없어 필드 레벨이 더 honest.
- 등록만 있는 엔티티: Create 패턴만 쓰고 Update schema 생략.

### 1:N 자식 schema (`{Parent}` schema 파일에 함께)

부모 PK + 자식 PK 둘 다 포함. CreateIn 은 부모 PK 제외 (URL 에서 옴), UpdateIn 은 부모 PK + 자식 PK 둘 다 제외 (PK 변경 안 함):

```typescript
// schemas/{parent}/{parent}.ts (부모 schema 와 같은 파일)
export const {Child}Schema = object({
  {parent_pk}: StrRange(1, 20),
  {child_pk}: StrRange(1, 20),
  // 자식 비즈니스 필드...
  use_at: enums(["Y", "N"]),
});

export const {Child}CreateInSchema = {Child}Schema.omit({ {parent_pk}: true });
export const {Child}UpdateInSchema = {Child}Schema.omit({ {parent_pk}: true, {child_pk}: true });

export type {Child} = z.infer<typeof {Child}Schema>;
export type {Child}Out = {Child} & CommonEntity;
export interface {Child}sOut {
  items: {Child}Out[];
  total_count: number;
}
```

## Prisma 모델 (Prisma 직접 시)

`frontend/prisma/schema.prisma` 에 모델 추가. 공통 감사 컬럼 4개 + `@@map("TN_{Entity}")` 필수.

**1:1 단일**

```prisma
model {Entity} {
  {pk}    String    @id @db.NVarChar(20)            /// PK
  name    String?   @db.NVarChar(200)               /// 이름
  // ... biz fields
  use_at  String    @default("Y") @db.NVarChar(5)   /// 사용여부
  reg_dt  DateTime? @db.DateTime                    /// 생성일시
  reg_id  String?   @db.NVarChar(100)               /// 생성자 ID
  mod_dt  DateTime? @db.DateTime                    /// 수정일시
  mod_id  String?   @db.NVarChar(100)               /// 수정자 ID

  @@map("TN_{Entity}")
}
```

**1:N (composite PK + relation)**

```prisma
model {Parent} {
  {parent_pk}  String    @id @db.NVarChar(20)
  // ... 부모 필드 + 감사 컬럼
  @@map("TN_{Parent}")

  {child}s {Child}[]
}

model {Child} {
  {parent_pk}  String    @db.NVarChar(20)
  {child_pk}   String    @db.NVarChar(20)
  // ... 자식 필드 + 감사 컬럼

  @@id([{parent_pk}, {child_pk}])
  @@map("TN_{Child}")

  {parent}_ref {Parent}  @relation(fields: [{parent_pk}], references: [{parent_pk}])
}
```

---

## 1:1 단일 엔티티 CRUD

### Service (`frontend/services/{entity}/{entity}Service.ts`)

`apiCall` + Zod 검증 + 파일 업로드를 한 service 에 통합. Create/Update 는 destructure-while-validate → `uploadFiles` → API 순. 필수 검증은 schema 의 `superRefine(requireFiles(...))` 가 자동 처리. Delete 는 첨부파일 삭제 후 API.

```typescript
// services/{entity}/{entity}Service.ts
import { CreateOut, UpdateOut, DeleteOut } from "@/schemas/common/types";
import { {Entity}CreateInSchema, {Entity}UpdateInSchema, {Entity}sOut, {Entity}Out } from "@/schemas/{entity}/{entity}";
import { apiCall } from "@/utils/common/api/client";
import { uploadFiles, deleteAllFiles } from "@/services/common/fileService";
import { handleZodValidationError, validateWithZod } from "@/lib/zod/validation";

const BASE_URL = "/api/external/{service}/{prefix}";   // Prisma 직접이면 "/api/common/{prefix}". {prefix} = backend prefix 그대로

// {Entity} 목록 조회
export const select{Entity}List = async (params: any): Promise<{Entity}sOut | null> => {
  const queryParams: Record<string, any> = { ...params };
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<{Entity}sOut>(BASE_URL, {
    method: "GET",
    params: queryParams,
  });
};

// 단일 {Entity} 조회
export const select{Entity} = async (data: any): Promise<{Entity}Out | null> => {
  const { {pk} } = data;

  return apiCall<{Entity}Out>(`${BASE_URL}/${ {pk} }`, {
    method: "GET",
  });
};

// {Entity} 생성
export const create{Entity} = async (data: any): Promise<CreateOut | null> => {
  try {
    const { imageFiles, documentFiles, ...validatedData } = validateWithZod({Entity}CreateInSchema, data);

    if (imageFiles?.length) {
      const photoUploadResult = await uploadFiles(imageFiles, validatedData.photo_atch_file_id);
      if (photoUploadResult?.data.atch_file_id) {
        validatedData.photo_atch_file_id = photoUploadResult.data.atch_file_id;
      }
    }

    if (documentFiles?.length) {
      const documentUploadResult = await uploadFiles(documentFiles, validatedData.document_atch_file_id);
      if (documentUploadResult?.data.atch_file_id) {
        validatedData.document_atch_file_id = documentUploadResult.data.atch_file_id;
      }
    }

    return apiCall<CreateOut>(BASE_URL, {
      method: "POST",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// {Entity} 수정
export const update{Entity} = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { {pk}, ...baseData } = data;
    const { imageFiles, documentFiles, hasExistingImages, hasExistingDocuments, ...validatedData } =
      validateWithZod({Entity}UpdateInSchema, baseData);

    if (imageFiles?.length) {
      const photoUploadResult = await uploadFiles(imageFiles, validatedData.photo_atch_file_id);
      if (photoUploadResult?.data.atch_file_id) {
        validatedData.photo_atch_file_id = photoUploadResult.data.atch_file_id;
      }
    }

    if (documentFiles?.length) {
      const documentUploadResult = await uploadFiles(documentFiles, validatedData.document_atch_file_id);
      if (documentUploadResult?.data.atch_file_id) {
        validatedData.document_atch_file_id = documentUploadResult.data.atch_file_id;
      }
    }

    return apiCall<UpdateOut>(`${BASE_URL}/${ {pk} }`, {
      method: "PUT",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

// {Entity} 삭제 (첨부파일도 함께 삭제)
export const delete{Entity} = async (data: any): Promise<DeleteOut | null> => {
  const { photo_atch_file_id, document_atch_file_id, {pk} } = data;

  try {
    await deleteAllFiles(photo_atch_file_id);
  } catch {
    // 파일 삭제 실패 시 무시 ({Entity} 삭제는 계속 진행)
  }

  try {
    await deleteAllFiles(document_atch_file_id);
  } catch {
    // 파일 삭제 실패 시 무시 ({Entity} 삭제는 계속 진행)
  }

  return apiCall<DeleteOut>(`${BASE_URL}/${ {pk} }`, {
    method: "DELETE",
  });
};
```

### Container (`{Entity}Container.tsx`)

SplitPane 좌(MasterGrid)/우(DetailPanel). `useCodeStore` 로 codeList 준비 후 `viewProps`/`formProps` 로 주입.

```tsx
// components/features/{Entity}/{Entity}Container.tsx
"use client";

import { useRef } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";
import { useCodeStore } from "@/stores/shared/codeStore";
import {
  select{Entity}List, select{Entity}, create{Entity}, update{Entity}, delete{Entity},
} from "@/services/{entity}/{entity}Service";
import {Entity}DetailView from "./{Entity}DetailView";
import {Entity}DetailForm from "./{Entity}DetailForm";

export default function {Entity}Container() {
  const gridRef = useRef<any>(null);

  const { getCode } = useCodeStore();
  const codeList = {
    sample: getCode("0000"),
  };

  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "{pk}", caption: "PK", width: 100 },
    { dataField: "name", caption: "이름", width: 150 },
    { dataField: "category", caption: "분류", width: 100,
      lookup: { dataSource: codeList.sample, displayExpr: "code_nm", valueExpr: "code" } },
    { dataField: "due_date", caption: "기한", width: 120, dataType: "date" },
    { dataField: "amount", caption: "금액", width: 120, dataType: "number" },
    { dataField: "description", caption: "설명", minWidth: 200 },
    { dataField: "use_at", caption: "사용여부", width: 100,
      lookup: { dataSource: [{ value: "Y", text: "사용" }, { value: "N", text: "미사용" }],
                displayExpr: "text", valueExpr: "value" } },
    { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
    { dataField: "reg_id", caption: "생성자ID", width: 100 },
    { dataField: "mod_dt", caption: "수정일시", width: 160, dataType: "datetime" },
    { dataField: "mod_id", caption: "수정자ID", width: 100 },
  ];

  const {
    dataSource, selectedData, isSelectLoading,
    handleSelect, handleCreate, handleRefresh, handleCompleteWithRefresh,
  } = useMasterGridData({ fetchGrid: select{Entity}List, fetchData: select{Entity} });

  const { handleExcelDownload } = useExcelExport({ gridRef, columns: GRID_COLUMNS, fileName: "download" });

  const buttons = useMasterGridActions({
    onCreate: handleCreate, onRefresh: handleRefresh, onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  const apiService = { select: select{Entity}, create: create{Entity}, update: update{Entity}, delete: delete{Entity} };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="{Entity} 목록" buttons={buttons}>
              <MasterGrid ref={gridRef} dataSource={dataSource} columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect} selectedData={selectedData} />
            </MasterPanel>,
            <DetailPanel key="detail" title="{Entity} 정보" data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={ {Entity}DetailView }
              FormComponent={ {Entity}DetailForm }
              viewProps={{ codeList }}
              formProps={{ codeList }}
              defaultFormData={{ use_at: "Y" }}
              onComplete={handleCompleteWithRefresh}
              apiService={apiService} />,
          ]}
        </SplitPane>
      </div>
    </div>
  );
}
```

`initialSizes`/`minSizes` 는 퍼센트 계약이다(`SplitPane.tsx` 주석 — 단위 없는 문자열로 내부 변환). O8-1 로 이주한 10개 Container 어느 것도 `minSizes` 를 지정하지 않는다(원본 DevExtreme `Item` 도 `minSize` 미지정) — 최소 크기 제약이 필요하면 `WatchlistContainer.tsx`(`minSizes={[20, 20]}`, O5)를 참고한다.

### DetailView (`{Entity}DetailView.tsx`)

`TableGroup/TableRow/TableCell` 로 read-only 표시. `data.x` 값은 단순 텍스트, 코드 변환은 TableCell 의 `items` prop 사용.

```tsx
// components/features/{Entity}/{Entity}DetailView.tsx
"use client";

import { Button, FileListDisplay } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { {Entity}Out } from "@/schemas/{entity}/{entity}";

interface Props {
  data: {Entity}Out;
  codeList?: any;
  onEdit: () => void;
  onDelete?: () => void;
}

export default function {Entity}DetailView({ data, codeList, onEdit, onDelete }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="수정" onClick={onEdit} />
          {onDelete && <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="기본 정보">
          <TableRow>
            <TableCell label="PK">{data.{pk}}</TableCell>
            <TableCell label="이름">{data.name}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="분류" items={codeList?.sample}>{data.category}</TableCell>
            <TableCell label="기한">{data.due_date}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="금액">{data.amount}</TableCell>
            <TableCell label="사용여부">{data.use_at}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="설명" colSpan={3}>{data.description}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="사진" colSpan={3}>
              <FileListDisplay atchFileId={data.photo_atch_file_id} />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="문서" colSpan={3}>
              <FileListDisplay atchFileId={data.document_atch_file_id} />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="생성일시">{data.reg_dt}</TableCell>
            <TableCell label="생성자">{data.reg_id}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="수정일시">{data.mod_dt}</TableCell>
            <TableCell label="수정자">{data.mod_id}</TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
```

**규칙**

- Props 시그니처 고정: `data: {Entity}Out`, `onEdit`, `onDelete?`, `codeList?: any` (DetailForm 과 동일하게 narrow 타입 금지)
- 코드 → 라벨 변환은 `<TableCell items={codeList?.sample}>{data.x}</TableCell>` — 자체 `find()` 호출 금지
- `<FileListDisplay atchFileId={...} />` 그대로 — `data.x ? ... : <span>-</span>` conditional 추가 금지

### DetailForm (`{Entity}DetailForm.tsx`)

`useFormState<{Entity}>` 로 폼 상태 + `handleSubmit` 으로 제출. UI 타입별 placeholder 1개씩 + FileUploader 포함.

```tsx
// components/features/{Entity}/{Entity}DetailForm.tsx
"use client";

import { useRef } from "react";
import { useFormState } from "@/hooks/shared/useFormState";
import {
  Button, TextBox, SelectBox, DateBox, NumberBox, TextArea,
  FileUploader, FileUploaderRef,
} from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { {Entity} } from "@/schemas/{entity}/{entity}";

interface Props {
  initialData: Partial<{Entity}>;
  isNew: boolean;
  codeList?: any;
  onSubmit: (
    data: {Entity} & {
      imageFiles?: File[];
      documentFiles?: File[];
      hasExistingImages?: boolean;
      hasExistingDocuments?: boolean;
    },
  ) => Promise<boolean>;
  onCancel?: () => void;
}

export default function {Entity}DetailForm({ initialData, isNew, codeList, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<{Entity}>(initialData);

  const imageUploaderRef = useRef<FileUploaderRef>(null);
  const documentUploaderRef = useRef<FileUploaderRef>(null);

  const handleFormSubmit = async (data: {Entity}) => {
    return await onSubmit({
      ...data,
      imageFiles: imageUploaderRef.current?.selectFiles() || [],
      hasExistingImages: imageUploaderRef.current?.hasExistingFiles() || false,
      documentFiles: documentUploaderRef.current?.selectFiles() || [],
      hasExistingDocuments: documentUploaderRef.current?.hasExistingFiles() || false,
    });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="저장" onClick={() => handleSubmit(handleFormSubmit)} />
          {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="기본 정보">
          <TableRow>
            <TableCell label="PK" required>
              <TextBox fieldName="{pk}" value={formData.{pk}} readOnly={!isNew}
                onValueChanged={handleFieldChange} getFieldProps={getFieldProps} />
            </TableCell>
            <TableCell label="이름">
              <TextBox fieldName="name" value={formData.name}
                onValueChanged={handleFieldChange} getFieldProps={getFieldProps} />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="분류">
              <SelectBox fieldName="category" value={formData.category} items={codeList?.sample}
                displayExpr="code_nm" valueExpr="code"
                onValueChanged={handleFieldChange} getFieldProps={getFieldProps} />
            </TableCell>
            <TableCell label="기한">
              <DateBox fieldName="due_date" value={formData.due_date}
                onValueChanged={handleFieldChange} getFieldProps={getFieldProps} />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="금액">
              <NumberBox fieldName="amount" value={formData.amount}
                onValueChanged={handleFieldChange} getFieldProps={getFieldProps} />
            </TableCell>
            <TableCell label="사용여부" required>
              <SelectBox fieldName="use_at" value={formData.use_at}
                items={[{ value: "Y", text: "사용" }, { value: "N", text: "미사용" }]}
                displayExpr="text" valueExpr="value"
                onValueChanged={handleFieldChange} getFieldProps={getFieldProps} />
            </TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="설명" colSpan={3}>
              <TextArea fieldName="description" value={formData.description}
                onValueChanged={handleFieldChange} getFieldProps={getFieldProps} />
            </TableCell>
          </TableRow>

          {/* 사진 파일 업로더 */}
          <TableRow>
            <TableCell label="사진" colSpan={3}>
              <FileUploader
                ref={imageUploaderRef}
                atchFileId={initialData.photo_atch_file_id}
                fileType="image"
                multiple
                maxFileCount={5}
                fieldName="imageFiles"
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>

          {/* 문서 파일 업로더 */}
          <TableRow>
            <TableCell label="문서" colSpan={3} required>
              <FileUploader
                ref={documentUploaderRef}
                atchFileId={initialData.document_atch_file_id}
                fileType="document"
                multiple
                maxFileCount={3}
                fieldName="documentFiles"
                getFieldProps={getFieldProps}
              />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
```

**규칙**

- Props 시그니처 고정: `isNew`, `initialData: Partial<{Entity}>`, `onSubmit`, `onCancel?`, `codeList?: any`. `{ sample: CodeItem[] }` 같이 narrow 타입으로 좁히거나 자체 `interface CodeItem` 추가 금지
- DevExtreme 직접 import 금지 — `@/components/shared/ui` 래퍼만 사용
- `value={formData.x ?? ""}` 같은 nullish fallback, `maxLength`/`height` 등 wrapper 부가 prop 추가 금지 (wrapper 와 Zod schema 가 처리)

### Page (`page.tsx`)

```tsx
// app/(main)/admin/{service}/{prefix}/page.tsx
import {Entity}Container from "@/components/features/{Entity}/{Entity}Container";

export default function Page() {
  return <{Entity}Container />;
}
```

### API Route — Prisma 직접 (`app/api/common/{prefix}/route.ts`)

```typescript
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { createSuccessResponse } from "@/utils/common/api/responses";
import { prisma } from "@/lib/prisma";
import { convertFilterToPrismaWhere, convertSortToPrismaOrderBy } from "@/lib/grid/filters";

export const GET = withAuth(async (request, session) => {
  const { searchParams } = new URL(request.url);
  const skip = parseInt(searchParams.get("skip") || "0");
  const take = searchParams.get("take") ? parseInt(searchParams.get("take")!) : undefined;
  const filter = searchParams.get("filter");
  const sort = searchParams.get("sort");

  const where = filter ? convertFilterToPrismaWhere(JSON.parse(filter)) : {};
  const orderBy = sort ? convertSortToPrismaOrderBy(JSON.parse(sort)) : {};

  const [items, total] = await Promise.all([
    prisma.{entity}.findMany({ where, orderBy, skip, take }),
    prisma.{entity}.count({ where }),
  ]);
  return createSuccessResponse({ items, total_count: total });
});

export const POST = withAuth(async (request, session) => {
  const body = await request.json();
  const created = await prisma.{entity}.create({
    data: { ...body, reg_id: session.user.email, reg_dt: new Date(),
            mod_id: session.user.email, mod_dt: new Date() },
  });
  return createSuccessResponse({ data: created });
});
// `[{pk}]/route.ts` — GET/PUT/DELETE 동일 withAuth + prisma 패턴
```

### API Route — Backend 프록시 (`app/api/external/{service}/{prefix}/route.ts`)

method 별로 handler 분리 → `withAuth` HOC 래핑. handler 안에서 `proxyApiRequest` 로 backend 호출.

```typescript
// app/api/external/{service}/{prefix}/route.ts
import { env } from "@/env";
import { withAuth } from "@/lib/auth/withAuth";
import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/utils/common/api/server";
import {
  createSuccessResponse,
  createErrorResponse,
} from "@/utils/common/api/responses";

const BACKEND_URL = env.{SERVICE}_SERVICE_URL + "/{prefix}";   // "/{prefix}" 는 backend APIRouter(prefix) 와 byte-identical

/**
 * [GET] /api/external/{service}/{prefix}
 */
const getHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "GET";
  try {
    const { searchParams } = new URL(req.url);
    const queryParams = Object.fromEntries(searchParams.entries());
    const result = await proxyApiRequest(`${BACKEND_URL}`, {
      method: operation,
      params: queryParams,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });
    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

/**
 * [POST] /api/external/{service}/{prefix}
 */
const postHandler = async (req: NextRequest, session: any, params?: any) => {
  const operation = "POST";
  try {
    const body = await req.json();
    const result = await proxyApiRequest(`${BACKEND_URL}`, {
      method: operation,
      data: body,
      headers: { Authorization: `Bearer ${session.accessToken}` },
    });
    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
export const POST = withAuth(postHandler);
```

`[{pk}]/route.ts` 는 동일 패턴 — `getHandler`/`putHandler`/`deleteHandler` 분리 후 `withAuth` 래핑. URL 에 `${params.{pk}}` 추가.

**규칙**

- `// HOC로 래핑하여 인증 처리` 같은 자명한 주석 추가 금지

---

## 1:N (parent → children) CRUD

부모-자식 1:N. 부모는 MasterGrid, 우측 DetailPanel 의 ViewComponent = **`{Parent}DetailView`** (단일 패턴과 동일). DetailView 안에 부모 정보 + 자식 grid (`{Parent}DetailGrid`) 임베드.

### 1:1 대비 추가/변경

- Service: 자식 함수 추가 (`select{Child}List/Create/Update/Delete`)
- 새 컴포넌트: `{Parent}DetailGrid.tsx` (재사용 자식 grid, Props camelCase)
- `{Parent}DetailView`: 부모 정보 + `<{Parent}DetailGrid />` 임베드
- `{Parent}DetailForm`: `TabPanel` 로 부모 편집(basic) + 자식 관리(children) 분리
- Container: `ViewComponent={ {Parent}DetailView }` (1:1과 동일), `formProps={{}}`
- API Route: `[{parent_pk}]/{child_route}/route.ts` + `[{child_pk}]/route.ts` nested

### Service — 자식 함수

```typescript
/**
 * {Child} 목록 조회 (특정 {parent_pk} 의 자식들)
 */
export const select{Child}List = async (params: any): Promise<{Child}sOut | null> => {
  const { {parent_pk}, ...queryParams } = params;
  if (queryParams.filter) queryParams.filter = JSON.stringify(queryParams.filter);
  if (queryParams.sort) queryParams.sort = JSON.stringify(queryParams.sort);

  return apiCall<{Child}sOut>(`${BASE_URL}/${ {parent_pk} }/{child_route}`, {
    method: "GET",
    params: queryParams,
  });
};

/**
 * {Child} 단일 조회
 */
export const select{Child} = async (data: any): Promise<{Child}Out | null> => {
  const { {parent_pk}, {child_pk} } = data;
  return apiCall<{Child}Out>(`${BASE_URL}/${ {parent_pk} }/{child_route}/${ {child_pk} }`, { method: "GET" });
};

/**
 * {Child} 생성
 */
export const create{Child} = async (data: any): Promise<CreateOut | null> => {
  try {
    const { {parent_pk}, ...baseData } = data;
    const validatedData = validateWithZod({Child}CreateInSchema, baseData);

    return apiCall<CreateOut>(`${BASE_URL}/${ {parent_pk} }/{child_route}`, {
      method: "POST",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

/**
 * {Child} 수정
 */
export const update{Child} = async (data: any): Promise<UpdateOut | null> => {
  try {
    const { {parent_pk}, {child_pk}, ...baseData } = data;
    const validatedData = validateWithZod({Child}UpdateInSchema, baseData);

    return apiCall<UpdateOut>(`${BASE_URL}/${ {parent_pk} }/{child_route}/${ {child_pk} }`, {
      method: "PUT",
      data: validatedData,
    });
  } catch (error) {
    handleZodValidationError(error);
  }
};

/**
 * {Child} 삭제
 */
export const delete{Child} = async (data: any): Promise<DeleteOut | null> => {
  const { {parent_pk}, {child_pk} } = data;
  return apiCall<DeleteOut>(`${BASE_URL}/${ {parent_pk} }/{child_route}/${ {child_pk} }`, { method: "DELETE" });
};
```

### {Parent}DetailGrid (`{Parent}DetailGrid.tsx`)

자식 grid 재사용 컴포넌트 — DetailView 안에 임베드되거나 DetailForm 의 tab 안에서 사용. **Props 는 camelCase** (`{parentPk}`), 서비스 호출 시 snake_case (`{parent_pk}`) 로 변환.

```tsx
// components/features/{Parent}/{Parent}DetailGrid.tsx
"use client";

import React from "react";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import type { LegacyGridColumn } from "@/types/grid";
import { TextBox, SelectBox, NumberBox, TextArea } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { select{Child}List, create{Child}, update{Child}, delete{Child} } from "@/services/{parent}/{parent}Service";
import { {Child}, {Child}Out } from "@/schemas/{parent}/{parent}";

interface Props {
  {parentPk}: string;
  onSelectionChanged?: ({child}: {Child}Out | null) => void;
  height?: string;
  editable?: boolean;
  codeList?: any;
}

const {Parent}DetailGrid: React.FC<Props> = ({ {parentPk}, onSelectionChanged, height = "100%", editable = false }) => {
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "{child_pk}", caption: "PK", width: 100 },
    // 자식 필드 컬럼...
  ];

  return (
    <DetailGridPanel
      fetchGrid={async (params: any) => select{Child}List({ ...params, {parent_pk}: {parentPk} })}
      columns={GRID_COLUMNS}
      height={height}
      apiService={{
        create: async (data: {Child}) => { await create{Child}({ ...data, {parent_pk}: {parentPk} }); },
        update: async (data: {Child}) => { await update{Child}(data); },
        delete: async (data: {Child}) => { await delete{Child}(data); },
      }}
      FormComponent={FormComponent}
      defaultFormData={{ use_at: "Y" }}
      editable={editable}
      onSelectionChanged={onSelectionChanged}
    />
  );
};

const FormComponent: React.FC<{
  formData: Partial<{Child}>;
  modalMode: "create" | "edit";
  onFieldChange: (field: string, value: any) => void;
  getFieldProps: (field: string) => any;
}> = ({ formData, modalMode, onFieldChange, getFieldProps }) => {
  return (
    <TableGroup title="자식 정보">
      <TableRow>
        <TableCell label="자식 PK" required>
          <TextBox fieldName="{child_pk}" value={formData.{child_pk}} readOnly={modalMode === "edit"}
            onValueChanged={onFieldChange} getFieldProps={getFieldProps} />
        </TableCell>
        {/* 자식 필드... */}
      </TableRow>
    </TableGroup>
  );
};

export default React.memo({Parent}DetailGrid);
```

**규칙**

- Props 는 camelCase (`{parentPk}`), DB/service 는 snake_case (`{parent_pk}`) — 컴포넌트 내부에서 변환
- update/delete service 호출 시 `data` 만 전달 (Code schema 가 이미 두 PK 다 가짐 — Zod schema 의 omit() 패턴 활용)
- `defaultFormData` 에 도메인-relevant default 추가 가능 (`sort_ordr: 1` 등)

### {Parent}DetailView (`{Parent}DetailView.tsx`)

부모 read-only 정보 + 자식 grid 임베드. `editable={false}` 로 자식은 조회만.

```tsx
// components/features/{Parent}/{Parent}DetailView.tsx
"use client";

import { Button } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import {Parent}DetailGrid from "./{Parent}DetailGrid";
import { {Parent}Out } from "@/schemas/{parent}/{parent}";

interface Props {
  data: {Parent}Out;
  onEdit: () => void;
  onDelete?: () => void;
}

export default function {Parent}DetailView({ data, onEdit, onDelete }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="수정" onClick={onEdit} />
          {onDelete && <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="기본 정보">
          {/* 부모 read-only 필드 row 들 */}
          <TableRow>
            <TableCell label="생성일시">{data.reg_dt}</TableCell>
            <TableCell label="생성자">{data.reg_id}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="수정일시">{data.mod_dt}</TableCell>
            <TableCell label="수정자">{data.mod_id}</TableCell>
          </TableRow>
        </TableGroup>

        <TableGroup title="자식 목록">
          <TableRow>
            <TableCell colSpan={4}>
              <{Parent}DetailGrid {parentPk}={data.{parent_pk}} editable={false} height="500px" />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
```

### {Parent}DetailForm (`{Parent}DetailForm.tsx`)

`TabPanel` 로 부모 편집 + 자식 관리 분리. 신규 (`isNew=true`) 일 때 자식 탭 disabled (부모 PK 없음).

```tsx
// components/features/{Parent}/{Parent}DetailForm.tsx
"use client";

import { useFormState } from "@/hooks/shared/useFormState";
import { Button, TextBox, SelectBox, TextArea, TabPanel, TabContent } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { {Parent} } from "@/schemas/{parent}/{parent}";
import {Parent}DetailGrid from "./{Parent}DetailGrid";

interface Props {
  isNew: boolean;
  initialData: Partial<{Parent}>;
  onSubmit: (data: {Parent}) => Promise<boolean>;
  onCancel?: () => void;
}

export default function {Parent}DetailForm({ initialData, isNew, onSubmit, onCancel }: Props) {
  const { formData, handleFieldChange, getFieldProps, handleSubmit } = useFormState<{Parent}>(initialData);

  const canAccessSubTabs = !isNew && !!formData.{parent_pk}?.trim();
  const tabs = [
    { id: "basic", text: "{Parent}", icon: "edit" },
    { id: "children", text: "{Child}", icon: "hierarchy", disabled: !canAccessSubTabs },
  ];

  return (
    <div className="h-full">
      <TabPanel items={tabs} defaultTab="basic">
        <TabContent tabId="basic">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                <Button text="저장" onClick={() => handleSubmit(onSubmit)} />
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              <TableGroup title="기본 정보">
                {/* 부모 입력 row 들 */}
              </TableGroup>
            </div>
          </div>
        </TabContent>

        <TabContent tabId="children">
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 mb-2">
              <div className="flex gap-2 justify-end">
                {onCancel && !isNew && <Button text="취소" onClick={onCancel} stylingMode="outlined" type="normal" />}
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              <TableGroup title="자식 목록">
                <TableRow>
                  <TableCell colSpan={4}>
                    <{Parent}DetailGrid {parentPk}={formData.{parent_pk}!} editable={true} height="500px" />
                  </TableCell>
                </TableRow>
              </TableGroup>
            </div>
          </div>
        </TabContent>
      </TabPanel>
    </div>
  );
}
```

### Container

단일 패턴과 거의 동일. `ViewComponent={ {Parent}DetailView }` 그대로 (DetailView 가 자식 grid 임베드). `formProps={}` 로 충분 (1:N 자식 grid 가 자체 service 호출).

```tsx
<DetailPanel
  title="{Parent} 정보"
  data={selectedData}
  initialMode={selectedData ? "view" : "create"}
  isSelectLoading={isSelectLoading}
  ViewComponent={ {Parent}DetailView }
  FormComponent={ {Parent}DetailForm }
  formProps={{}}
  defaultFormData={{ use_at: "Y" }}
  onComplete={handleCompleteWithRefresh}
  apiService={apiService}
/>
```

### API Route

**Prisma 직접**: `app/api/common/{prefix}/[{parent_pk}]/{child_route}/route.ts` + `[{child_pk}]/route.ts` 추가. Prisma `where: { {parent_pk}: params.{parent_pk} }` 로 자식 필터.

**Backend 프록시**: `app/api/external/{service}/{prefix}/[{parent_pk}]/{child_route}/route.ts` + `[{child_pk}]/route.ts` 추가. 1:1 과 동일한 형식 (`getHandler`/`postHandler` 분리 + try/catch + `createSuccessResponse`/`createErrorResponse` + `withAuth` 래핑) 으로 작성. URL 만 nested path 로:

```typescript
const BACKEND_URL = env.{SERVICE}_SERVICE_URL + "/{prefix}";   // 부모 prefix 그대로 (byte-identical)

const getHandler = async (req: NextRequest, session: any, { params }: any) => {
  const operation = "GET";
  try {
    const { searchParams } = new URL(req.url);
    const queryParams = Object.fromEntries(searchParams.entries());
    const result = await proxyApiRequest(
      `${BACKEND_URL}/${params.{parent_pk}}/{child_route}`,
      {
        method: operation,
        params: queryParams,
        headers: { Authorization: `Bearer ${session.accessToken}` },
      },
    );
    return createSuccessResponse(result, operation);
  } catch (error) {
    return createErrorResponse(error, operation);
  }
};

export const GET = withAuth(getHandler);
// POST/[{child_pk}] GET·PUT·DELETE 도 동일 패턴, URL 끝에 `/${params.{child_pk}}` 추가
```

---

## 패턴 변형 (Variants)

표준 1:1 / 1:N CRUD 에서 벗어나는 **합법적** 구조들. review-frontend 가 "표준 아님 → 위반/스킵" 으로 오판하지 않도록 여기에 명시한다. 각 변형은 [`anti-patterns-frontend.md`](anti-patterns-frontend.md) 룰의 예외 또는 정상 패턴으로 인정됨 (특히 룰 5 Container 구조 예외와 짝). Docs 도메인 (Project / Document / Chat) 이 대표 사례.

### 2-depth 스코프 선택 (부모 스코프 → 자식 CRUD)

자식 엔티티가 항상 부모 스코프에 종속될 때 (예: 문서는 항상 특정 프로젝트 소속), Container 는 `SplitPane` **위**에 `ConditionBar` / `{Scope}ControlBar` 를 두어 부모를 먼저 고른 뒤 자식을 CRUD. 부모는 `MasterGrid` 가 아니라 드롭다운으로 선택한다.

```tsx
// components/features/{Domain}/{Child}Container.tsx (발췌, 예: DocumentContainer)
return (
  <div className="h-full flex flex-col">
    {/* 부모 스코프 선택 — SplitPane 밖, 페이지 레벨 */}
    <{Scope}ControlBar value={selectedScopeId} onChange={handleScopeChange} />

    <div className="flex-1 min-h-0 border-t">
      <SplitPane orientation="horizontal" initialSizes={[50, 50]}>
        {[
          <MasterPanel key="master" title="{Child} 목록" buttons={buttons}>
            {selectedScopeId ? (
              <MasterGrid ref={gridRef} dataSource={dataSource} columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect} selectedData={selectedData} />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">{Scope}를 선택해주세요</div>
            )}
          </MasterPanel>,
          selectedScopeId ? (
            <DetailPanel key={`detail-${selectedScopeId}-${createKey}`} ...
              formProps={{ {scope}Id: selectedScopeId, onRefresh: handleRefresh, codeList }} ... />
          ) : (
            <div key="detail-placeholder" className="flex items-center justify-center h-full text-gray-500">{Scope}를 선택해주세요</div>
          ),
        ]}
      </SplitPane>
    </div>
  </div>
);
```

**규칙**

- `SplitPane` + `MasterPanel` + `DetailPanel` 은 **그대로 유지** (anti-patterns 룰 5 위반 아님 — 예외 명시됨).
- 부모 선택 전에는 grid/DetailPanel 자리에 placeholder. `DetailPanel key` 에 `selectedScopeId` 포함 → 스코프 전환 시 detail remount.
- 부모 스코프 id 는 `formProps` 로 Form 에 주입 (`projectId` 등) — DetailForm 의 허용된 추가 prop (아래 [허용 추가 props](#detailview--detailform-의-허용된-추가-props)).
- `ConditionBar` 는 `components/shared/Layout/` 의 공용 컴포넌트, `{Scope}ControlBar` (예: `ProjectControlBar`) 는 fetch / 표시 expr 만 고정한 thin preset:

```tsx
// components/features/{Domain}/{Scope}ControlBar.tsx
import { ConditionBar } from "@/components/shared/Layout";
import { select{Scope}List } from "@/services/{domain}/{scope}Service";

export function {Scope}ControlBar({ value, onChange, onItemsLoaded }: Props) {
  return (
    <ConditionBar
      label="{Scope}:"
      value={value}
      onChange={onChange}
      fetchItems={() => select{Scope}List({ take: 1000 })}
      displayExpr="{scope}_nm"
      valueExpr="{scope}_id"
      placeholder="{Scope}를 선택하세요"
      onItemsLoaded={onItemsLoaded}
    />
  );
}
```

### 추출 상세 섹션 + `editable` prop

DetailView (읽기) 와 DetailForm (편집) 이 **같은 하위 영역** (멤버 목록 / 청크 / 버전 등) 을 보여줄 때, 그 영역을 별도 컴포넌트로 추출하고 `editable` prop 으로 모드를 전환한다. **View 는 `editable={false}` (추가/편집/삭제 버튼 숨김), Form 은 생략 (기본 `true`)**. 같은 컴포넌트가 View 와 Form 양쪽에서 import 되는지로 "추출 섹션" 을 식별.

**(a) DetailGridPanel 기반** — 1:N 자식 grid 의 확장 골격 (`{Parent}DetailGrid` 와 동일). 예: `ProjectMemberGrid`, `ProjectDocumentGrid`.

```tsx
interface Props {
  {scope}Id: number;        // camelCase (룰 3)
  editable?: boolean;       // 기본 true; View 에서만 false
  height?: string;
  // 도메인 추가 (isSysAdmin 등)
}

<DetailGridPanel
  fetchGrid={async (params) => select{Child}List({ ...params, {scope}_id: {scope}Id })}
  columns={GRID_COLUMNS} keyField="{child_pk}" height={height} editable={editable}
  apiService={editable ? { create, delete } : undefined}   // 읽기 전용이면 미전달
  FormComponent={FormComponent} />
```

**(b) 커스텀 훅 기반 섹션** — grid 가 아닌 복합 UI (자체 도메인 훅 + 생성/충돌/복원 등). 예: `DocumentChunkSection` (`useDocumentChunks`), `DocumentVersionSection` (`useDocumentVersion`), `ProjectDocumentUploadPanel`.

```tsx
interface Props {
  data: {Entity}Out;
  editable?: boolean;       // false 면 액션 버튼/편집 UI 숨기고 목록만
  onRefresh?: () => void;
  // 편집 전용 입력 — 편집 모드에서만 의미, View 는 미전달
  content?: string;
  onReloadContent?: () => Promise<void>;
}
```

**규칙**

- Props 는 **camelCase** (룰 3) — `{scope}Id` / `isSysAdmin` / `editable` / `onRefresh`. DB key snake_case 는 service 호출 LEFT 에서만.
- `editable` 기본값 `true`, View 에서만 명시적 `false`. `editable` 에 따라 `apiService` / 액션 버튼 조건부 노출.
- DevExtreme 단일 값 바인딩 설정 컨트롤 (`chunkStrategy` 등) 은 `useFormState` 객체 폼이 아니므로 직접 import OK (룰 4 예외 5).

### 비-CRUD 도메인 feature (대화형 / 워크스페이스)

엔티티 CRUD 가 아닌 화면 (채팅 등) 은 View/Form 쌍이 없다. `SplitPane` + 도메인 전용 패널로 구성하며 `MasterPanel` / `DetailPanel` / `useFormState` / `apiService` 가 없어도 anti-patterns 룰 5 위반 아님 (예외 명시됨).

```tsx
// components/features/{Domain}/{Feature}Container.tsx (예: ResearchChatContainer)
return (
  <div className="h-full flex flex-col">
    <{Scope}ControlBar value={selectedScopeId} onChange={setSelectedScopeId} onItemsLoaded={setScopes} />
    <div className="flex-1 min-h-0 border-t">
      <SplitPane orientation="horizontal" initialSizes={[25, 75]}>
        {[
          // 좌: 세션 사이드바
          <{Feature}SessionPanel key="sessions" sessionsHook={sessionsHook} ... />,
          // 우: 대화
          <{Feature}ConversationPanel key="conversation" messagesHook={messagesHook} ... />,
        ]}
      </SplitPane>
    </div>
    {/* 공유/설정 모달은 공용 FormModal 오버레이 */}
  </div>
);
```

`minSizes` 픽셀 지정은 안 된다 — `SplitPane` 의 `initialSizes`/`minSizes` 는 퍼센트 전용 계약이라 DevExtreme `Item` 의 `minSize="200px"` 같은 픽셀 지정은 옮길 수 없다(계약에 없음). 실제 이주분(`ResearchChatContainer.tsx`·`DevActivityContainer.tsx`, O8-1)도 `minSizes` 없이 `initialSizes` 만 쓴다 — 최소 크기가 필요하면 퍼센트로 `minSizes={[20, 20]}` 같이 지정(`WatchlistContainer.tsx`, O5 참고).

**규칙**

- 상태/로직은 도메인 훅 (`useChatSessions` / `useChatMessages` / `useChatMetadata` 등) 에 위임 — Container 는 조립만.
- 패널은 `components/features/{Domain}/` 에 위치 (룰 2). Props camelCase + 훅 객체 전달 (`sessionsHook` 등).
- 비-CRUD 라도 **데이터/인증 룰은 동일 적용**: HTTP 는 `apiCall` / `proxyApiRequest` (룰 6), 공통코드는 codeStore (룰 9). 모달은 공용 `FormModal` (자체 모달 구현 금지).

### 다중 탭 DetailForm

DetailForm 이 `TabPanel` 로 여러 영역을 나눌 때 (1:N 의 basic/children 2탭에서 확장). isNew 처리 두 방식:

- **탭 disable 방식**: 신규 시 부모 PK 없는 하위 탭을 `disabled`. 예: `ProjectDetailForm` — `기본정보` / `시스템 프롬프트`\* / `문서`\* / `멤버`\* (`*` = `disabled: !isExisting`).
- **early return 방식**: 신규 시 아예 다른 폼으로 분기. 예: `DocumentDetailForm` — `isNew` 면 `<DocumentUploadForm/>`, 편집이면 `기본정보` / `내용` / `청킹` / `이미지` / `버전` 탭.

**규칙**

- early return 분기는 **모든 훅 호출 이후** (Rules of Hooks). 생성 전용 effect 는 `if (isNew) return` 으로 가드.
- 자체 API 로 즉시 처리되는 탭 (문서 업로드 / 멤버 추가 등 폼 제출과 무관) 은 `저장` 버튼 없이 `취소` 만 둘 수 있음.

### DetailView / DetailForm 의 허용된 추가 props

표준 시그니처 (`data` / `onEdit` / `onDelete?` / `codeList?` · `isNew` / `initialData` / `onSubmit` / `onCancel?` / `codeList?`) 는 **유지**하되, 도메인상 필요한 아래 prop 은 **추가 가능** (Container 가 `viewProps` / `formProps` 로 주입):

| prop                         | 방향      | 용도                                       |
| ---------------------------- | --------- | ------------------------------------------ |
| `onRefresh?`                 | View/Form | 즉시 처리 하위 액션 후 master 목록 갱신    |
| `{scope}Id?` (예: `projectId`) | Form      | 2-depth 스코프 id                          |
| `canManage{X}?`              | View/Form | 권한 플래그 → 버튼/탭 노출 제어            |
| `codeList?`                  | View/Form | 코드 라벨 변환 (TableCell `items`)         |

> design-patterns 의 "narrow 타입 금지" 는 `codeList?: any` 를 `{ sample: CodeItem[] }` 처럼 **좁히지 말라**는 뜻 — 도메인 prop **추가** 를 금지하는 게 아니다. Phase C 에서 위 prop 들은 정상으로 인정.
