import { describe, expect, it } from "vitest";

import { Action, INITIAL, researchChatReducer, State } from "@/components/features/ResearchChat/researchChatReducer";
import { ResearchSource } from "@/schemas/researchChat/researchChat";

// #173 — 컨테이너에서 분리한 순수 reducer 의 불변식 그물.
// 스트리밍 도중 끊김·중복 클릭·세션 삭제는 화면에서 재현하기 번거롭지만 여기서는 액션 나열로 고정된다.

const SOURCE: ResearchSource = {
  title: "리서치 리포트.pdf",
  tool: "doc_search_topic_workspace",
  url: "",
  domain: "사내 리서치자료",
  content: "목표주가 산정 근거",
  thumbnail: "",
  favicon: "",
};

/** 액션을 순서대로 적용한 최종 상태. */
function run(actions: Action[], initial: State = INITIAL): State {
  return actions.reduce(researchChatReducer, initial);
}

/** 질문 1건이 오간 세션 하나를 만든다 (gid 고정). */
function sessionWithAnswer(gid = 1, answer = "부분 답변"): State {
  return run([
    { type: "NEW_SESSION", gid },
    { type: "APPEND_USER_MSG", gid, text: "목표주가 근거를 알려줘" },
    { type: "START_ASSISTANT_MSG", gid },
    { type: "APPEND_DELTA", gid, text: answer },
  ]);
}

describe("researchChatReducer — 세션 목록", () => {
  it("NEW_SESSION 은 새 세션을 맨 앞에 넣고 활성으로 만든다", () => {
    const state = run([
      { type: "NEW_SESSION", gid: 1 },
      { type: "NEW_SESSION", gid: 2 },
    ]);
    expect(state.sessions.map((s) => s.gid)).toEqual([2, 1]);
    expect(state.activeGid).toBe(2);
  });

  // Date.now() 로 gid 를 만들기 때문에 같은 ms 안에 두 번 눌리면 gid 가 겹친다.
  it("같은 gid 로 NEW_SESSION 이 또 오면 세션을 새로 만들지 않고 활성만 옮긴다", () => {
    const state = run([
      { type: "NEW_SESSION", gid: 1 },
      { type: "NEW_SESSION", gid: 2 },
      { type: "NEW_SESSION", gid: 1 },
    ]);
    expect(state.sessions.map((s) => s.gid)).toEqual([2, 1]);
    expect(state.activeGid).toBe(1);
  });

  it("활성 세션을 지우면 남은 첫 세션이 활성이 되고, 다 지우면 null", () => {
    const two = run([
      { type: "NEW_SESSION", gid: 1 },
      { type: "NEW_SESSION", gid: 2 },
    ]);
    const afterFirst = researchChatReducer(two, { type: "DELETE_SESSION", gid: 2 });
    expect(afterFirst.activeGid).toBe(1);
    expect(researchChatReducer(afterFirst, { type: "DELETE_SESSION", gid: 1 }).activeGid).toBeNull();
  });

  it("비활성 세션을 지워도 활성 세션은 그대로다", () => {
    const state = run([
      { type: "NEW_SESSION", gid: 1 },
      { type: "NEW_SESSION", gid: 2 },
      { type: "DELETE_SESSION", gid: 1 },
    ]);
    expect(state.activeGid).toBe(2);
    expect(state.sessions.map((s) => s.gid)).toEqual([2]);
  });
});

describe("researchChatReducer — 스트리밍 누적", () => {
  it("APPEND_DELTA 는 마지막 assistant 메시지에 이어 붙인다", () => {
    const state = run(
      [
        { type: "APPEND_DELTA", gid: 1, text: "이어붙임" },
        { type: "SET_SOURCES", gid: 1, sources: [SOURCE] },
        { type: "SET_FOLLOWUPS", gid: 1, followUps: ["다음 질문"] },
      ],
      sessionWithAnswer(1, "앞부분 "),
    );
    const last = state.sessions[0].messages.at(-1);
    expect(last?.content).toBe("앞부분 이어붙임");
    expect(last?.sources).toEqual([SOURCE]);
    expect(last?.followUps).toEqual(["다음 질문"]);
  });

  it("다른 세션의 gid 로 온 델타는 어느 세션도 건드리지 않는다", () => {
    const before = sessionWithAnswer(1, "원문");
    const after = researchChatReducer(before, { type: "APPEND_DELTA", gid: 999, text: "침범" });
    expect(after.sessions[0].messages.at(-1)?.content).toBe("원문");
  });

  it("이전 상태를 변형하지 않는다 (불변 갱신)", () => {
    const before = sessionWithAnswer(1, "원문");
    const snapshot = JSON.parse(JSON.stringify(before));
    researchChatReducer(before, { type: "APPEND_DELTA", gid: 1, text: "추가" });
    expect(before).toEqual(snapshot);
  });
});

describe("researchChatReducer — 종료·중단", () => {
  it("END_ASSISTANT_MSG 는 제목이 없을 때만 첫 질문 앞 40자로 채운다", () => {
    const longQuestion = "가".repeat(50);
    const state = run([
      { type: "NEW_SESSION", gid: 1 },
      { type: "APPEND_USER_MSG", gid: 1, text: longQuestion },
      { type: "START_ASSISTANT_MSG", gid: 1 },
      { type: "END_ASSISTANT_MSG", gid: 1 },
    ]);
    expect(state.sessions[0].title).toBe(longQuestion.slice(0, 40));

    const titled = run([{ type: "END_ASSISTANT_MSG", gid: 1 }], {
      ...state,
      sessions: [{ ...state.sessions[0], title: "백엔드가 준 제목" }],
    });
    expect(titled.sessions[0].title).toBe("백엔드가 준 제목");
  });

  it("중단 시 부분 답변은 남기고 빈 말풍선만 지운다", () => {
    const partial = researchChatReducer(sessionWithAnswer(1, "여기까지 왔다"), {
      type: "ABORT_ASSISTANT_MSG",
      gid: 1,
    });
    expect(partial.sessions[0].messages.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(partial.sessions[0].messages.at(-1)?.content).toBe("여기까지 왔다");

    const empty = run([
      { type: "NEW_SESSION", gid: 1 },
      { type: "APPEND_USER_MSG", gid: 1, text: "질문" },
      { type: "START_ASSISTANT_MSG", gid: 1 },
      { type: "ABORT_ASSISTANT_MSG", gid: 1 },
    ]);
    expect(empty.sessions[0].messages.map((m) => m.role)).toEqual(["user"]);
  });

  // 본문 없이 근거만 온 상태에서 끊기면(도구는 돌았고 생성만 못 한 경우) 근거를 버리지 않는다.
  it("본문이 비어도 근거가 있으면 말풍선을 지우지 않는다", () => {
    const state = run([
      { type: "NEW_SESSION", gid: 1 },
      { type: "APPEND_USER_MSG", gid: 1, text: "질문" },
      { type: "START_ASSISTANT_MSG", gid: 1 },
      { type: "SET_SOURCES", gid: 1, sources: [SOURCE] },
      { type: "ABORT_ASSISTANT_MSG", gid: 1 },
    ]);
    expect(state.sessions[0].messages.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(state.sessions[0].messages.at(-1)?.sources).toEqual([SOURCE]);
  });

  it("공백뿐인 답변은 내용 없음으로 보고 지운다", () => {
    const state = researchChatReducer(sessionWithAnswer(1, "   \n  "), { type: "ABORT_ASSISTANT_MSG", gid: 1 });
    expect(state.sessions[0].messages.map((m) => m.role)).toEqual(["user"]);
  });
});

describe("researchChatReducer — 복원", () => {
  it("HYDRATE 는 저장된 상태로 통째 교체한다", () => {
    const saved = sessionWithAnswer(7, "저장된 답변");
    expect(researchChatReducer(INITIAL, { type: "HYDRATE", state: saved })).toEqual(saved);
  });

  it("모르는 액션은 상태를 그대로 둔다", () => {
    const before = sessionWithAnswer(1);
    expect(researchChatReducer(before, { type: "UNKNOWN" } as unknown as Action)).toBe(before);
  });
});
