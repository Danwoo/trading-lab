import { BotWorkbench } from "@/components/features/Bot/BotWorkbench";

/** 저장한 봇을 다시 연다 — 그때 조건이 폼에 그대로 보이는 것이 마일스톤 2 의 완료 조건이다. */
export default async function Page({ params }: { params: Promise<{ botId: string }> }) {
  const { botId } = await params;
  return <BotWorkbench botId={Number(botId)} />;
}
