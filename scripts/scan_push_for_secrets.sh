#!/usr/bin/env bash
# push 되는 **커밋**을 시크릿으로 훑는다 — pre-push 단계 전용.
#
# **왜 공식 훅을 그대로 쓰지 않나**: gitleaks 의 pre-commit 훅은 `gitleaks protect --staged` 라
# **git 인덱스**를 본다. push 시점에는 커밋이 이미 끝나 인덱스가 비어 있는 것이 정상이므로,
# 그 훅을 pre-push 에 걸면 **아무것도 안 보고 늘 통과한다** — 있는 척만 하는 층이 된다.
#
# 여기서는 `PRE_COMMIT_FROM_REF..PRE_COMMIT_TO_REF`(pre-commit 이 push 범위로 넘겨주는 것)를
# 받아 그 구간의 커밋을 훑는다. 범위를 못 받으면 **훑을 것을 모르는 것**이므로 거부한다 —
# 조용히 통과시키면 이 층이 있으나 마나다.
#
# 우회는 `--no-verify` 뿐이고, 그렇게 들어온 것은 main 착륙 시 히스토리 전량 스캔이 받는다.
set -uo pipefail

FROM="${PRE_COMMIT_FROM_REF:-}"
TO="${PRE_COMMIT_TO_REF:-}"

if [ -z "$TO" ]; then
  echo "push 범위를 못 읽었습니다 (PRE_COMMIT_TO_REF 없음) — 훑을 것을 모르므로 거부합니다." >&2
  exit 1
fi

# 새 브랜치는 from 이 all-zero 다 — 그때는 「이 브랜치에만 있는 커밋」을 본다.
if [ -z "$FROM" ] || [ "$FROM" = "0000000000000000000000000000000000000000" ]; then
  RANGE="$TO --not --remotes"
else
  RANGE="$FROM..$TO"
fi

# **실패와 0 을 가른다.** `|| echo 0` 으로 뭉개면 rev-list 가 죽었을 때(FROM 이 로컬에 없는
# force push · 얕은 클론 · 객체 누락) 「새 커밋 없음」으로 읽혀 비밀이 든 push 가 스캔 한 번
# 없이 지나간다 — 이 파일 머리말이 금지한 바로 그것이다.
# shellcheck disable=SC2086
if ! COUNT=$(git rev-list --count $RANGE 2>&1); then
  echo "push 범위를 셀 수 없습니다 ($RANGE) — 훑을 것을 모르므로 거부합니다: $COUNT" >&2
  exit 1
fi
if ! [ "$COUNT" -eq "$COUNT" ] 2>/dev/null; then
  echo "push 범위의 커밋 수를 숫자로 읽지 못했습니다 ($COUNT) — 거부합니다." >&2
  exit 1
fi
if [ "$COUNT" -eq 0 ]; then
  echo "push 할 새 커밋이 없습니다 — 훑을 것이 없습니다."
  exit 0
fi

# 바이너리 찾기 — **pre-commit 이 이미 받아 둔 것을 먼저 쓴다.**
# 이 레포는 gitleaks 를 pre-commit 훅으로 쓰므로 그 캐시에 훅과 같은 판본이 있다. PATH 만
# 보면 그것을 두고도 「없다」고 막아, 개발자 기계의 **모든 push** 가 멎는다 (실측 — 이 층을
# 처음 켤 때 그렇게 됐다).
BIN="${GITLEAKS_BIN:-}"
if [ -z "$BIN" ] && command -v gitleaks >/dev/null 2>&1; then
  BIN="$(command -v gitleaks)"
fi
if [ -z "$BIN" ]; then
  BIN="$(find "${PRE_COMMIT_HOME:-$HOME/.cache/pre-commit}" -maxdepth 4 -type f -name gitleaks -perm -u+x 2>/dev/null | head -1)"
fi
if [ -z "$BIN" ] || [ ! -x "$BIN" ]; then
  echo "gitleaks 를 찾을 수 없습니다 — \`pre-commit install-hooks\` 를 돌리거나 GITLEAKS_BIN 을 주세요." >&2
  echo "  (찾은 곳: PATH · ${PRE_COMMIT_HOME:-$HOME/.cache/pre-commit})" >&2
  exit 1
fi

echo "push 커밋 ${COUNT}건을 훑습니다 ($RANGE)"
"$BIN" detect --redact --no-banner --source . --log-opts="$RANGE"
