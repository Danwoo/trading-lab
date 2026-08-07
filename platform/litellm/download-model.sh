#!/bin/bash

set -euo pipefail

pip install --quiet --no-cache-dir hf_transfer 2>/dev/null || true

MODEL_DIR="${MODEL_DIR:?MODEL_DIR must be set}"
MODEL_NAMES="${MODEL_NAMES:-${MODEL_NAME:-}}"  # 다중 또는 단일 지원

check_hf_login() {
    if [[ -n "${HF_TOKEN:-}" ]]; then
        return 0
    fi
    if ! hf auth whoami >/dev/null 2>&1; then
        echo "ERROR: HF_TOKEN 환경변수 또는 hf auth login 필요"
        exit 1
    fi
}

get_remote_size_mb() {
    local model_name=$1
    python3 -c "
from huggingface_hub import HfApi
try:
    api = HfApi()
    model_info = api.model_info(repo_id='$model_name', files_metadata=True)
    total_size = sum(sibling.size for sibling in model_info.siblings if sibling.size)
    print(int(total_size / (1024 * 1024)))
except:
    print('0')
"
}

show_local_size() {
    local model_path=$1
    if [[ -d "$model_path" ]]; then
        local size_mb=$(($(du -sk "$model_path" | cut -f1) / 1024))
        echo "로컬 크기: ${size_mb}MB"
    else
        echo "로컬 크기: 0MB"
    fi
}

monitor_download_progress() {
    local model_path=$1
    local total_size_mb=$2
    local model_name=$3

    while true; do
        local timestamp=$(TZ='Asia/Seoul' date '+%Y-%m-%d %H:%M:%S')

        if [[ -d "$model_path" ]]; then
            local current_mb=$(($(du -sk "$model_path" 2>/dev/null | cut -f1) / 1024))

            if [[ "$total_size_mb" != "0" ]]; then
                local percent=$((current_mb * 100 / total_size_mb))
                echo "[$timestamp][$model_name] >>> ${current_mb}MB / ${total_size_mb}MB (${percent}%)"
            else
                echo "[$timestamp][$model_name] >>> ${current_mb}MB"
            fi
        else
            echo "[$timestamp][$model_name] >>> 대기중"
        fi

        sleep 60
    done
}

download_model() {
    local model_name=$1
    local model_path="${MODEL_DIR}/${model_name}"

    echo "=================================="
    echo "모델: ${model_name}"
    local total_size_mb=$(get_remote_size_mb "$model_name")
    echo "예상 크기: ${total_size_mb}MB"
    echo "=================================="

    if [[ -f "$model_path/README.md" ]]; then
        echo "INFO: 이미 다운로드 완료된 모델입니다."
        show_local_size "$model_path"
        return 0
    fi

    mkdir -p "$model_path"

    echo "INFO: 다운로드 시작..."

    monitor_download_progress "$model_path" "$total_size_mb" "$model_name" &
    local monitor_pid=$!
    trap "kill $monitor_pid 2>/dev/null" EXIT

    export HF_HUB_ENABLE_HF_TRANSFER=1
    huggingface-cli download "$model_name" \
        --local-dir "$model_path" --local-dir-use-symlinks false --exclude "README.md"

    kill $monitor_pid 2>/dev/null
    trap - EXIT

    echo "INFO: 완료 마커(README.md) 다운로드..."
    huggingface-cli download "$model_name" \
        "README.md" --local-dir "$model_path" --local-dir-use-symlinks false

    echo "SUCCESS: 다운로드 완료"
    show_local_size "$model_path"
    echo "=================================="
}

# === 메인 ===
mkdir -p "$MODEL_DIR"
check_hf_login

if [[ -z "$MODEL_NAMES" ]]; then
    echo "INFO: 다운로드할 모델 없음 (MODEL_NAMES 또는 MODEL_NAME 미설정)"
    exit 0
fi

# 콤마로 구분된 모델들 순차 다운로드
IFS=',' read -ra MODELS <<< "$MODEL_NAMES"
for model in "${MODELS[@]}"; do
    # 공백 제거
    model=$(echo "$model" | xargs)
    if [[ -n "$model" ]]; then
        download_model "$model"
    fi
done

echo "=== 모든 다운로드 완료 ==="
