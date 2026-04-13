import json
import random
import uuid
from typing import Optional
from config import MAX_DECISION_ROUNDS
from shared.models import MemoryType
from npc_agent.api_models import AddMemoryRequest
from event.api_models import NpcDecisionOutput, RoundResult, PresetEvent
from npc_agent.memory_manager import NpcMemoryManager
from npc_agent.metadata_store import MetadataStore
from shared.llm_service import LlmService

SYSTEM_PROMPT = """你是游戏NPC决策引擎。根据NPC的性格、目标、记忆、当前场景，决定NPC的下一步行为。输出简洁的总结性文字，不要写小说。

JSON格式：
{
  "action": "用一句话概括行为",
  "elapsed_seconds": 这个行为经过多少秒（整数），
  "memory_note": "客观记录，一句话",
  "new_event": null 或 {"description": "一句话描述", "affected_npc_ids": ["被影响NPC的ID"]},
  "goal_changes": []
}

规则：
- action：一句话，只说做了什么
- elapsed_seconds：整数秒，合理即可（推人2，逃跑10，打架30）
- new_event：只有行为实质性改变局面时才填（动手、逃跑找援军），口头行为一律null
- affected_npc_ids：**必须使用 NPC 的 ID（如 a、b、c），不要使用中文名字**。这个行为直接影响到的NPC ID列表，没有就空数组
- goal_changes：只记录长期人生目标变化（如"为父报仇"），不记录当场反应
- 文字尽量简短
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

    # ── 公共入口 ──

    def simulate_scene(
        self,
        description: str,
        location: str,
        characters: list[str],
        intensity: float,
        game_time: int,
        preset_event: Optional[PresetEvent] = None,
    ) -> list[RoundResult]:
        _log(f"========== 场景推演 ==========")
        _log(f"场景: {description}")
        _log(f"地点: {location} | 主要人物: {characters}")
        if preset_event:
            _log(f"预设事件: {preset_event.description} (actor={preset_event.actor_npc_id}, affected={preset_event.affected_npc_ids})")

        rounds = []
        affected_npcs = self._get_scene_npcs(location, intensity, characters)

        if preset_event:
            # 分支 B：预设事件 — 直接写记忆，然后决策反应
            self._write_event_memories(
                event_description=preset_event.description,
                location=location,
                game_time=game_time,
                actor_npc_id=preset_event.actor_npc_id,
                affected_npc_ids=preset_event.affected_npc_ids,
                in_scene_npcs=affected_npcs,
            )
            # 塞入 pending，进入循环。actor 本轮不再重复决策
            pending_events = [{
                "description": preset_event.description,
                "location": location,
                "intensity": intensity,
                "actor_npc_id": preset_event.actor_npc_id,
                "affected_npc_ids": preset_event.affected_npc_ids,
                "game_time": game_time,
                "scene_context": description,
                "skip_actor_decision": True,
            }]
        else:
            # 分支 A：纯场景 — 每个 NPC 根据场景背景自行决策
            pending_events = [{
                "description": "",  # 没有当前事件
                "location": location,
                "intensity": intensity,
                "actor_npc_id": None,
                "affected_npc_ids": [],
                "game_time": game_time,
                "scene_context": description,
                "is_scene_init": True,
                "initial_npcs": affected_npcs,  # 初始决策的 NPC
            }]

        self._run_decision_loop(pending_events, rounds)
        _log(f"\n========== 场景推演结束，共 {len(rounds)} 轮 ==========\n")
        return rounds

    # ── 决策循环 ──

    def _run_decision_loop(self, pending_events: list[dict], rounds: list[RoundResult]):
        for round_num in range(1, MAX_DECISION_ROUNDS + 1):
            if not pending_events:
                _log(f"没有新事件，循环结束")
                break

            _log(f"\n---------- 第 {round_num} 轮 ----------")

            all_decisions = []
            all_new_events = []
            decided_this_round = set()
            round_event_desc = "; ".join(
                e.get("description") or e.get("scene_context", "")[:40] for e in pending_events
            )

            for event in pending_events:
                desc = event.get("description") or "(场景起始)"
                _log(f"\n事件: {desc}")

                # 确定需要决策的 NPC 列表
                if event.get("is_scene_init"):
                    npcs_to_decide = event["initial_npcs"]
                    _log(f"  场景初始决策 NPC: {npcs_to_decide}")
                else:
                    scene_npcs = self._get_scene_npcs(
                        event["location"], event["intensity"],
                        [event["actor_npc_id"]] + event.get("affected_npc_ids", [])
                        if event.get("actor_npc_id") else event.get("affected_npc_ids", []),
                    )
                    npcs_to_decide = scene_npcs
                    _log(f"  actor: {event.get('actor_npc_id')} | affected: {event.get('affected_npc_ids')} | 在场: {scene_npcs}")

                if not npcs_to_decide:
                    continue

                # 非场景初始化且非预设事件时，写入新事件的记忆（由 LLM 决策产生）
                if not event.get("is_scene_init") and not event.get("memories_written"):
                    self._write_event_memories(
                        event_description=event["description"],
                        location=event["location"],
                        game_time=event["game_time"],
                        actor_npc_id=event.get("actor_npc_id"),
                        affected_npc_ids=event.get("affected_npc_ids", []),
                        in_scene_npcs=npcs_to_decide,
                        skip_actor=True,  # actor 已通过 memory_note 写过 action 记忆，不重复
                    )

                # 决策
                for npc_id in npcs_to_decide:
                    if npc_id in decided_this_round:
                        continue
                    # 预设事件的 actor 本轮跳过决策
                    if event.get("skip_actor_decision") and npc_id == event.get("actor_npc_id"):
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

            pending_events = all_new_events
            _log(f"\n  本轮 {len(all_decisions)} 个决策，产生 {len(all_new_events)} 个新事件")

    # ── 辅助 ──

    def _get_scene_npcs(self, location: str, intensity: float, must_include: list[str]) -> list[str]:
        all_npcs = self._meta.list_npcs()
        same_location = [n["npc_id"] for n in all_npcs if n.get("location") == location]

        if intensity < 1.0 and same_location:
            count = max(1, int(len(same_location) * intensity))
            same_location = random.sample(same_location, min(count, len(same_location)))

        must_valid = [nid for nid in must_include if nid and self._meta.get_npc(nid)]
        return list(set(same_location + must_valid))

    def _write_event_memories(
        self,
        event_description: str,
        location: str,
        game_time: int,
        actor_npc_id: Optional[str],
        affected_npc_ids: list[str],
        in_scene_npcs: list[str],
        skip_actor: bool = False,
    ):
        """给一个事件写入记忆：actor → action, affected → affected, 其他在场 → witnessed"""
        gt = str(game_time)
        related = [nid for nid in ([actor_npc_id] if actor_npc_id else []) + affected_npc_ids if nid]

        # actor 写 action
        if actor_npc_id and not skip_actor and self._meta.get_npc(actor_npc_id):
            self._memory.add_memory(actor_npc_id, AddMemoryRequest(
                game_time=gt,
                content=event_description,
                memory_type=MemoryType.ACTION,
                location=location,
                related_npc_ids=related,
            ))

        # affected 写 affected
        for npc_id in affected_npc_ids:
            if self._meta.get_npc(npc_id):
                self._memory.add_memory(npc_id, AddMemoryRequest(
                    game_time=gt,
                    content=event_description,
                    memory_type=MemoryType.AFFECTED,
                    location=location,
                    related_npc_ids=related,
                ))

        # 其他在场者写 witnessed
        participants = set(related)
        bystanders = [nid for nid in in_scene_npcs if nid not in participants]
        for npc_id in bystanders:
            self._memory.add_memory(npc_id, AddMemoryRequest(
                game_time=gt,
                content=event_description,
                memory_type=MemoryType.WITNESSED,
                location=location,
                related_npc_ids=related,
            ))

    def _decide_for_npc(self, npc: dict, event: dict) -> tuple[NpcDecisionOutput | None, int]:
        npc_id = npc["npc_id"]

        goals = self._meta.list_goals(npc_id, status="active")
        goals_text = "\n".join(f"- [{g['goal_type']}] {g['description']}（优先级{g['priority']}）" for g in goals)
        if not goals_text:
            goals_text = "（暂无目标）"

        query = event.get("description") or event.get("scene_context", "")
        memories = self._memory.search_memories(npc_id, query, top_k=10)
        memories_text = "\n".join(
            f"- [{m.game_time}] ({m.memory_type}): {m.content}" for m in memories
        )
        if not memories_text:
            memories_text = "（没有相关记忆）"

        scene_context = event.get("scene_context", "")
        event_desc = event.get("description", "")

        # 列出在场 NPC 的 ID → 名字 映射
        in_scene_npcs = self._get_scene_npcs(event["location"], 1.0, [])
        npc_list_text = "\n".join(
            f"- {n['npc_id']}: {n['name']}"
            for n in [self._meta.get_npc(nid) for nid in in_scene_npcs]
            if n
        )

        event_section = ""
        if event_desc:
            event_section = f"""
## 当前发生的事件
时间: {event['game_time']}秒
事件: {event_desc}"""
            if event.get("actor_npc_id"):
                event_section += f"\n发起者: {event['actor_npc_id']}"
            if event.get("affected_npc_ids"):
                event_section += f"\n被影响者: {', '.join(event['affected_npc_ids'])}"

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

## 场景背景
时间: {event['game_time']}秒
地点: {event['location']}
场景: {scene_context}
{event_section}

## 在场人物（ID 对照）
{npc_list_text}

请决定{npc['name']}的下一步行为。new_event 的 affected_npc_ids 必须使用上方的 ID。"""

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
        # 写 action 记忆（决策者自身）
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
                    gc.get("goal_type", "long_term"),
                    gc.get("description", ""),
                    gc.get("priority", 5),
                    str(game_time), None,
                )
            elif action in ("complete", "abandon"):
                goals = self._meta.list_goals(npc_id, status="active")
                for g in goals:
                    if gc.get("description", "") in g["description"]:
                        status = "completed" if action == "complete" else "abandoned"
                        self._meta.update_goal(g["goal_id"], status=status)
                        break

        # 返回新事件（location/intensity 由系统维持，不采信 LLM 输出）
        if decision.new_events:
            evt = decision.new_events[0]
            # 过滤非法的 affected_npc_ids（必须是有效 NPC）
            raw_affected = evt.get("affected_npc_ids", []) or []
            affected_ids = [nid for nid in raw_affected if self._meta.get_npc(nid)]
            return {
                "description": evt.get("description", ""),
                "location": location,
                "intensity": 1.0,
                "actor_npc_id": npc_id,
                "affected_npc_ids": affected_ids,
                "game_time": game_time,
                "scene_context": "",
            }
        return None
