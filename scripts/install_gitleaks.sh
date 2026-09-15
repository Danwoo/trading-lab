#!/usr/bin/env bash
# gitleaks 를 `$RUNNER_TEMP` 에 내려받는다 — **훅과 같은 판본임을 스스로 증명한다.**
#
# 버전과 해시를 이 파일 하나에 둔다. 스텝마다 적으면 한쪽만 올라가 조용히 갈리는데, 그 갈림은
# 「훅과 같은 버전」이라는 근거 자체를 지운다. `.pre-commit-config.yaml` 의 rev 와 대조해
# 어긋나면 실패한다.
#
# 바이너리는 작업 트리 밖(`$RUNNER_TEMP`)에 푼다 — 트리에 두면 스캔 대상에 자기 자신이 섞인다.
set -euo pipefail

GITLEAKS_VERSION="8.21.2"
GITLEAKS_SHA256="5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba"

HOOK_REV=$(sed -n '/gitleaks\/gitleaks/,+3{s/^[[:space:]]*rev:[[:space:]]*v\{0,1\}//p;}' .pre-commit-config.yaml | head -1)
if [ -z "$HOOK_REV" ]; then
  echo "::error::.pre-commit-config.yaml 에서 gitleaks rev 를 못 읽었습니다 — 훅과 같은 버전이라는 근거가 사라집니다"
  exit 1
fi
if [ "$HOOK_REV" != "$GITLEAKS_VERSION" ]; then
  echo "::error::훅의 gitleaks v${HOOK_REV} 와 이 스크립트의 ${GITLEAKS_VERSION} 이 어긋납니다 — 버전과 GITLEAKS_SHA256 을 함께 올리세요"
  exit 1
fi

if [ -x "${RUNNER_TEMP}/gitleaks" ]; then
  echo "gitleaks ${GITLEAKS_VERSION} (훅 rev 와 일치) — 이미 받아 둔 것을 쓴다"
  exit 0
fi

# `--retry` — self-hosted 러너의 일시 네트워크 오류로 이 단계가 죽었다
# (2026-08-25 실측: `curl: (35) Recv failure: Connection reset by peer`).
# 무결성은 아래 sha256 대조가 지키므로 재시도는 안전하다.
curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors \
  -o "$RUNNER_TEMP/gitleaks.tar.gz" \
  "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
echo "${GITLEAKS_SHA256}  $RUNNER_TEMP/gitleaks.tar.gz" | sha256sum -c -
tar xzf "$RUNNER_TEMP/gitleaks.tar.gz" -C "$RUNNER_TEMP" gitleaks
echo "gitleaks ${GITLEAKS_VERSION} (훅 rev 와 일치) 준비됨"
