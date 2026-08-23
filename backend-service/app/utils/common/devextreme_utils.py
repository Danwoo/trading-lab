"""DevExtreme 파라미터 파싱 및 SQL 변환 유틸리티"""

import json
import re
from typing import Any

from core.exceptions import BadRequestError

# SQL 식별자 검증: 알파벳, 숫자, 밑줄만 허용 (SQL injection 방지)
_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# 중첩 그룹 재귀의 깊이 상한 — frontend/lib/devextreme/filters.ts 의 `MAX_FILTER_DEPTH` 와
# **같은 값**이어야 한다. 두 파서가 다른 상한을 쓰면 같은 필터가 한쪽만 통과해 #295 가 없앤
# 발산이 되살아난다. 값의 근거(실측 최대 깊이 4, 화면이 만드는 최대 2)는 그 파일의 주석에 있다.
#
# 상한이 없으면 클라이언트가 보낸 3KB 짜리 필터 하나가 `RecursionError` 를 내고, 그건
# `RuntimeError` 의 서브클래스라 core/exception_handler.py 의 handle_runtime_error 에 잡혀
# **500** 이 됐다 (#401 실측). 문법 오류를 400 으로 접는 설계가 이 축에서만 뚫려 있었다.
_MAX_FILTER_DEPTH = 32


def _validate_identifier(name: str) -> str:
    """SQL 식별자(컬럼명/필드명)가 안전한지 검증

    문자열이 아닌 값도 여기서 접는다 — `re.match` 에 리스트를 넘기면 TypeError 가 나고, 그건
    전역 예외 처리기를 타 **500** 이 된다(`sort=[{"selector": ["a"]}]` 로 도달한다). frontend 쪽
    `validateIdentifier` 는 같은 입력을 이미 400 으로 접는다 — 두 파서의 판정을 맞춘다(#401 ①).
    """
    if not isinstance(name, str) or not name or not _SAFE_IDENTIFIER_RE.match(name):
        raise BadRequestError(f"유효하지 않은 필드명입니다: {name}")
    return name


# JSON 디코딩 자체의 재귀 한계 — `json.loads` 는 중첩 약 1만 단에서 `RecursionError` 를 던진다
# (실측: 견디는 최대 깊이 9997, 약 20KB 요청 하나). `RecursionError` 는 `RuntimeError` 의
# 서브클래스라 core/exception_handler.py 의 handle_runtime_error 에 잡혀 **500** 이 된다 —
# 아래 `_MAX_FILTER_DEPTH` 가 막는 것은 표현식 재귀뿐이라 그보다 앞 단계인 이 층을 따로 접는다.
# frontend 의 `JSON.parse` 는 같은 입력을 재귀 없이 처리해 예외가 없다(#401 ②).
_JSON_DEPTH_MESSAGE = "필터/정렬 JSON 중첩이 너무 깊습니다."


def parse_filter_sort(
    filter: str | None = None,
    sort: str | None = None,
) -> tuple[Any, Any]:
    """DevExtreme 그리드 filter/sort 파라미터 파싱

    Args:
        filter: JSON 문자열 형태의 필터 조건
        sort: JSON 문자열 형태의 정렬 조건

    Returns:
        tuple[Any, Any]: (filter_obj, sort_obj) 파싱된 객체 튜플

    Raises:
        HTTPException: JSON 파싱 실패 시 400 에러
    """
    try:
        filter_obj = json.loads(filter) if filter else None
        sort_obj = json.loads(sort) if sort else None
        return filter_obj, sort_obj
    except json.JSONDecodeError as e:
        raise BadRequestError("잘못된 filter/sort 형식입니다.") from e
    except RecursionError as e:
        raise BadRequestError(_JSON_DEPTH_MESSAGE) from e


# 값이 비어 있는 행의 자리 — 방향과 무관하게 항상 끝이다.
#
# PostgreSQL 의 기본은 `ASC` 면 NULLS LAST, `DESC` 면 NULLS FIRST 다. 즉 NULL 이 "가장 큰 값"으로
# 취급돼, 목표가를 내림차순으로 정렬하면 **목표가가 없는 행**이 1등으로 온다 — "가장 높은 목표가"를
# 찾으려고 열 머리를 누른 사람이 맨 위에서 보는 것은 빈 칸이다(#352). 격자에서 열을 정렬하는 것은
# "값이 큰 것부터 보여 달라"는 뜻이므로, 값이 없는 행은 어느 방향에서든 뒤로 보낸다.
#
# ASC 에서는 PostgreSQL 기본과 결과가 같지만 그래도 명시한다 — 방향마다 규칙이 갈리면 다음 사람이
# 다시 이 함정을 판단해야 하고, 이 유틸은 이미 방언 중립이 아니다(ILIKE). 규칙을 SQL 에 적어 두면
# 읽는 사람이 방언 기본값을 몰라도 정렬 결과를 안다.
_NULLS_POSITION = "NULLS LAST"


def parse_sort(sort_obj) -> str | None:
    """DevExtreme sort 배열을 SQL ORDER BY 문자열로 변환"""
    if isinstance(sort_obj, str):
        try:
            sort_obj = json.loads(sort_obj)
        except json.JSONDecodeError:
            return None
        except RecursionError as e:
            raise BadRequestError(_JSON_DEPTH_MESSAGE) from e

    if isinstance(sort_obj, list) and len(sort_obj) > 0:
        sort_clauses = []
        for s in sort_obj:
            # 항이 dict 가 아니면 거절한다 — `[None]` 은 `.get` 에서 AttributeError 를 내고
            # 그게 전역 예외 처리기를 타 500 이 됐다. frontend 쪽 convertSortToPrismaOrderBy 도
            # 같은 입력을 400 으로 접는다 (#401).
            if not isinstance(s, dict):
                raise BadRequestError(f"정렬 항목은 객체여야 합니다: {s!r}")
            selector = s.get("selector")
            desc = s.get("desc", False)
            if selector:
                _validate_identifier(selector)
                direction = "DESC" if desc else "ASC"
                sort_clauses.append(f"{selector} {direction} {_NULLS_POSITION}")
        return ", ".join(sort_clauses)

    return None


# 텍스트 연산자의 LIKE 패턴 — 와일드카드를 SQL 이 아니라 바인드 값에 붙인다.
#
# SQL 안에서 문자열을 잇는 방식은 방언마다 갈린다: `+` 는 PostgreSQL 에 text 연산자가 없어
# 실패하고, `||` 는 MSSQL 에 없다. 양쪽 문법인 `CONCAT` 도 PostgreSQL 에서는
# `concat(VARIADIC "any")` 라 타입 없는 바인드 파라미터를 못 푼다
# (`could not determine data type of parameter`). 패턴을 파이썬에서 만들면 SQL 은
# `ILIKE :param` 하나로 남아 문자열 연결의 방언차를 아예 만들지 않는다.
_LIKE_PATTERNS = {
    "contains": "%{}%",
    "notcontains": "%{}%",
    "startswith": "{}%",
    "endswith": "%{}",
}


# 그리드 검색은 사용자가 친 글자를 문자 그대로 찾는다는 의미다. 값 안의 `%`·`_` 를 그냥 두면
# 와일드카드로 해석돼 `%` 한 글자가 전건을 부른다. PostgreSQL 의 LIKE/ILIKE 는 ESCAPE 절이
# 없으면 백슬래시가 기본 이스케이프 문자이므로 그것에 기댄다 — 다른 방언으로 옮기면 여기부터
# 다시 확인해야 한다. 같은 filter JSON 을 소비하는 프론트엔드
# (`frontend/lib/grid/filters.ts` 의 escapeLikeValue) 와 같은 규약이어야 한다.
_LIKE_WILDCARD_RE = re.compile(r"[\\%_]")


def like_pattern(op: str, value):
    """텍스트 연산자의 바인드 값을 LIKE 패턴으로 감싼다 (filter_condition 과 한 쌍).

    값이 None 이면 그대로 둔다 — `컬럼 ILIKE NULL` 은 무매칭이라
    문자열 연결 시절(`'%' + NULL + '%'` → NULL)의 의미가 보존된다.

    이스케이프는 감싸기 **전**에 한다 — 뒤에 하면 패턴 자신의 와일드카드까지 죽는다.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = _LIKE_WILDCARD_RE.sub(r"\\\g<0>", value)
    return _LIKE_PATTERNS[op].format(value)


def filter_condition(field, op, param_name, value=None) -> str:
    """DevExtreme 필터 연산자를 SQL WHERE 조건으로 변환

    텍스트 검색은 대소문자를 가리지 않는다(`ILIKE`) — 그리드 검색은 사용자가 입력한 대소문자와
    무관하게 같은 행을 찾아야 한다. `ILIKE` 는 PostgreSQL 전용이라 이 유틸은 방언 중립이 아니다;
    다른 방언으로 옮기면 그쪽의 대소문자 무관 비교(collation·`LOWER()`)로 바꿔야 한다.
    """
    # 연산자 자리에 문자열이 아닌 값이 오면 먼저 접는다. 아래 `op in conditions` 는 dict 조회라
    # 해시 불가능한 값(list·dict)에서 TypeError 를 내는데, 그건 전역 예외 처리기를 타고 500 이
    # 된다 — 클라이언트가 보낸 값이 서버 오류가 되는 것이다(#389). frontend 쪽 filters.ts 는
    # switch 문의 default 로 같은 입력을 이미 400 으로 거절해 왔다.
    if not isinstance(op, str):
        raise BadRequestError(f"지원하지 않는 연산자: {op}")

    conditions = {
        "contains": f"{field} ILIKE :{param_name}",
        "notcontains": f"{field} NOT ILIKE :{param_name}",
        "startswith": f"{field} ILIKE :{param_name}",
        "endswith": f"{field} ILIKE :{param_name}",
        ">": f"{field} > :{param_name}",
        ">=": f"{field} >= :{param_name}",
        "<": f"{field} < :{param_name}",
        "<=": f"{field} <= :{param_name}",
        "between": f"({field} BETWEEN :{param_name}_start AND :{param_name}_end)",
        "isblank": f"({field} IS NULL OR {field} = '')",
        "isnotblank": f"({field} IS NOT NULL AND {field} <> '')",
    }

    # between 은 값이 [시작, 끝] 2원소 배열이어야 바인드 이름(_start/_end)이 둘 다 채워진다.
    # 여기서 거절하지 않으면 SQL 은 "BETWEEN :x_start AND :x_end" 로 나가는데 params 쪽엔
    # 채울 값이 없어 실행 시점 500 이 된다(#295 M-5) — 파싱 시점 400 으로 당긴다.
    if op == "between":
        if not (isinstance(value, list) and len(value) == 2):
            raise BadRequestError(f"between 연산자는 값이 [시작, 끝] 2개인 배열이어야 합니다: {field}")
        return conditions[op]

    if op in ("in", "anyof", "notin", "noneof"):
        # 값이 배열이 아니면 거절한다(#295 M-7) — 예전엔 스칼라를 [값] 으로 조용히 감쌌는데,
        # 그러면 frontend/lib/grid/filters.ts(조건을 통째로 버림)와 갈라진다. 어느 쪽도
        # "잘못된 입력을 조용히 통과"시키지 않는 쪽으로 모은다.
        if not isinstance(value, list):
            raise BadRequestError(f"{op} 연산자는 값이 배열이어야 합니다: {field}")
        # text() 는 스칼라 bindparam 만 지원 → list 를 개별 플레이스홀더로 전개
        negate = op in ("notin", "noneof")
        if not value:
            # 빈 배열: in/anyof 는 무매칭, notin/noneof 는 전체매칭 (IN () 문법오류 회피)
            return "(1 = 0)" if not negate else "(1 = 1)"
        placeholders = ", ".join(f":{param_name}_{i}" for i in range(len(value)))
        keyword = "NOT IN" if negate else "IN"
        return f"{field} {keyword} ({placeholders})"

    if op in conditions:
        return conditions[op]
    elif op == "=":
        return f"{field} = :{param_name}" if value is not None else f"{field} IS NULL"
    elif op in ("<>", "!="):
        return f"{field} <> :{param_name}" if value is not None else f"{field} IS NOT NULL"
    else:
        raise BadRequestError(f"지원하지 않는 연산자: {op}")


def parse_filter(filter_obj, param_index=0) -> tuple[str, dict]:
    """DevExtreme filter 포맷을 SQL WHERE로 변환"""
    sql, params, _ = _parse_expression(filter_obj, param_index, 1)
    return sql, params


def _parse_expression(filter_obj, param_index: int, depth: int = 1) -> tuple[str, dict, int]:
    """(SQL, 바인드, 다음 파라미터 번호) 를 돌려준다 — 번호를 형제에게 넘겨야 이름이 안 겹친다.

    한 조건이 소비하는 **번호**와 만들어내는 **바인드 개수**는 다르다: `isblank` 는 번호를
    쓰고도 바인드를 안 만들고, `between`·`in` 은 번호 하나로 바인드를 여럿 만든다. 그래서
    바인드 개수로 번호를 밀면 형제가 같은 이름을 집어, 뒤 값이 앞 조건을 오류 없이 덮어쓴다.
    """
    # 깊이 검사는 다른 어떤 처리보다 먼저다 — 아래 분기들이 재귀를 부르기 때문이다.
    if depth > _MAX_FILTER_DEPTH:
        raise BadRequestError(f"필터 중첩이 너무 깊습니다 (최대 {_MAX_FILTER_DEPTH}단).")

    # 형식이 깨진 필터를 "필터 없음"으로 삼키면 전건이 나간다 — 사용자는 필터가 걸렸다고
    # 믿는데 제약이 없는 결과를 받는다(#389). 필터가 아예 안 온 경우("filter" 키 부재·None)는
    # build_filter_params 가 이 함수를 부르기 전에 가른다.
    if isinstance(filter_obj, str):
        try:
            filter_obj = json.loads(filter_obj)
        except json.JSONDecodeError as e:
            raise BadRequestError("잘못된 filter 형식입니다: JSON 을 읽을 수 없습니다.") from e
        except RecursionError as e:
            raise BadRequestError(_JSON_DEPTH_MESSAGE) from e

    if not isinstance(filter_obj, list):
        raise BadRequestError(f"필터는 배열이어야 합니다: {filter_obj!r}")

    # 빈 배열 `[]`, 항 없는 부정 `["!"]` — DevExtreme 이 "아무것도 안 맞음" 뜻으로 회선에
    # 올리는 형태다(검색 패널이 오늘도 도달시킨다, #306). 아래 그룹 처리로 흘려보내면
    # operands 가 비어 "" 를 돌려주고, build_filter_params 는 그것을 "필터 없음"으로 읽어
    # 전건을 반환한다 — DevExtreme 의 뜻과 정반대다. 항상 거짓인 조건으로 명시한다.
    if filter_obj == [] or filter_obj == ["!"]:
        return "(1 = 0)", {}, param_index

    # NOT 조건: ["!", condition]
    #
    # 피연산자가 리스트가 아니면 거절한다 — 예전엔 하위 파싱이 빈 SQL 을 내고 여기서 ""(필터
    # 없음)로 빠져나가, `["!", "x"]` 가 전건을 냈다(#389). 부정이 통째로 사라진 정반대 결과다.
    if len(filter_obj) == 2 and filter_obj[0] == "!":
        if not isinstance(filter_obj[1], list):
            raise BadRequestError("부정(!) 의 피연산자는 조건 배열이어야 합니다.")
        sub_sql, sub_params, next_index = _parse_expression(filter_obj[1], param_index, depth + 1)
        return f"NOT {sub_sql}", sub_params, next_index

    # 항이 더 붙은 `!` 는 문법에 없다. 아래 그룹 처리로 흘려보내면 `!` 가 and/or 가 아닌
    # 문자열이라 조용히 버려져, 부정이 사라진 정반대 조건이 나간다.
    if len(filter_obj) > 2 and filter_obj[0] == "!":
        raise BadRequestError("잘못된 부정 조건 형식입니다.")

    # 단일 조건: ["field", "operator", value]
    if len(filter_obj) == 3 and isinstance(filter_obj[0], str):
        field, op, value = filter_obj

        _validate_identifier(field)
        param_name = f"filter_param_{param_index}"
        sql = filter_condition(field, op, param_name, value)

        params = {}
        if op == "between" and isinstance(value, list) and len(value) == 2:
            params[f"{param_name}_start"] = value[0]
            params[f"{param_name}_end"] = value[1]
        elif op in ("isblank", "isnotblank"):
            pass  # SQL에 값 파라미터 없음
        elif op in ("in", "anyof", "notin", "noneof"):
            # filter_condition 이 이미 value 가 배열임을 확인했다 — 여기서 다시 스칼라를
            # [값] 으로 감싸면 위에서 막은 "조용한 통과"가 뒷문으로 되살아난다.
            for i, v in enumerate(value):
                params[f"{param_name}_{i}"] = v
        elif op in _LIKE_PATTERNS:
            params[param_name] = like_pattern(op, value)
        else:
            params[param_name] = value

        return sql, params, param_index + 1

    # 논리 연산자(AND/OR) 및 중첩 처리.
    # 연산자는 피연산자 사이에만 놓는다 — 문자열 목록에 그대로 이어붙이면 연산자가 없거나
    # 자식이 빈 SQL 을 낼 때 `(a = :p b = :q)`·`(AND a = :p)` 같은 문법 오류가 나간다.
    operands: list[str] = []
    operators: list[str] = []
    params = {}
    next_index = param_index
    pending_operator = None

    for item in filter_obj:
        if isinstance(item, list):
            sub_sql, sub_params, next_index = _parse_expression(item, next_index, depth + 1)
            if operands:
                operators.append(pending_operator or "AND")
            operands.append(sub_sql)
            params.update(sub_params)
            pending_operator = None
        elif isinstance(item, str) and item.lower() in ("and", "or"):
            # 좌항 없는 연산자는 문법 오류다 — DevExtreme 평가기도 `["and", A]` 에 0건을 낸다
            # (실측). 예전엔 이 토큰을 그냥 삼켜 A 만 남았다: 심판보다 넓은 결과다.
            if not operands:
                raise BadRequestError(f"연산자 앞에 조건이 없습니다: {item}")
            pending_operator = item.upper()
        # and/or 도 리스트도 아닌 항은 버린다(M-9) — DevExtreme 평가기도 `[A, 5, B]` 에서 그
        # 항을 무시하고 나머지를 AND 로 결합한다(실측).

    # 조건이 하나도 안 쌓였다 = 필터가 왔는데 형식이 문법에 없다. 예전엔 ""(제약 없음)를
    # 돌려줘 `["and"]`·`["a","="]`·`[1,"=",1]`·`["a","=",1,"and",2]` 가 전부 전건을 냈다(#389).
    # DevExtreme 평가기는 같은 입력에 0건 또는 예외를 낸다 — 전건은 어느 쪽도 아니다.
    if not operands:
        raise BadRequestError(f"필터에서 읽을 수 있는 조건이 없습니다: {filter_obj!r}")

    # 한 그룹 안에서 and 와 or 가 섞이면 거절한다(#295 M-2). DevExtreme 자신의 필터 컴파일러
    # (grid_core/m_utils.js compileCriteria → compileGroup)도 같은 입력에 E4019 를 던진다 —
    # `[A,"and",B,"or",C]` 같은 평면 배열은 이 프레임워크의 문법에도 없다. 여태 파이썬은
    # SQL 의 AND-가-OR-보다-우선 규칙에 기대 "(A AND B OR C)" 를 냈는데, 그건 우연히 조용히
    # 넘어간 것이지 문법이 허용한 게 아니다. 섞고 싶으면 괄호로 명시적으로 묶어야 한다.
    if len(operators) >= 2 and len(set(operators)) > 1:
        raise BadRequestError("같은 그룹 안에서 and 와 or 를 섞어 쓸 수 없습니다. 괄호로 묶어 중첩하세요.")

    parts = [operands[0]]
    for operator, operand in zip(operators, operands[1:], strict=True):
        parts.extend((operator, operand))

    return f"({' '.join(parts)})", params, next_index


def build_filter_params(args: dict) -> tuple[str, dict]:
    """필터 파라미터 빌드"""
    sql_where, sql_params = "", {}
    filter_obj = args.get("filter")

    # `None`("filter" 쿼리 파라미터 자체가 없음)과 `[]`(필터가 왔는데 내용이 비어 있음,
    # #306 의 "항상 거짓")를 구분해야 한다 — 예전엔 둘 다 `if filter_obj:` 에 falsy 로
    # 걸려 같은 취급(제약 없음 = 전건)이었다. parse_filter([]) 는 "(1 = 0)" 을 내지만,
    # 이 truthy 검사가 그 호출 자체를 막아 실제 HTTP 경로에서는 아무 효과가 없었다 —
    # `?filter=[]` 가 여전히 전건을 반환했다(교차 리뷰 지적, #306). `is not None` 은
    # `[]`·`0`·`""`·`False` 같은 다른 falsy JSON 값도 parse_filter 로 들여보낸다 — `[]` 는
    # "항상 거짓"(#306), 나머지는 리스트가 아니므로 400 이다(#389 — 예전엔 빈 SQL 을 돌려줘
    # 전건이 나갔다). 쿼리스트링이 `?filter=` 로 비어 온 경우는 parse_filter_sort 가 None 으로
    # 만들어 이 분기 자체를 안 탄다.
    #
    # parse_filter 는 이제 빈 SQL 을 돌려주지 않는다 — 읽을 수 없는 형식이면 예외로 접는다.
    # 그래서 "필터가 왔는데 sql_where 는 비어 있다"(= 제약 없이 전건)는 상태가 만들어지지 않는다.
    if filter_obj is not None:
        filter_sql, filter_params = parse_filter(filter_obj)
        sql_where += f" AND {filter_sql}"
        sql_params.update(filter_params)

    return sql_where, sql_params
