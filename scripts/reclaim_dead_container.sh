#!/usr/bin/env bash
# 이름만 잡고 죽어 있는 컨테이너를 걷어낸다 — **돌고 있는 것은 건드리지 않는다**.
#
# `docker run --rm --name <이름>` 의 `--rm` 은 **정상 종료 때만** 지운다. 비정상 종료(255)나
# 도커 데몬 재시작으로 남은 컨테이너가 있으면 그 이름이 영영 잡혀 있어, 다음 기동이
# `Conflict. The container name ... is already in use` 로 죽는다. 사용자가 보는 것은 그
# 메시지뿐이고 「지우면 됩니다」는 어디에도 없다 (실측: 2주 전 죽은 `fintech-pg` 하나가
# 스택 전체를 막았다 — #452 A-1).
#
# **돌고 있는 것을 지우지 않는 이유**는 이 레포가 이미 값을 치른 규율이다 — 종전 `fuser -k`
# 가 "그 포트를 쓰는 게 내 이전 인스턴스인지 남의 프로세스인지" 가리지 않아 다른 프로젝트
# 컨테이너를 죽였다 (#308, `process-compose.yaml` 의 그 주석). 같은 실수를 이름으로 반복하지
# 않는다: **죽은 것만 걷어내고, 살아 있으면 사유를 말하고 멈춘다.**
#
# 데이터는 named volume 에 있으므로 컨테이너를 지워도 없어지지 않는다.
#
#   scripts/reclaim_dead_container.sh fintech-pg
#
# `DOCKER_BIN` 으로 도커 명령을 바꿔 끼울 수 있다 (그물이 이 자리를 쓴다).
set -euo pipefail

NAME=${1:-}
if [ -z "$NAME" ]; then
  echo "사용법: reclaim_dead_container.sh <컨테이너 이름>" >&2
  exit 2
fi

DOCKER=${DOCKER_BIN:-docker}

# 이름이 **정확히** 같은 것만 본다 — `--filter name=` 는 부분 일치라 `fintech-pg-backup` 까지
# 걸린다. 남의 컨테이너를 지우는 길을 열어 두지 않는다.
STATE=$("$DOCKER" inspect --format '{{.State.Running}}' "$NAME" 2>/dev/null || true)

case "$STATE" in
  "")
    # 그런 이름이 없다 — 정상. 조용히 지나간다.
    exit 0
    ;;
  true)
    echo "이미 같은 이름의 컨테이너가 돌고 있습니다: $NAME" >&2
    echo "  스택이 이미 떠 있는 것일 수 있습니다. 확인: docker ps --filter name=$NAME" >&2
    echo "  내리려면: process-compose down (또는 그 컨테이너를 쓰는 쪽을 먼저 멈추세요)" >&2
    echo "  돌고 있는 컨테이너는 이 스크립트가 지우지 않습니다 — 남의 것일 수 있기 때문입니다 (#308)." >&2
    exit 1
    ;;
  false)
    echo "죽은 채 이름을 잡고 있던 컨테이너를 걷어냅니다: $NAME (데이터는 named volume 에 남습니다)"
    "$DOCKER" rm -f "$NAME" >/dev/null
    exit 0
    ;;
  *)
    echo "컨테이너 상태를 읽지 못했습니다: $NAME (docker inspect → [$STATE])" >&2
    echo "  무엇을 지우는지 모르므로 건드리지 않습니다." >&2
    exit 1
    ;;
esac
