import json
import os
from pathlib import Path

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text


class ChatHistoryRepository:
    """공통 DB `frontend.ai_chat_history` 멀티턴 히스토리 조회 + 각 턴 적재(#213).

    Prisma 소유 테이블이지만 지금까지 이 테이블에 쓰는 코드가 레포 전체에 없어(#213) 서버측
    히스토리가 항상 빈 배열이었다 — 매 질문이 단일턴으로 처리됐다. `insert_turn` 이 그 공백을
    메운다. 소유는 여전히 frontend(Prisma) 몫이다 — 여기서는 read/write 둘 다 LLM 멀티턴
    컨텍스트용 question/answer 만 다룬다(sources/images/followups 는 프론트 표시 전용이라
    여기서 적재하지 않는다 — 그 값들은 프론트가 SSE 이벤트로 직접 받아 자기 상태에 둔다).

    스키마 수식(`frontend.`)이 붙는 이유: DB(`fintech`)는 하나지만 소유를 스키마로 갈랐다 —
    파이썬 서비스는 `public`, Prisma 소유 테이블은 `frontend` (#166,
    .docs/5-인프라셋팅/로컬-postgres.md). 이 커넥션의 search_path 는 기본값(public)이라
    수식하지 않으면 테이블을 찾지 못한다.

    max_turns: 적재할 (question,answer) 쌍 상한 — 최근 N턴만 읽어 대화 길이와 무관하게
    메모리·토큰을 bound 한다 (무제한 로드 방지, #85).
    """

    def __init__(self, sql_client, max_turns: int = 10):
        self.sql_client = sql_client
        self.max_turns = max_turns

    def _select(self, email: str, gid: int) -> list[dict]:
        # dev 전용 로컬 폴백 — MULTI_AGENT_HISTORY_FILE 설정 시 공통 DB 대신 로컬 JSON 에서 읽음
        # (공통 DB 없이 멀티턴 검증용). production 은 env 미설정이라 아래 DB 경로.
        local = os.getenv("MULTI_AGENT_HISTORY_FILE")
        if local:
            p = Path(local)
            rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
            filtered = [
                {"question": r["question"], "answer": r["answer"]}
                for r in rows
                if r.get("email") == email and r.get("gid") == gid and r.get("flag", 1) == 1
            ]
            # DB 경로의 LIMIT 캡과 동일하게 최근 N턴만 (파일은 sort 순 저장 가정 → 꼬리 slice)
            return filtered[-self.max_turns :] if self.max_turns > 0 else filtered
        # 최근 N턴만: 안쪽에서 sort DESC 로 N건을 뽑고 바깥에서 sort ASC 로 시간순 복원.
        sql = text(
            "SELECT question, answer FROM ("
            "  SELECT question, answer, sort FROM frontend.ai_chat_history "
            "  WHERE email = :email AND gid = :gid AND flag = 1 "
            "  ORDER BY sort DESC LIMIT :limit"
            ") t ORDER BY t.sort ASC"
        )
        with self.sql_client.connect() as conn:
            rows = conn.execute(sql, {"email": email, "gid": gid, "limit": self.max_turns}).mappings().all()
        return [dict(r) for r in rows]

    async def select_history(self, email: str, gid: int) -> list[dict]:
        # psycopg sync → 이벤트루프 블로킹 방지 (anti-pattern 13)
        return await run_in_threadpool(self._select, email, gid)

    def _insert(self, email: str, gid: int, question: str, answer: str) -> None:
        # dev 전용 로컬 폴백 — _select 와 같은 스위치. 공통 DB 없이 멀티턴 검증할 때 왕복이 성립하게.
        local = os.getenv("MULTI_AGENT_HISTORY_FILE")
        if local:
            p = Path(local)
            rows = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
            rows.append({"email": email, "gid": gid, "question": question, "answer": answer, "flag": 1})
            p.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            return
        # sort 는 유니크 제약이 없다(테이블 원 설계 그대로 — 새 제약을 이 변경에서 얹지 않는다).
        # 같은 (email,gid) 로 동시 두 턴이 겹치면 sort 가 같은 값으로 남을 수 있으나(드묾, 사용자
        # 하나가 같은 대화에 동시에 두 질문을 보내는 경우뿐), id(PK) 로 항상 안정적 전순서가 있어
        # 표시가 깨지지는 않는다.
        #
        # next_sort 를 INSERT 문 안 서브쿼리로 넣지 않고 별도 SELECT 로 미리 구한다 — 같은 바인드
        # 이름(:email/:gid)을 VALUES 절과 서브쿼리 WHERE 절에 함께 쓰면 psycopg3 확장 프로토콜이
        # "text versus character varying" AmbiguousParameter 로 거부한다(실측, 컬럼 타입 추론이
        # 두 문맥에서 갈린다) — 트랜잭션 안에서 두 문으로 나누면 원자성은 유지하면서 이 충돌을 피한다.
        next_sort_sql = text(
            "SELECT COALESCE(MAX(sort), 0) + 1 FROM frontend.ai_chat_history WHERE email = :email AND gid = :gid"
        )
        insert_sql = text(
            "INSERT INTO frontend.ai_chat_history "
            "(email, gid, sort, question, answer, flag, reg_dt, reg_id, mod_dt, mod_id) "
            "VALUES (:email, :gid, :sort, :question, :answer, 1, now(), :reg_id, now(), :reg_id)"
        )
        with self.sql_client.connect() as conn:
            with conn.begin():
                next_sort = conn.execute(next_sort_sql, {"email": email, "gid": gid}).scalar()
                conn.execute(
                    insert_sql,
                    {
                        "email": email,
                        "gid": gid,
                        "sort": next_sort,
                        "question": question,
                        "answer": answer,
                        "reg_id": email,
                    },
                )

    async def insert_turn(self, email: str, gid: int, question: str, answer: str) -> None:
        """이번 턴(질문+답변)을 적재한다. answer 는 스트리밍 중단 시 빈 문자열일 수 있다(테이블 주석과 동일 전제)."""
        # psycopg sync → 이벤트루프 블로킹 방지 (anti-pattern 13)
        await run_in_threadpool(self._insert, email, gid, question, answer)
