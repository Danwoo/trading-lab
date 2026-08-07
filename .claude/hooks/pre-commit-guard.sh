#!/bin/bash
# Claude Code PreToolUse(Bash) hook — git commit 전에 pre-commit 선실행.
# fixer 자동수정 발생 시 기존 staged 파일만 재스테이징해 커밋이 한 번에 통과하게 한다.
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
case "$cmd" in
  *git\ commit*) ;;
  *) exit 0 ;;
esac

cwd=$(printf '%s' "$input" | jq -r '.cwd // empty')
[ -n "$cwd" ] && cd "$cwd" 2>/dev/null
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
[ -f .pre-commit-config.yaml ] || exit 0

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}

command -v pre-commit >/dev/null 2>&1 \
  || deny "pre-commit 명령을 찾을 수 없습니다. 설치 후 다시 시도하세요 (uv tool install pre-commit 또는 pip install pre-commit)."

# git hook 미설치면 자동 install
hookfile=$(git rev-parse --git-path hooks/pre-commit)
if [ ! -f "$hookfile" ] || ! grep -q pre-commit "$hookfile" 2>/dev/null; then
  pre-commit install >/dev/null 2>&1 || deny "pre-commit install 실패 — 수동 확인이 필요합니다."
fi

staged=$(git diff --cached --name-only --diff-filter=d)
[ -n "$staged" ] || exit 0

if ! out=$(pre-commit run 2>&1); then
  # fixer가 staged 파일을 고쳤을 수 있음 — 그 파일들만 재스테이징 후 1회 재검사
  printf '%s\n' "$staged" | xargs -d '\n' git add -- 2>/dev/null
  if ! out=$(pre-commit run 2>&1); then
    deny "pre-commit 실패 — 자동수정으로 해결되지 않는 오류입니다. 직접 수정 후 다시 커밋하세요.
$(printf '%s' "$out" | tail -30)"
  fi
fi
exit 0
