---
description: Run frontend pattern review (invokes review-frontend agent)
argument-hint: "[--all|--diff]"
disable-model-invocation: true
---

review-frontend 에이전트를 사용해서 프론트엔드 코드의 Anti-pattern 위반을 검토해줘.

옵션: $ARGUMENTS

- 인자 없음 또는 `--all` → 전체 검사 (default, `frontend/` 전체 scan).
- `--diff` → 변경분만 검토 (staged + M + U). 변경분 0건이면 "변경분 없음" 보고만 하고 종료.
