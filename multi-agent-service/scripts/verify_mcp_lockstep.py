"""lockstep 계약 정적 검증 — MCP tool 이름 소비자 ↔ MCP 라우터 operation_id.

소비자 2축:
  - multi-agent-service agents/domains/*.py 의 SUBAGENT_SPECS.mcp_tools
  - backend-service app/ 의 call_mcp_tool(..., "리터럴") 호출부 (AST 문자열 인자)

계약: 소비자의 모든 tool 이름이 어느 *-mcp-service 라우터의 operation_id 와
정확히 일치해야 한다 (operation_id 가 FastMCP tool 이름의 SoT).
multi-agent 쪽 위반은 "기동 시 경고 후 제외"로 조용히 사라지고 (app/agents/sub_agents.py),
backend-service 쪽은 런타임 ValueError (clients/mcp/mcp_client.py) 라 정적 검사가 회귀 방어선이다.

검사 2가지:
  (1) 소비자 이름 ⊆ 공급자 operation_id 합집합 — 미존재 이름은 위반
  (2) operation_id 전역 유일성 — MultiServerMCPClient 가 tool 이름을 평탄화하므로
      서버 간 중복은 조용한 섀도잉

공급자 미사용 tool 은 위반 아님 (타 소비자·향후 바인딩용).
template-mcp-service 는 복사용 템플릿(미기동)이라 공급자에서 제외.

stdlib 전용 (AST 파싱, import 없음) — 의존성·env 없이 어디서든:
`python3 multi-agent-service/scripts/verify_mcp_lockstep.py` (cwd 무관).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOMAINS_DIR = REPO_ROOT / "multi-agent-service/app/agents/domains"
LITERAL_CALL_DIRS = [REPO_ROOT / "backend-service/app"]
EXCLUDED_SERVICES = {"template-mcp-service"}


def check_scan_roots() -> list[str]:
    """설정된 스캔 루트가 실제로 있는지 확인 — 없는 경로는 rglob 이 조용히 빈 결과를 낸다.

    폴더 이동·삭제로 이 목록이 현실과 어긋나면 위반 0건 → exit 0 으로 "검사가 사라진 채 초록"이 된다
    (실측: 흡수로 devactivity-service 가 사라진 뒤 리터럴 검사가 0개를 세며 통과했다).
    검사 대상이 없는 것과 위반이 없는 것은 다르므로, 여기서 빨강으로 끊는다.
    """
    return [str(path.relative_to(REPO_ROOT)) for path in [DOMAINS_DIR, *LITERAL_CALL_DIRS] if not path.is_dir()]


def collect_consumer() -> dict[str, list[str]]:
    """{sub_agent_name: [tool, ...]} — SUBAGENT_SPECS dict 의 키·mcp_tools 리터럴 추출."""
    out: dict[str, list[str]] = {}
    for path in sorted(DOMAINS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values, strict=True):
                if not (
                    isinstance(key, ast.Constant)
                    and isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id == "SubAgentSpec"
                ):
                    continue
                for kw in value.keywords:
                    if kw.arg == "mcp_tools" and isinstance(kw.value, ast.List):
                        out[key.value] = [ast.literal_eval(e) for e in kw.value.elts]
    return out


def _literal_tool_name(call: ast.Call) -> str | None:
    """call_mcp_tool 의 tool_name 인자 — 문자열 리터럴(위치 2번째 또는 tool_name= 키워드)만 추출."""
    if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant) and isinstance(call.args[1].value, str):
        return call.args[1].value
    for kw in call.keywords:
        if kw.arg == "tool_name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def collect_literal_calls() -> dict[str, list[str]]:
    """{tool_name: ["path:line", ...]} — call_mcp_tool 호출부의 리터럴 tool 이름 추출."""
    out: dict[str, list[str]] = {}
    for base in LITERAL_CALL_DIRS:
        for path in sorted(base.rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (
                    (isinstance(func, ast.Name) and func.id == "call_mcp_tool")
                    or (isinstance(func, ast.Attribute) and func.attr == "call_mcp_tool")
                ):
                    continue
                name = _literal_tool_name(node)
                if name is not None:
                    out.setdefault(name, []).append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    return out


def collect_provider() -> tuple[dict[str, str], list[str]]:
    """({operation_id: 서비스}, [중복 메시지]) — 라우터 데코레이터의 operation_id 추출."""
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for routers_dir in sorted(REPO_ROOT.glob("*-mcp-service/app/routers")):
        service = routers_dir.parents[1].name
        if service in EXCLUDED_SERVICES:
            continue
        for path in sorted(routers_dir.rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for kw in node.keywords:
                    if kw.arg == "operation_id" and isinstance(kw.value, ast.Constant):
                        name = kw.value.value
                        if name in seen:
                            duplicates.append(f"{name}: {seen[name]} vs {service}")
                        seen[name] = service
    return seen, duplicates


def main() -> int:
    if missing_roots := check_scan_roots():
        print("스캔 루트가 없음 — 검사가 조용히 비는 상태다. 폴더 이동이면 이 스크립트의 경로 상수를 갱신하세요:")
        for rel in missing_roots:
            print(f"  - {rel}")
        return 1

    consumer = collect_consumer()
    literal_calls = collect_literal_calls()
    provider, duplicates = collect_provider()

    if not consumer or not provider:
        print(f"수집 실패: sub-agent {len(consumer)}개 / operation_id {len(provider)}개 — 경로·파싱 확인")
        return 1

    missing = sorted({t for tools in consumer.values() for t in tools} - set(provider))
    missing_literals = sorted(set(literal_calls) - set(provider))

    ok = True
    if missing:
        ok = False
        print("mcp_tools 에 있으나 어느 MCP 라우터 operation_id 에도 없음 (기동 시 tool 제외됨):")
        for name in missing:
            users = ", ".join(s for s, tools in consumer.items() if name in tools)
            print(f"  - {name} (사용: {users})")
    if missing_literals:
        ok = False
        print("call_mcp_tool 리터럴이 어느 MCP 라우터 operation_id 에도 없음 (런타임 ValueError):")
        for name in missing_literals:
            print(f"  - {name} (호출: {', '.join(literal_calls[name])})")
    if duplicates:
        ok = False
        print("operation_id 중복 (MultiServerMCPClient 에서 조용히 섀도잉됨):")
        for msg in duplicates:
            print(f"  - {msg}")

    if ok:
        n_tools = len({t for tools in consumer.values() for t in tools})
        print(
            f"lockstep OK — sub-agent {len(consumer)}개의 tool 이름 {n_tools}개 + "
            f"call_mcp_tool 리터럴 {len(literal_calls)}개 전부 operation_id {len(provider)}개에 존재, 중복 없음"
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
