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

# fail-closed — 대상이 사라지면 시험은 자기 머리에 적은 근거(전이 체인)를 잃는다. 그런데
# `printf >>` 가 없던 경로에 새 파일을 만들어 7건이 전부 「기대대로」 나오고, trap 이 빈
# 백업을 덮어써 0바이트 파일까지 남았다 — 「전수 통과」로 끝나는 강등이었다 (#331).
if [ ! -f "$TARGET" ]; then
  echo "[injection-probe] 주입 대상이 없습니다: $TARGET"
  echo "[injection-probe] 리네임·이동됐다면 이 스크립트의 TARGET 도 함께 옮기세요 (전이 체인을 무는 실재 파일이어야 합니다)."
  exit 1
fi

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

# 실패해도 여기서 종료하지 않는다 — 끝의 `cmp` 가 원복 결과를 판정한다 (트랩 안 exit 은
# 종료 코드를 덮어써 주입 결과를 가린다).
restore() { cp "$BACKUP" "$TARGET" || echo "[injection-probe] 원복 실패: $TARGET"; }
trap 'restore; rm -f "$BACKUP"' EXIT

cp "$TARGET" "$BACKUP" || {
  echo "[injection-probe] 백업을 뜨지 못했습니다: $TARGET → $BACKUP"
  exit 1
}

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

# 시험이 소스를 망가뜨리고 끝나는 경로를 닫는다 — 원복이 바이트 동일해야 한다.
if ! cmp -s "$BACKUP" "$TARGET"; then
  echo "[injection-probe] 원복이 원본과 다릅니다: $TARGET — 주입 잔재가 남았습니다."
  exit 1
fi

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

echo "[injection-probe] 주입 ${checked}건(차단 ${#BANNED[@]} · 허용 ${#ALLOWED[@]}) 전수 통과 · 대상 원복 바이트 동일."
