/* eslint-env node */
const { generatorHandler } = require("@prisma/generator-helper");
const fs = require("fs");
const path = require("path");

/**
 * Prisma Schema Complete SQL Generator for PostgreSQL
 *
 * Prisma 스키마 파일을 파싱하여 완전한 PostgreSQL 데이터베이스 생성 스크립트를 만듭니다.
 * - 테이블 삭제 (DROP ... CASCADE — FK 제약을 함께 정리하므로 순서 무관)
 * - 테이블 생성 (컬럼 · PK)
 * - 외래키 · 인덱스 생성
 * - 주석 (COMMENT ON — MSSQL EXTENDED PROPERTIES 의 대응물)
 *
 * 식별자는 큰따옴표로 감싼다: Postgres 는 따옴표 없는 식별자를 소문자로 폴딩하므로
 * 혼합케이스 컬럼(better-auth 의 emailVerified·createdAt 등)을 그대로 쓰려면 인용이 필수 (#166).
 */

// Prisma 소유 스키마. 실제 접속의 SoT 는 `DATABASE_URL` 의 `?schema=` 이고, 여기 상수는 이 스크립트를
// psql 로 직접 적용할 때 쓸 search_path 다 — 생성 시점에는 DATABASE_URL 이 없을 수 있어(prisma.config.ts
// 참조) URL 에서 읽지 않고 못 박는다. 스키마를 옮기면 두 곳을 함께 바꾼다.
const TARGET_SCHEMA = "frontend";

generatorHandler({
  onManifest() {
    return {
      defaultOutput: "../init",
      prettyName: "Prisma Complete SQL Generator",
      requiresGenerators: [],
    };
  },

  async onGenerate(options) {
    const outputDir = options.generator.output?.value || path.join(options.schemaPath, "..", "init");
    const outputPath = path.join(outputDir, "tables.sql");

    console.log("🔍 Generating complete database SQL...");

    try {
      const models = parseSchema(options.dmmf.datamodel.models, options.dmmf.datamodel.indexes);
      const sql = generateCompleteSQL(models);

      // 출력 디렉토리 생성
      if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
      }

      fs.writeFileSync(outputPath, sql, "utf-8");

      console.log(`✅ Complete SQL file generated: ${outputPath}`);
      console.log(`📊 Models: ${models.length}`);
    } catch (error) {
      console.error("❌ Error generating SQL:", error.message);
      throw error;
    }
  },
});

/**
 * Prisma DMMF 모델을 파싱합니다
 */
function parseSchema(dmmfModels, dmmfIndexes) {
  const models = [];

  for (const model of dmmfModels) {
    const parsedModel = {
      name: model.name,
      comment: model.documentation || null,
      tableName: model.dbName || model.name,
      allFields: [], // 모든 필드 정보 (테이블 생성용 + 주석용)
      foreignKeys: [], // 외래키 정보
      indexes: [], // 인덱스 정보
    };

    for (const field of model.fields) {
      // 모든 필드 정보 저장 (테이블 생성용 + 주석용)
      if (field.kind !== "object") {
        // relation 필드 제외

        // nativeType 정보 추출 - Prisma는 [typeName, [args]] 형태로 전달
        let nativeTypeInfo = null;
        if (field.nativeType && Array.isArray(field.nativeType)) {
          nativeTypeInfo = {
            name: field.nativeType[0],
            args: field.nativeType[1] || [],
          };
        }

        parsedModel.allFields.push({
          name: field.dbName || field.name,
          type: typeof field.type === "string" ? field.type : field.type?.name || field.type,
          isRequired: field.isRequired,
          isList: field.isList,
          isId: field.isId,
          isUnique: field.isUnique,
          hasDefaultValue: field.hasDefaultValue,
          default: field.default,
          isUpdatedAt: field.isUpdatedAt,
          documentation: field.documentation, // 주석 포함
          dbName: field.dbName,
          nativeType: nativeTypeInfo,
        });
      } else if (field.kind === "object" && field.relationName) {
        // 외래키 관계 정보 추출
        if (field.relationFromFields && field.relationFromFields.length > 0) {
          parsedModel.foreignKeys.push({
            name: field.relationName,
            fields: field.relationFromFields,
            references: field.relationToFields || [],
            referencedTable: field.type,
            // 스키마에 안 적은 관계는 DMMF 가 undefined 를 준다 — 그 자리는 Prisma 기본값으로
            // 채운다(referentialActions 참고). 안 채우면 이 생성물만 NO ACTION 이 된다.
            onDelete: field.relationOnDelete,
            onUpdate: field.relationOnUpdate,
            isRequired: field.isRequired,
          });
        }
      }
    }

    // 복합 키 정보
    if (model.primaryKey) {
      parsedModel.primaryKey = model.primaryKey.fields;
    }

    // 인덱스 정보 - DMMF의 최상위 indexes 배열에서 가져오기
    if (dmmfIndexes && dmmfIndexes.length > 0) {
      const modelIndexes = dmmfIndexes.filter((idx) => idx.model === model.name);

      for (const index of modelIndexes) {
        // type이 'id'인 것은 기본키이므로 제외
        // type이 'normal'인 것이 @@index, 'unique'인 것이 @@unique (필드 레벨이 아닌 경우)
        if (index.type !== "id" && !index.isDefinedOnField) {
          const fieldNames = index.fields.map((f) => f.name);
          parsedModel.indexes.push({
            name: index.name || null,
            fields: fieldNames,
            isUnique: index.type === "unique",
          });
        }
      }
    }

    models.push(parsedModel);
  }

  return models;
}

/**
 * 완전한 PostgreSQL 데이터베이스 생성 스크립트를 생성합니다
 */
function generateCompleteSQL(models) {
  const sqlLines = [];

  sqlLines.push("-- ============================================================================");
  sqlLines.push("-- Prisma Complete Database Generator (PostgreSQL)");
  sqlLines.push("-- ============================================================================");
  sqlLines.push("");

  // 스키마 고정 — 아래 DDL 은 전부 이 스키마에 적재된다. Prisma 소유 테이블은 frontend 스키마에
  // 살고 public 은 파이썬 서비스 몫이라, search_path 를 못 박지 않으면 이 스크립트가 남의
  // 스키마에 테이블을 만든다 (DB 는 fintech 하나 — .docs/5-인프라셋팅/로컬-postgres.md).
  sqlLines.push("-- ============================================================================");
  sqlLines.push("-- 0. 스키마 (frontend — Prisma 소유. public 은 파이썬 서비스 소유라 건드리지 않는다)");
  sqlLines.push("-- ============================================================================");
  sqlLines.push("");
  sqlLines.push(`CREATE SCHEMA IF NOT EXISTS ${quoteIdent(TARGET_SCHEMA)};`);
  sqlLines.push(`SET search_path TO ${quoteIdent(TARGET_SCHEMA)};`);
  sqlLines.push("");

  // 1. 테이블 삭제
  sqlLines.push("-- ============================================================================");
  sqlLines.push("-- 1. 기존 테이블 삭제 (CASCADE — 의존 FK 함께 정리)");
  sqlLines.push("-- ============================================================================");
  sqlLines.push("");
  sqlLines.push(...generateDropTables(models));
  sqlLines.push("");

  // 2. 테이블 생성
  sqlLines.push("-- ============================================================================");
  sqlLines.push("-- 2. 테이블 생성");
  sqlLines.push("-- ============================================================================");
  sqlLines.push("");
  sqlLines.push(...generateTableCreation(models));
  sqlLines.push("");

  // 3. 외래키 생성
  sqlLines.push("-- ============================================================================");
  sqlLines.push("-- 3. 외래키 생성");
  sqlLines.push("-- ============================================================================");
  sqlLines.push("");
  sqlLines.push(...generateForeignKeys(models));
  sqlLines.push("");

  // 4. 인덱스 생성
  sqlLines.push("-- ============================================================================");
  sqlLines.push("-- 4. 인덱스 생성");
  sqlLines.push("-- ============================================================================");
  sqlLines.push("");
  sqlLines.push(...generateIndexes(models));
  sqlLines.push("");

  // 5. 주석 추가
  sqlLines.push("-- ============================================================================");
  sqlLines.push("-- 5. 주석 (COMMENT ON)");
  sqlLines.push("-- ============================================================================");
  sqlLines.push("");
  sqlLines.push(...generateComments(models));

  return sqlLines.join("\n");
}

/**
 * 식별자 인용 (Postgres 는 인용하지 않으면 소문자로 폴딩)
 */
function quoteIdent(name) {
  return `"${String(name).replace(/"/g, '""')}"`;
}

/**
 * 기존 테이블 삭제 쿼리 생성
 */
function generateDropTables(models) {
  const sqlLines = [];

  for (const model of models) {
    sqlLines.push(`DROP TABLE IF EXISTS ${quoteIdent(model.tableName)} CASCADE;`);
  }

  return sqlLines;
}

/**
 * 테이블 생성 쿼리 생성
 */
function generateTableCreation(models) {
  const sqlLines = [];

  for (const model of models) {
    const tableName = model.tableName;

    sqlLines.push(`-- Create table ${tableName}`);
    sqlLines.push(`CREATE TABLE ${quoteIdent(tableName)} (`);

    const bodyLines = model.allFields.map((field) => `    ${generateColumnDefinition(field)}`);

    // Primary Key 정의
    const pkFields = model.primaryKey?.length
      ? model.primaryKey
      : model.allFields.filter((f) => f.isId).map((f) => f.name);
    if (pkFields.length > 0) {
      const pkColumns = pkFields.map(quoteIdent).join(", ");
      bodyLines.push(`    CONSTRAINT ${quoteIdent(`pk_${tableName}`)} PRIMARY KEY (${pkColumns})`);
    }

    sqlLines.push(bodyLines.join(",\n"));
    sqlLines.push(`);`);
    sqlLines.push("");
  }

  return sqlLines;
}

/**
 * 컬럼 정의 생성
 */
function generateColumnDefinition(field) {
  // 기본값 유무는 null/undefined 로만 판정한다 — @default(false)/@default(0) 은 falsy 라
  // truthy 검사로는 누락된다 (MSSQL 판에서 `emailVerified` DEFAULT 가 빠지던 버그).
  const hasDefault = field.hasDefaultValue && field.default !== undefined && field.default !== null;
  const isSerial = hasDefault && field.default.name === "autoincrement";

  let columnDef = `${quoteIdent(field.name)} `;

  // 데이터 타입 매핑 (autoincrement 는 serial 계열이 타입 자체를 대체)
  columnDef += isSerial ? mapAutoincrementType(field) : mapPrismaTypeToSQL(field);

  // NULL 여부
  columnDef += field.isRequired ? " NOT NULL" : " NULL";

  // DEFAULT 값 (serial 은 시퀀스가 기본값이므로 제외)
  if (!isSerial && hasDefault) {
    if (field.default.name === "now") {
      columnDef += " DEFAULT CURRENT_TIMESTAMP";
    } else if (field.default.name === "dbgenerated") {
      // dbgenerated는 스킵
    } else {
      const defaultValue = typeof field.default === "object" ? field.default.args?.[0] : field.default;
      if (defaultValue !== undefined) {
        columnDef += ` DEFAULT ${formatDefaultValue(defaultValue, field.type)}`;
      }
    }
  }

  // UNIQUE
  if (field.isUnique) {
    columnDef += " UNIQUE";
  }

  return columnDef;
}

/**
 * autoincrement 필드의 타입 (Postgres serial 계열)
 */
function mapAutoincrementType(field) {
  return field.type === "BigInt" ? "BIGSERIAL" : "SERIAL";
}

/**
 * Prisma 타입을 PostgreSQL 타입으로 매핑
 */
function mapPrismaTypeToSQL(field) {
  const type = field.type;

  // Prisma의 native type 정보 확인 (@db.VarChar(100) 등)
  if (field.nativeType && field.nativeType.name) {
    const nativeType = field.nativeType;

    // VarChar/Char — 길이 인자가 없으면 TEXT (Postgres 는 무제한 varchar 표기가 없음)
    if (nativeType.name === "VarChar" || nativeType.name === "Char") {
      const length = Number(nativeType.args?.[0]);
      if (!isNaN(length) && length > 0) {
        return `${nativeType.name === "Char" ? "CHAR" : "VARCHAR"}(${length})`;
      }
      return "TEXT";
    }

    // Text 타입
    if (nativeType.name === "Text") {
      return "TEXT";
    }

    // Decimal 타입
    if (nativeType.name === "Decimal") {
      const precision = nativeType.args?.[0] || 18;
      const scale = nativeType.args?.[1] || 2;
      return `DECIMAL(${precision},${scale})`;
    }

    // 날짜/시간 타입
    if (nativeType.name === "Timestamp" || nativeType.name === "Timestamptz") {
      const precision = nativeType.args?.[0];
      const base = nativeType.name === "Timestamptz" ? "TIMESTAMPTZ" : "TIMESTAMP";
      return precision !== undefined && precision !== null ? `${base}(${precision})` : base;
    }

    // 기타 native type은 그대로 사용
    if (nativeType.args && nativeType.args.length > 0) {
      return `${nativeType.name.toUpperCase()}(${nativeType.args.join(",")})`;
    }
    return nativeType.name.toUpperCase();
  }

  // 기본 타입 매핑 (native type이 없는 경우 — Prisma 기본 매핑과 동일)
  switch (type) {
    case "String":
      return "TEXT";
    case "Int":
      return "INTEGER";
    case "BigInt":
      return "BIGINT";
    case "Float":
      return "DOUBLE PRECISION";
    case "Decimal":
      return "DECIMAL(65,30)";
    case "Boolean":
      return "BOOLEAN";
    case "DateTime":
      return "TIMESTAMP(3)";
    case "Json":
      return "JSONB";
    case "Bytes":
      return "BYTEA";
    default:
      return "TEXT";
  }
}

/**
 * DEFAULT 값 포맷팅
 */
function formatDefaultValue(value, type) {
  if (value === null || value === undefined) {
    return "NULL";
  }

  if (type === "String") {
    return `'${escapeSQLString(value)}'`;
  }

  if (type === "Boolean") {
    return value ? "TRUE" : "FALSE";
  }

  return value;
}

/**
 * FK 의 참조 동작(ON DELETE / ON UPDATE)을 Prisma 규약대로 결정한다.
 *
 * 이걸 안 붙이면 이 생성물의 FK 는 전부 Postgres 기본값 `NO ACTION` 이 되는데, 실제 배포는
 * `prisma db push` 로 세워지므로 같은 스키마가 **다른 참조 동작**을 갖게 된다 — 이 생성물로
 * 세운 DB(CI 잡·수동 부트스트랩·verify_*.py 의 scratch DB)만 운영과 다르게 동작한다.
 * 실측: 부모 키(`tn_user.email`) 변경이 db push DB 에서는 자식으로 전파(CASCADE)되고,
 * 이 생성물 DB 에서는 FK 위반으로 거부됐다 (#238 조사).
 *
 * 스키마에 명시된 값이 있으면 그것을 쓰고, 없으면 Prisma 의 기본값을 채운다 —
 * 필수 관계는 `ON DELETE RESTRICT`, 선택 관계는 `ON DELETE SET NULL`, 둘 다 `ON UPDATE CASCADE`.
 * 계약은 `backend-service/scripts/verify_frontend_fk_referential_actions.py` 가 잠근다.
 */
function referentialActions(fk) {
  const toSql = (action) =>
    ({
      Cascade: "CASCADE",
      Restrict: "RESTRICT",
      NoAction: "NO ACTION",
      SetNull: "SET NULL",
      SetDefault: "SET DEFAULT",
    })[action];

  const onDelete = toSql(fk.onDelete) || (fk.isRequired ? "RESTRICT" : "SET NULL");
  const onUpdate = toSql(fk.onUpdate) || "CASCADE";
  return ` ON DELETE ${onDelete} ON UPDATE ${onUpdate}`;
}

/**
 * 외래키 생성 쿼리 생성
 */
function generateForeignKeys(models) {
  const sqlLines = [];

  for (const model of models) {
    const tableName = model.tableName;

    if (model.foreignKeys && model.foreignKeys.length > 0) {
      for (const fk of model.foreignKeys) {
        // 참조 테이블 찾기
        const referencedModel = models.find((m) => m.name === fk.referencedTable);
        if (!referencedModel) continue;

        const referencedTableName = referencedModel.tableName;
        const fkName = `fk_${tableName}_${fk.fields.join("_")}`;
        const fkColumns = fk.fields.map(quoteIdent).join(", ");
        const refColumns = fk.references.map(quoteIdent).join(", ");

        sqlLines.push(`-- Add foreign key for ${tableName}.${fk.fields.join(", ")}`);
        sqlLines.push(
          `ALTER TABLE ${quoteIdent(tableName)} ADD CONSTRAINT ${quoteIdent(fkName)} ` +
            `FOREIGN KEY (${fkColumns}) REFERENCES ${quoteIdent(referencedTableName)} (${refColumns})` +
            `${referentialActions(fk)};`,
        );
        sqlLines.push("");
      }
    }
  }

  return sqlLines;
}

/**
 * 인덱스 생성 쿼리 생성
 */
function generateIndexes(models) {
  const sqlLines = [];

  for (const model of models) {
    const tableName = model.tableName;

    if (model.indexes && model.indexes.length > 0) {
      for (const index of model.indexes) {
        const indexName = index.name || `ix_${tableName}_${index.fields.join("_")}`;
        const indexColumns = index.fields.map(quoteIdent).join(", ");
        const uniqueKeyword = index.isUnique ? "UNIQUE " : "";

        sqlLines.push(`-- Add index for ${tableName}.${index.fields.join(", ")}`);
        sqlLines.push(
          `CREATE ${uniqueKeyword}INDEX ${quoteIdent(indexName)} ON ${quoteIdent(tableName)} (${indexColumns});`,
        );
        sqlLines.push("");
      }
    }
  }

  return sqlLines;
}

/**
 * 주석(COMMENT ON) 추가 쿼리 생성
 */
function generateComments(models) {
  const sqlLines = [];

  for (const model of models) {
    const tableName = model.tableName;

    sqlLines.push(`-- Add comments for ${tableName}`);

    // 테이블 주석
    if (model.comment) {
      sqlLines.push(`COMMENT ON TABLE ${quoteIdent(tableName)} IS '${escapeSQLString(model.comment)}';`);
    }

    // 컬럼 주석 (allFields에서 가져오기 - 모든 필드 포함)
    for (const field of model.allFields) {
      if (field.documentation) {
        sqlLines.push(
          `COMMENT ON COLUMN ${quoteIdent(tableName)}.${quoteIdent(field.name)} IS ` +
            `'${escapeSQLString(field.documentation)}';`,
        );
      }
    }

    sqlLines.push("");
  }

  return sqlLines;
}

/**
 * SQL 문자열 이스케이프 처리
 */
function escapeSQLString(str) {
  return str.replace(/'/g, "''");
}
