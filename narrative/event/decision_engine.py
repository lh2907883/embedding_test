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

MEMORY_SYSTEM_PROMPT = """你是 NPC 记忆生成器。给定一个 NPC 经历的一系列连续事件，从他的第一人称视角生成记忆。

JSON格式：
{
  "memories": [
    {
      "content": "记忆叙事文本（第一人称）",
      "memory_type": "action / affected / witnessed",
      "game_time": 该记忆对应的游戏时间秒数（整数）
    }
  ]
}

规则：
1. 多个连续相关的事件可以合并为一条记忆（如果有前因后果）
2. 不相关的事件、时间间隔大的事件应该拆成多条记忆
3. 视角不同：
   - actor（主导者）：用"我做了..."
   - affected（被影响者）：用"我被..."或"...发生在我身上"
   - witnessed（旁观者）：用"我看到..."（描述外在表现，不知内幕）
4. 旁观者只能记录他能直接观察到的现象，不能推测内幕
5. 记忆要简洁、有前因后果、客观（不加情绪描写）
6. game_time 取该段记忆覆盖事件的最后时间点
"""


SYSTEM_PROMPT = """你是游戏剧情推演引擎。每轮你需要为一组在场的 NPC 同时决定他们的行为，输出一个【整体协调一致】的剧情阶段。

JSON格式：
{
  "round_event": {
    "description": "本轮发生了什么的整体描述（一句话）",
    "actor_npc_id": "本轮主导者的ID（推动剧情的那个人）",
    "affected_npc_ids": ["被这个事件直接影响的NPC的ID列表"]
  },
  "elapsed_seconds": 本轮经过的秒数（整数）,
  "npc_actions": [
    {"npc_id": "a", "action": "一句话描述"},
    {"npc_id": "b", "action": "一句话描述"}
  ],
  "should_continue": true/false,
  "goal_changes": [
    {"npc_id": "a", "action": "add/complete/abandon", "description": "...", "goal_type": "long_term", "priority": 5}
  ]
}

**核心原则：每一轮 = 一次格局变化，必须推演到该阶段的最终结果**

**什么是格局变化：**
参与者的角色关系、物理位置、信息掌握、力量对比发生了不可逆的变化。

**一轮必须包含完整的阶段性结果，不能停在过程中间：**
- ✅ "赵六试图低价骗购玉佩，刘八当场揭穿骗局，小明决定不卖并离开"（一轮完成：骗局→揭穿→结果）
- ❌ "赵六出价十两" → "刘八说值更多" → "赵六反驳" → "继续争吵"（拆成多轮，每轮没有结果）

**如果一个阶段已经开始（如争吵、追逐、谈判），必须在当前轮中推演到出结果：**
- 争吵 → 谁赢了 / 被打断 / 某人离开
- 追逐 → 追上了 / 追丢了 / 被拦下
- 谈判 → 达成 / 破裂 / 被第三方打断

**should_continue 判断：**

本轮结束时，是否形成了一个**值得继续推演的新格局**？

✅ 触发续轮（true）——下列任一成立：
- 冲突对象切换：A 打 B，第三方 C 介入 → A 接下来可能打 C 或继续打 B（换对手=新格局）
- 参与者加入 / 脱离：有人新卷入、有人逃走、有人被打倒
- 力量对比反转：压制方 ↔ 被压制方
- 某角色产生了对当前局势的新态度（敌意、被激怒、决心报复、获得新信息）
- 未解决的张力：某方只是被暂时压下/挡住，并没有真正罢手或离场

❌ 终止（false）——下列任一成立：
- 所有在场 actor 都已经罢手 / 离场 / 达成一致，没人还有进一步行动意愿
- 剩余张力只是原局势的机械重复（还在互骂同一句话，没有新信息/新参与者/新态度）

**正面示例**（暴躁者 vs 弱者 vs 调停者）：
- 第 1 轮：张暴打李怯，王正阻拦 → 新格局：三人对峙，王正暂时挡住张暴
  → should_continue=true（张暴被挡住但未罢手，下一步选择是新焦点）
- 第 2 轮：张暴把王正打跑 → 新格局：调停者被击败，李怯暴露
  → should_continue=true（张暴是否继续追打李怯是新焦点）
- 第 3 轮：张暴继续追打李怯 → 新格局：二次施暴
  → should_continue 取决于下一步（李怯是否逃脱 / 是否有人报警）

**NPC 决策必须合乎基本逻辑：**
- NPC 获得关键新信息后（如被告知物品真实价值），必须做出合理反应（如去别处询价、拒绝交易），不能无视信息反复犹豫
- NPC 的行为应该服务于自身利益和目标，不能为了拖延剧情而做出不合理的行为

**其他规则：**
1. 所有 NPC 行为必须互相协调，不能矛盾
2. NPC 行为基于性格和记忆
3. **只能使用在场人物列表中已有的 NPC，禁止凭空引入新角色**
4. actor_npc_id / affected_npc_ids / npc_actions[].npc_id：必须用 ID，不能用名字
5. elapsed_seconds：整个阶段的时长（包含中间的争吵、追逐、打斗等过程）
6. goal_changes：只记录长期人生目标变化，不记当场反应
7. 文字简短，不写小说
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

        in_scene_npcs = self._get_scene_npcs(location, intensity, characters)
        rounds = []
        round_events = []  # 收集所有 round_event 用于最后生成视角记忆
        prev_round_event = None
        current_time = game_time

        # 预设事件作为第一个事件加入序列
        if preset_event:
            round_events.append({
                "game_time": current_time,
                "description": preset_event.description,
                "actor_npc_id": preset_event.actor_npc_id,
                "affected_npc_ids": preset_event.affected_npc_ids,
            })
            prev_round_event = {
                "description": preset_event.description,
                "actor_npc_id": preset_event.actor_npc_id,
                "affected_npc_ids": preset_event.affected_npc_ids,
            }

        # 决策循环（不写记忆，只收集事件）
        for round_num in range(1, MAX_DECISION_ROUNDS + 1):
            _log(f"\n---------- 第 {round_num} 轮 ----------")

            round_data = self._decide_round(
                scene_context=description,
                location=location,
                in_scene_npcs=in_scene_npcs,
                game_time=current_time,
                prev_round_event=prev_round_event,
            )
            if not round_data:
                _log(f"决策失败，循环结束")
                break

            elapsed = round_data["elapsed_seconds"]
            new_time = current_time + elapsed
            re = round_data["round_event"]
            _log(f"  事件: {re['description']} (+{elapsed}s → {new_time}s)")
            _log(f"  actor: {re['actor_npc_id']} | affected: {re['affected_npc_ids']}")
            for a in round_data["npc_actions"]:
                npc = self._meta.get_npc(a["npc_id"])
                name = npc["name"] if npc else a["npc_id"]
                _log(f"    [{name}] {a['action']}")

            # 收集事件
            round_events.append({
                "game_time": new_time,
                "description": re["description"],
                "actor_npc_id": re["actor_npc_id"],
                "affected_npc_ids": re["affected_npc_ids"],
            })

            # 处理目标变更
            for gc in round_data.get("goal_changes", []):
                self._apply_goal_change(gc, new_time)

            decisions = [
                NpcDecisionOutput(
                    npc_id=a["npc_id"],
                    npc_name=(self._meta.get_npc(a["npc_id"]) or {}).get("name", a["npc_id"]),
                    action=a["action"],
                    new_events=[],
                    goal_changes=[],
                )
                for a in round_data["npc_actions"]
            ]
            rounds.append(RoundResult(
                round=round_num,
                event_description=re["description"],
                decisions=decisions,
            ))

            current_time = new_time
            prev_round_event = re

            if not round_data.get("should_continue", False):
                _log(f"剧情自然结束")
                break

        # 场景结束后，为每个 NPC 生成视角记忆
        if round_events:
            _log(f"\n---------- 生成视角记忆 ----------")
            for npc_id in in_scene_npcs:
                self._generate_perspective_memories(npc_id, round_events, location)

        _log(f"\n========== 场景推演结束，共 {len(rounds)} 轮 ==========\n")
        return rounds

    # ── 单轮决策 ──

    def _decide_round(
        self,
        scene_context: str,
        location: str,
        in_scene_npcs: list[str],
        game_time: int,
        prev_round_event: Optional[dict],
    ) -> Optional[dict]:
        # 收集所有在场 NPC 的信息
        npcs_info_text = []
        for npc_id in in_scene_npcs:
            npc = self._meta.get_npc(npc_id)
            if not npc:
                continue
            goals = self._meta.list_goals(npc_id, status="active")
            goals_text = "; ".join(f"{g['description']}" for g in goals) or "无"

            # 检索相关记忆
            query = (prev_round_event or {}).get("description") or scene_context
            memories = self._memory.search_memories(npc_id, query, top_k=5)
            mem_text = "; ".join(f"[{m.game_time}s][{m.memory_type}]{m.content[:50]}" for m in memories) or "无"

            npcs_info_text.append(
                f"### {npc_id}: {npc['name']}\n"
                f"  性格: {npc['personality']}\n"
                f"  特征: {json.dumps(npc.get('traits', {}), ensure_ascii=False)}\n"
                f"  目标: {goals_text}\n"
                f"  相关记忆: {mem_text}"
            )

        prev_section = ""
        if prev_round_event:
            prev_section = f"""
## 上一轮发生的事件
{prev_round_event['description']}
发起者: {prev_round_event.get('actor_npc_id', '')}
被影响者: {', '.join(prev_round_event.get('affected_npc_ids', []))}
"""

        user_prompt = f"""## 场景
{scene_context}
地点: {location}
当前时间: {game_time}秒

## 在场 NPC（共 {len(in_scene_npcs)} 人）
{chr(10).join(npcs_info_text)}
{prev_section}

请决定本轮（一个完整剧情阶段）发生什么。所有 NPC 的行为必须互相协调一致，不能矛盾。
如果剧情已经稳定（如冲突结束、所有人达成新状态），should_continue 设为 false。"""

        try:
            result = self._llm.decide(SYSTEM_PROMPT, user_prompt)
            re = result.get("round_event", {})
            if not re.get("description"):
                return None

            # 过滤非法的 NPC ID
            actor = re.get("actor_npc_id")
            if actor and not self._meta.get_npc(actor):
                actor = None
            re["actor_npc_id"] = actor
            re["affected_npc_ids"] = [
                nid for nid in re.get("affected_npc_ids", []) or []
                if self._meta.get_npc(nid)
            ]

            return {
                "round_event": re,
                "elapsed_seconds": int(result.get("elapsed_seconds", 5)),
                "npc_actions": [
                    a for a in result.get("npc_actions", [])
                    if a.get("npc_id") and self._meta.get_npc(a["npc_id"])
                ],
                "should_continue": result.get("should_continue", False),
                "goal_changes": result.get("goal_changes", []),
            }
        except Exception as e:
            _log(f"  ❌ LLM 决策失败: {e}")
            return None

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
    ):
        """给一个事件写入记忆：actor → action, affected → affected, 其他在场 → witnessed"""
        gt = str(game_time)
        related = [nid for nid in ([actor_npc_id] if actor_npc_id else []) + affected_npc_ids if nid]

        if actor_npc_id and self._meta.get_npc(actor_npc_id):
            self._memory.add_memory(actor_npc_id, AddMemoryRequest(
                game_time=gt,
                content=event_description,
                memory_type=MemoryType.ACTION,
                location=location,
                related_npc_ids=related,
            ))

        for npc_id in affected_npc_ids:
            if self._meta.get_npc(npc_id):
                self._memory.add_memory(npc_id, AddMemoryRequest(
                    game_time=gt,
                    content=event_description,
                    memory_type=MemoryType.AFFECTED,
                    location=location,
                    related_npc_ids=related,
                ))

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

    def _generate_perspective_memories(self, npc_id: str, round_events: list[dict], location: str):
        """根据所有 round_events 为指定 NPC 生成视角记忆"""
        npc = self._meta.get_npc(npc_id)
        if not npc:
            return

        # 为该 NPC 列出每个事件中他的角色和能感知的内容
        events_text = []
        for i, evt in enumerate(round_events, 1):
            actor = evt.get("actor_npc_id")
            affected = evt.get("affected_npc_ids", [])
            if npc_id == actor:
                role = "actor（你是发起者）"
            elif npc_id in affected:
                role = "affected（你是被影响者）"
            else:
                role = "witnessed（你是旁观者，只能看到外在表现）"
            events_text.append(
                f"事件{i}（{evt['game_time']}秒）: {evt['description']}\n"
                f"  你的角色: {role}"
            )

        user_prompt = f"""## 你是谁
ID: {npc_id}
姓名: {npc['name']}
性格: {npc['personality']}

## 你刚刚经历的事件序列
{chr(10).join(events_text)}

请从你的第一人称视角生成你对这件事的记忆。
- 连续相关的事件可以合并为一条记忆
- 不相关或时间跨度大的事件拆成多条
- 旁观者不能描述内幕，只能说看到的外在表现
"""

        try:
            result = self._llm.decide(MEMORY_SYSTEM_PROMPT, user_prompt)
            memories = result.get("memories", [])
            related = list(set(
                [evt.get("actor_npc_id") for evt in round_events if evt.get("actor_npc_id")] +
                [nid for evt in round_events for nid in evt.get("affected_npc_ids", [])]
            ))
            for m in memories:
                content = m.get("content", "")
                if not content:
                    continue
                mtype_str = m.get("memory_type", "witnessed")
                try:
                    mtype = MemoryType(mtype_str)
                except ValueError:
                    mtype = MemoryType.WITNESSED
                gt = str(m.get("game_time", round_events[-1]["game_time"]))
                self._memory.add_memory(npc_id, AddMemoryRequest(
                    game_time=gt,
                    content=content,
                    memory_type=mtype,
                    location=location,
                    related_npc_ids=related,
                ))
            _log(f"  {npc['name']}({npc_id}): 生成 {len(memories)} 条视角记忆")
        except Exception as e:
            _log(f"  ❌ {npc['name']} 视角记忆生成失败: {e}")

    def _apply_goal_change(self, gc: dict, game_time: int):
        npc_id = gc.get("npc_id")
        if not npc_id or not self._meta.get_npc(npc_id):
            return
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
