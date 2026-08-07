"""LiteLLM custom guardrails — config.yaml 의 guardrails 섹션에서 `파일명.클래스명` 으로 지정.

  CanaryInjectGuard (pre_call)  : 모든 요청 system 에 canary 주입 (SafetyGuard 누설탐지의 전제).
  PiiMaskGuard      (pre_call)  : 입력에서 고민감 PII만 마스킹 (주민/카드/계좌). 전화·이메일·사업자·우편·이름·주소는 통과.
  SafetyGuard       (post_call) : 출력에서 canary 누설=차단(거부문구), 욕설=마스킹.
                                  비스트리밍·스트리밍 동일 정책.

각 가드레일 litellm_params 에 `models: [...]` 선언 시 해당 모델만 적용, 생략 시 전체.

의존성 (라이선스):
    pip install korcen           # 한국어 욕설 마스킹 (level='general'). MIT
    # 영어 욕설(korcen level='english'/'all')을 쓰려면 better-profanity 추가 설치.

정밀 PII 가 필요하면 Presidio 로 교체 권장.
"""

import logging
import os
import re
import secrets
from typing import Any, AsyncGenerator

import litellm
from korcen import korcen  # type: ignore
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.proxy._types import UserAPIKeyAuth
from litellm.types.utils import ModelResponseStream

_guard_log = logging.getLogger("guardrail")


def _log_block(msg: str) -> None:
    """차단 시 warning 로그를 기록."""
    _guard_log.warning("[GUARD BLOCK] %s", msg)


# --- 설정 (환경변수) ---
# 미지정 시 프로세스 기동마다 랜덤 생성 (배포별 고유 — repo 박힌 상수 노출 회피).
# 멀티워커여도 주입(pre)·누설검사(post)는 동일 요청=동일 워커라 같은 값을 본다.
PROMPT_CANARY = os.environ.get("PROMPT_CANARY") or f"__CANARY_{secrets.token_hex(6)}__"
# 누설 탐지 시 출력 거부 문구 (도메인 중립 — 프로젝트별 env 교체).
REFUSAL = os.environ.get("GUARDRAIL_REFUSAL", "요청하신 내용은 제공할 수 없습니다.")

# --- 출력 필터 상수 ---
_PROFANITY_MASK = "[부적절한 표현]"
_PROFANITY_MARK = "\x00"  # 정상 텍스트엔 안 나오는 sentinel
_PROFANITY_RE = re.compile(r"\x00.+?\x00")

# --- 스트리밍 가드 상수 ---
_HOLDBACK = 80  # hold-back 보류 길이 (방출 전에 canary 검사 완료가 확정될 때까지 토큰을 쌓아둔다)
_WS = re.compile(r"\s+")
_KEEP = object()  # _clone_chunk 가 finish_reason 을 건드리지 않음 sentinel


def _normalize(s: str) -> str:
    """공백 제거 + 소문자."""
    return _WS.sub("", s or "").lower()


def _content_text(content) -> str:
    """누설 검사용 — str content 또는 멀티모달 text 파트들을 단일 문자열로. 그 외 타입=빈 문자열."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            p["text"]
            for p in content
            if isinstance(p, dict)
            and p.get("type") == "text"
            and isinstance(p.get("text"), str)
        )
    return ""


def _map_text_parts(content, fn):
    """str 이면 fn 결과를 반환, 멀티모달 list 면 각 text 파트를 fn 으로 in-place 치환 후 같은 list 반환.
    그 외 타입(이미지·오디오·None)은 손대지 않음."""
    if isinstance(content, str):
        return fn(content)
    if isinstance(content, list):
        for p in content:
            if (
                isinstance(p, dict)
                and p.get("type") == "text"
                and isinstance(p.get("text"), str)
            ):
                p["text"] = fn(p["text"])
    return content


def _resolve_scope(models) -> set:
    """가드레일 적용 모델 집합 (config.yaml `models:`, LiteLLM 이 kwargs 전달). 비면 전체."""
    return {str(m).strip() for m in (models or []) if str(m).strip()}


def _in_scope(scope: set, data: dict) -> bool:
    """scope 가 비면 전체(True), 아니면 요청 모델이 scope 에 있을 때만."""
    return not scope or (data or {}).get("model") in scope


# === CanaryInjectGuard (pre_call) — 모든 요청 system 에 canary 주입 ===
class CanaryInjectGuard(CustomGuardrail):
    def __init__(self, **kwargs):
        self._scope = _resolve_scope(kwargs.pop("models", None))
        super().__init__(**kwargs)

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if not PROMPT_CANARY or not _in_scope(self._scope, data):
            return data
        msgs = data.get("messages") or []
        # 앞에 주입 — verbatim 덤프 시 canary 가 먼저 재현돼 스트리밍에서도 본문 방출 전 검출.
        for m in msgs:
            if m.get("role") != "system":
                continue
            c = m.get("content")
            if isinstance(c, str):
                if PROMPT_CANARY not in c:
                    m["content"] = f"{PROMPT_CANARY}\n\n{c}"
                data["messages"] = msgs
                return data
            if isinstance(c, list):  # 멀티모달 system — text 파트로 맨 앞에 주입
                if PROMPT_CANARY not in _content_text(c):
                    c.insert(0, {"type": "text", "text": PROMPT_CANARY})
                data["messages"] = msgs
                return data
        msgs.insert(0, {"role": "system", "content": PROMPT_CANARY})
        data["messages"] = msgs
        return data


# === PiiMaskGuard (pre_call) — 고민감 식별정보만 마스킹, 전화·이메일·사업자·우편번호는 통과 ===
class PiiMaskGuard(CustomGuardrail):
    MASK_PATTERNS = {
        "[주민번호]": r"\b\d{6}-?\d{7}\b",
        "[카드번호]": r"\b(?:\d{4}[- ]?){3}\d{4}\b",
        "[계좌번호]": r"\b\d{2,3}-\d{2,6}-\d{2,6}\b",
    }
    # 절대 마스킹 안 함 — 다른 패턴이 먼저 삼키지 못하게 빼둔다. 우편번호(숫자만)는 어떤 패턴에도 안 걸림.
    KEEP_RE = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"  # 이메일 (주민번호 무하이픈이 숫자 local 삼키는 것 방지)
        r"|\b01\d-?\d{3,4}-?\d{4}\b"  # 휴대폰
        r"|\b0\d{1,2}-?\d{3,4}-?\d{4}\b"  # 유선전화
        r"|\b\d{3}-\d{2}-\d{5}\b"  # 사업자등록번호 (계좌와 형태 유사 → 오탐 방지)
    )

    def __init__(self, **kwargs):
        self._scope = _resolve_scope(kwargs.pop("models", None))
        super().__init__(**kwargs)

    def _mask_pii(self, text: str) -> str:
        # 전화·사업자번호를 placeholder 로 빼두고(계좌 정규식 오탐 방지) 마스킹 후 원복.
        kept = []

        def _stash(mt):
            kept.append(mt.group(0))
            return f"\x00KEEP{len(kept) - 1}\x00"

        text = self.KEEP_RE.sub(_stash, text)
        for repl, pat in self.MASK_PATTERNS.items():
            text = re.sub(pat, repl, text)
        for i, p in enumerate(kept):
            text = text.replace(f"\x00KEEP{i}\x00", p)
        return text

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if not _in_scope(self._scope, data):
            return data
        for m in data.get("messages") or []:
            c = m.get("content")
            if isinstance(c, (str, list)):
                m["content"] = _map_text_parts(c, self._mask_pii)
        return data


# === SafetyGuard (post_call) — canary 누설 차단 + 욕설 마스킹 ===
class SafetyGuard(CustomGuardrail):
    def __init__(self, **kwargs):
        self._scope = _resolve_scope(kwargs.pop("models", None))
        super().__init__(**kwargs)

    async def async_post_call_success_hook(
        self, data, user_api_key_dict: UserAPIKeyAuth, response
    ):
        """비스트리밍: 전체 응답 조립 후 canary 검사, 욕설 처리."""
        if not isinstance(response, litellm.ModelResponse) or not _in_scope(
            self._scope, data
        ):
            return response
        canary_norm = _normalize(PROMPT_CANARY)
        for choice in response.choices:
            msg = getattr(choice, "message", None)
            content = getattr(msg, "content", None)
            text = _content_text(content)
            if not text:
                continue
            if self._is_leak(text, canary_norm):
                msg.content = REFUSAL
            else:
                msg.content = _map_text_parts(content, self._mask_profanity)
        return response

    async def async_post_call_streaming_iterator_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        response: Any,
        request_data: dict,
    ) -> AsyncGenerator[ModelResponseStream, None]:
        """스트리밍: hold-back 으로 토큰 흐름 중 canary 검사 — 누설=거부문구 대체 후 종료, 그 외 prefix 욕설 처리."""
        if not _in_scope(self._scope, request_data):
            async for item in response:
                yield item
            return
        canary_norm = _normalize(PROMPT_CANARY)
        full_out = ""
        emitted = 0  # 이미 방출한 글자 수 (hold-back 경계)
        last = None

        async for item in response:
            last = item
            choices = getattr(item, "choices", None)
            if not choices:  # usage-only 등
                yield item
                continue
            ch0 = choices[0]
            delta = getattr(ch0, "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if not isinstance(content, str):  # 멀티모달/비텍스트 델타는 그대로 통과
                content = None
            finish = getattr(ch0, "finish_reason", None)

            if content:
                full_out += content
                if self._is_leak(full_out, canary_norm):
                    yield self._clone_chunk(item, REFUSAL, finish_reason="stop")
                    return

            if content is None and finish is None:  # role-only/빈 chunk
                yield item
                continue

            # 종료 chunk 면 보류분까지, 아니면 hold-back 만큼 말미 보류
            safe_end = (
                len(full_out)
                if finish is not None
                else max(0, len(full_out) - _HOLDBACK)
            )
            out_text = ""
            if safe_end > emitted:
                out_text = self._mask_profanity(full_out[emitted:safe_end])
                emitted = safe_end

            if finish is not None:  # 종료 chunk: finish_reason 보존하며 보류분 방출
                yield self._clone_chunk(item, out_text)
            elif out_text:  # 확정된 안전 prefix 만 방출
                yield self._clone_chunk(item, out_text)

        # finish_reason 없이 끝난 방어 — 마지막 chunk 메타로 보류분 flush
        if emitted < len(full_out) and last is not None:
            yield self._clone_chunk(
                last,
                self._mask_profanity(full_out[emitted:]),
                finish_reason="stop",
            )

    @staticmethod
    def _is_leak(out: str, canary_norm: str) -> bool:
        """출력에 canary 누설이 있는지 확인."""
        norm = _normalize(out)
        if canary_norm and canary_norm in norm:
            _log_block(f"canary match. out[:200]={out[:200]}")
            return True
        return False

    @staticmethod
    def _mask_profanity(text: str) -> str:
        """욕설을 마스크 치환. level='general' 만 사용('all'은 일반 동사 false positive 유발).
        실패는 차단보다 통과가 안전(서비스 중단 회피)."""
        if not text:
            return text
        try:
            marked = korcen.highlight_profanity(
                text, level="general", highlight_char=_PROFANITY_MARK
            )
            return _PROFANITY_RE.sub(_PROFANITY_MASK, marked)
        except Exception:
            return text

    @staticmethod
    def _clone_chunk(
        template: ModelResponseStream, content: str, finish_reason=_KEEP
    ) -> ModelResponseStream:
        """chunk 복제 후 델타 content(및 선택적 finish_reason) 교체 — 메타(id/model/created) 보존."""
        try:
            c = template.model_copy(deep=True)
        except Exception:
            c = template
        try:
            c.choices[0].delta.content = content
            if finish_reason is not _KEEP:
                c.choices[0].finish_reason = finish_reason
        except Exception:
            pass
        return c
