import json
import random
import uuid
from config import MAX_DECISION_ROUNDS
from shared.models import MemoryType
from npc_agent.api_models import AddMemoryRequest
from event.api_models import NpcDecisionOutput, RoundResult
from npc_agent.memory_manager import NpcMemoryManager
from npc_agent.metadata_store import MetadataStore
from shared.llm_service import LlmService

SYSTEM_PROMPT = """你是游戏NPC决策引擎。输出简洁的总结性文字，不要写小说，不要描写细节动作和语言。

JSON格式：
{
  "action": "用一句话概括行为",
  "elapsed_seconds": 这个行为大概经过了多少秒（整数，如：推人=2秒，逃跑=10秒，打架=30秒）,
  "memory_note": "客观记录发生了什么，一句话",
  "new_event": null 或 {"description": "一句话描述", "location": "地点", "intensity": 1.0, "involved_npc_ids": ["..."]},
  "goal_changes": []
}

规则：
- action：一句话，只说做了什么
- elapsed_seconds：这个行为从发生到结束经历的秒数，要合理
- memory_note：一句话客观记录
- new_event：只有行为实质性改变局面时才填，口头行为一律null
- goal_changes：只记录长期人生目标变化（如"为父报仇"），不记录当场反应
- 所有文字尽量简短
"""


def _log(msg: str):
    print(f"[DecisionEngine] {msg}", flush=True)


class DecisionEngine:
    def __init__(
        self,
        memory_manager: NpcMemoryManager,
        metadata_store: MetadataStore,
        llm_service: LlmService,
    ):
        self._memory = memory_manager
        self._meta = metadata_store
        self._llm = llm_service

    def inject_event(self, description: str, location: str, intensity: float,
                     involved_npc_ids: list[str], game_time: int) -> list[RoundResult]:
        _log(f"========== 事件注入 ==========")
        _log(f"事件: {description}")
        _log(f"地点: {location} | 强度: {intensity} | 当事人: {involved_npc_ids}")

        rounds = []
        pending_events = [{
            "description": description,
            "location": location,
            "intensity": intensity,
            "involved_npc_ids": involved_npc_ids,
            "game_time": game_time,
        }]

        for round_num in range(1, MAX_DECISION_ROUNDS + 1):
            if not pending_events:
                _log(f"没有新事件，循环结束")
                break

            _log(f"\n---------- 第 {round_num} 轮 ----------")

            # 本轮所有事件的所有决策汇总
            all_decisions = []
            all_new_events = []
            decided_this_round = set()  # 每个 NPC 一轮只决策一次
            round_event_desc = "; ".join(e["description"] for e in pending_events)

            for event in pending_events:
                _log(f"\n事件: {event['description']}")

                affected_npcs = self._get_affected_npcs(
                    event["location"], event["intensity"], event["involved_npc_ids"]
                )
                if not affected_npcs:
                    _log(f"  没有受影响的 NPC")
                    continue

                involved = set(event.get("involved_npc_ids", []))
                bystanders = [nid for nid in affected_npcs if nid not in involved]
                _log(f"  当事人: {list(involved)} | 旁观者: {bystanders}")

                # 当事人写 affected 记忆
                gt = str(event["game_time"])
                for npc_id in involved:
                    if self._meta.get_npc(npc_id):
                        self._memory.add_memory(npc_id, AddMemoryRequest(
                            game_time=gt,
                            content=event["description"],
                            memory_type=MemoryType.AFFECTED,
                            location=event["location"],
                            related_npc_ids=list(involved),
                        ))

                # 旁观者写 witnessed 记忆
                for npc_id in bystanders:
                    self._memory.add_memory(npc_id, AddMemoryRequest(
                        game_time=gt,
                        content=event["description"],
                        memory_type=MemoryType.WITNESSED,
                        location=event["location"],
                        related_npc_ids=list(involved),
                    ))

                # 所有在场 NPC 同时决策（每个 NPC 本轮只决策一次）
                for npc_id in affected_npcs:
                    if npc_id in decided_this_round:
                        continue
                    npc = self._meta.get_npc(npc_id)
                    if not npc:
                        continue

                    decision, elapsed = self._decide_for_npc(npc, event)
                    if decision:
                        decided_this_round.add(npc_id)
                        all_decisions.append(decision)
                        new_time = event["game_time"] + elapsed
                        _log(f"  {npc['name']}({npc_id}): {decision.action} (+{elapsed}s → {new_time}s)")

                        new_event = self._process_decision(
                            npc_id, decision, new_time, event["location"]
                        )
                        if new_event:
                            _log(f"    → 新事件: {new_event['description']}")
                            all_new_events.append(new_event)

            if all_decisions:
                rounds.append(RoundResult(
                    round=round_num,
                    event_description=round_event_desc,
                    decisions=all_decisions,
                ))

            # 汇总本轮产生的新事件，进入下一轮
            pending_events = all_new_events
            _log(f"\n  本轮 {len(all_decisions)} 个决策，产生 {len(all_new_events)} 个新事件")

        _log(f"\n========== 决策循环结束，共 {len(rounds)} 轮 ==========\n")
        return rounds

    def _get_affected_npcs(self, location: str, intensity: float, involved_npc_ids: list[str]) -> list[str]:
        all_npcs = self._meta.list_npcs()
        same_location = [n["npc_id"] for n in all_npcs if n.get("location") == location]

        if intensity < 1.0 and same_location:
            count = max(1, int(len(same_location) * intensity))
            same_location = random.sample(same_location, min(count, len(same_location)))

        affected = list(set(same_location + [nid for nid in involved_npc_ids if self._meta.get_npc(nid)]))
        return affected

    def _decide_for_npc(self, npc: dict, event: dict) -> tuple[NpcDecisionOutput | None, int]:
        npc_id = npc["npc_id"]

        goals = self._meta.list_goals(npc_id, status="active")
        goals_text = "\n".join(f"- [{g['goal_type']}] {g['description']}（优先级{g['priority']}）" for g in goals)
        if not goals_text:
            goals_text = "（暂无目标）"

        memories = self._memory.search_memories(npc_id, event["description"], top_k=10)
        memories_text = "\n".join(
            f"- [{m.game_time}] ({m.memory_type}): {m.content}" for m in memories
        )
        if not memories_text:
            memories_text = "（没有相关记忆）"

        user_prompt = f"""## NPC信息
ID: {npc_id}
姓名: {npc['name']}
性格: {npc['personality']}
特征: {json.dumps(npc.get('traits', {}), ensure_ascii=False)}
当前位置: {npc.get('location', '未知')}

## 当前目标
{goals_text}

## 相关记忆
{memories_text}

## 当前发生的事件
时间: {event['game_time']}秒
地点: {event['location']}
事件: {event['description']}
相关人物: {', '.join(event.get('involved_npc_ids', []))}

请决定{npc['name']}的行为。"""


        try:
            result = self._llm.decide(SYSTEM_PROMPT, user_prompt)
            elapsed = int(result.get("elapsed_seconds", 5))

            new_events = []
            new_event = result.get("new_event")
            if new_event and isinstance(new_event, dict) and new_event.get("description"):
                new_events = [new_event]

            return NpcDecisionOutput(
                npc_id=npc_id,
                npc_name=npc["name"],
                action=result.get("action", "无反应"),
                memory_note=result.get("memory_note"),
                new_events=new_events,
                goal_changes=result.get("goal_changes", []),
            ), elapsed
        except Exception as e:
            _log(f"  ❌ LLM 决策失败: {e}")
            return None, 0

    def _process_decision(self, npc_id: str, decision: NpcDecisionOutput,
                          game_time: int, location: str) -> dict | None:
        # 写记忆
        if decision.memory_note:
            self._memory.add_memory(npc_id, AddMemoryRequest(
                game_time=str(game_time),
                content=decision.memory_note,
                memory_type=MemoryType.ACTION,
                location=location,
            ))

        # 处理目标变更
        for gc in decision.goal_changes:
            action = gc.get("action")
            if action == "add":
                goal_id = str(uuid.uuid4())[:8]
                self._meta.create_goal(
                    goal_id, npc_id,
                    gc.get("goal_type", "short_term"),
                    gc.get("description", ""),
                    gc.get("priority", 5),
                    game_time, None,
                )
                pass
            elif action in ("complete", "abandon"):
                goals = self._meta.list_goals(npc_id, status="active")
                for g in goals:
                    if gc.get("description", "") in g["description"]:
                        status = "completed" if action == "complete" else "abandoned"
                        self._meta.update_goal(g["goal_id"], status=status)
                        pass
                        break

        # 返回新事件（只有推动情节的才有）
        if decision.new_events:
            evt = decision.new_events[0]
            return {
                "description": evt.get("description", ""),
                "location": evt.get("location", location),
                "intensity": evt.get("intensity", 1.0),
                "involved_npc_ids": evt.get("involved_npc_ids", [npc_id]),
                "game_time": game_time,
            }
        return None
