#!/usr/bin/env bash
# 재도입 그물(check-terminal-devextreme-transitive.js)의 커버리지를 **주입으로** 증명한다.
#
# 왜 필요한가: 이 그물은 "#341 이 걷어낸 6종의 재도입 0건"을 지키는 유일한 자동 게이트다
# (CI 잡 `test: frontend-devextreme-scope`). 그런데 6종 중 하나만 주입해 보고 "그물이 산다"고
# 쓰면 나머지 5종의 커버리지는 아무도 안 센 채로 남는다 — 실제로 그렇게 4종이 뚫린 채
# 초록이었다(PR #417 독립 리뷰). 그래서 **6종 각각 + 허용 대상 오탐**을 매번 전수로 두들긴다.
#
# 사용법:  bash frontend/scripts/injection-probe-devextreme.sh     (frontend/ 안에서든 밖에서든)
# 성공하면 exit 0 과 "전수 통과" 한 줄. 하나라도 어긋나면 exit 1 + 어긋난 케이스 목록.

set -uo pipefail

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="$FRONTEND_DIR/scripts/check-terminal-devextreme-transitive.js"

# 주입 대상은 **실재하는 소스 파일**이다 — 새 파일을 만들면 그 파일 자신이 진입점이라
# "진입점에서 직접 import" 만 검증하게 된다. 이 파일은 DataTable 커널이 import 하는 모듈이라
# 배럴·상대경로를 거친 **전이 체인**까지 함께 두들긴다.
TARGET="$FRONTEND_DIR/components/shared/DataTable/gridColumnLayout.ts"
BACKUP="$(mktemp)"

# 차단돼야 하는 6종 — #341 이 package.json 에서 걷어낸 전부.
BANNED=(
  'devextreme'
  'devextreme-react'
  'devexpress-diagram'
  'devexpress-gantt'
  '@devexpress/utils'
  '@devextreme/runtime'
)
# 차단되면 **안 되는** 것 — 이름만 계열을 닮은 MIT exceljs 포크(레포가 실제로 쓴다).
ALLOWED=(
  'devextreme-exceljs-fork'
)

restore() { cp "$BACKUP" "$TARGET"; }
trap 'restore; rm -f "$BACKUP"' EXIT

cp "$TARGET" "$BACKUP"

failures=()
checked=0

run_checker() {
  node "$CHECKER" >/dev/null 2>&1
  echo $?
}

# 주입 전 기준선 — 깨끗한 트리에서 통과해야 그 뒤 exit 1 들이 "주입 때문"이라고 말할 수 있다.
base_exit="$(run_checker)"
if [ "$base_exit" != "0" ]; then
  echo "[injection-probe] 기준선 실패 — 주입 전 트리에서 이미 exit $base_exit. 주입 시험의 의미가 없습니다."
  exit 1
fi
echo "[injection-probe] 기준선(주입 없음): exit 0"

for pkg in "${BANNED[@]}"; do
  restore
  printf '\nimport "%s";\n' "$pkg" >>"$TARGET"
  code="$(run_checker)"
  checked=$((checked + 1))
  if [ "$code" = "1" ]; then
    echo "[injection-probe] 차단 대상 '$pkg' 주입 → exit $code  (기대 1) ✓"
  else
    echo "[injection-probe] 차단 대상 '$pkg' 주입 → exit $code  (기대 1) ✗"
    failures+=("차단 실패: $pkg (exit $code)")
  fi
done

for pkg in "${ALLOWED[@]}"; do
  restore
  printf '\nimport "%s";\n' "$pkg" >>"$TARGET"
  code="$(run_checker)"
  checked=$((checked + 1))
  if [ "$code" = "0" ]; then
    echo "[injection-probe] 허용 대상 '$pkg' 주입 → exit $code  (기대 0) ✓"
  else
    echo "[injection-probe] 허용 대상 '$pkg' 주입 → exit $code  (기대 0) ✗"
    failures+=("오탐: $pkg (exit $code)")
  fi
done

restore

# fail-closed — 케이스가 0건이면 "위반 없음"이 아니라 "아무것도 안 두들겼음"이다.
expected=$(( ${#BANNED[@]} + ${#ALLOWED[@]} ))
if [ "$checked" -ne "$expected" ]; then
  echo "[injection-probe] 검사 건수 $checked 건 — 기대 $expected 건과 다릅니다. 목록이 어긋났습니다."
  exit 1
fi

if [ ${#failures[@]} -gt 0 ]; then
  echo ""
  echo "[injection-probe] ${#failures[@]}건 어긋남:"
  printf '  - %s\n' "${failures[@]}"
  exit 1
fi

echo "[injection-probe] 주입 ${checked}건(차단 ${#BANNED[@]} · 허용 ${#ALLOWED[@]}) 전수 통과."
