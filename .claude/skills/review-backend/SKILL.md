---
description: Run backend pattern review (invokes review-backend agent)
argument-hint: "[--all|--diff]"
disable-model-invocation: true
---

review-backend 에이전트를 사용해서 백엔드 코드의 Anti-pattern 위반을 검토해줘.

옵션: $ARGUMENTS

- 인자 없음 또는 `--all` → 전체 검사 (default). backend 2개 이상이면 어느 backend 들을 검토할지 multiSelect ask.
- `--diff` → 변경분만 검토 (staged + M + U). 변경분 0건이면 "변경분 없음" 보고만 하고 종료. backend 가 여러 개여도 변경분 있는 곳 모두 자동 검토.
