"""
测试场景：学校走廊冲突

两个测试场景：
  场景 1: 纯情境 — 放学后走廊相遇，LLM 自主推演
  场景 2: 预设事件 — 强制"张暴推李怯"，看其他人反应

使用方法：
  终端1: cd narrative && uvicorn app:app --port 8001
  终端2: cd narrative && python tests/test_fight.py
"""

import requests

BASE = "http://localhost:8001/api"


def reset():
    npcs = requests.get(f"{BASE}/npcs").json()
    for npc in npcs:
        requests.delete(f"{BASE}/npcs/{npc['npc_id']}")
    print(f"清理完成，删除了 {len(npcs)} 个 NPC")


def create_npc(npc_id, name, personality, traits, location):
    r = requests.post(f"{BASE}/npcs", json={
        "npc_id": npc_id, "name": name,
        "personality": personality, "traits": traits,
        "location": location,
    })
    print(f"创建 NPC: {name}({npc_id}) — {r.status_code}")


def simulate_scene(description, location, characters, intensity, game_time, preset_event=None):
    print(f"\n{'='*60}")
    print(f"场景: {description}")
    if preset_event:
        print(f"预设事件: {preset_event['description']}")
    print(f"{'='*60}\n")

    payload = {
        "description": description,
        "location": location,
        "characters": characters,
        "intensity": intensity,
        "game_time": game_time,
    }
    if preset_event:
        payload["preset_event"] = preset_event

    r = requests.post(f"{BASE}/scenes/simulate", json=payload)
    if r.status_code != 200:
        print(f"错误: {r.status_code} — {r.text}")
        return

    result = r.json()
    for rnd in result["rounds"]:
        print(f"\n--- 第 {rnd['round']} 轮 ---")
        for d in rnd["decisions"]:
            print(f"  [{d['npc_name']}] {d['action']}")
            if d.get("new_events"):
                for ne in d["new_events"]:
                    print(f"    → {ne.get('description', '')}")

    print(f"\n共 {len(result['rounds'])} 轮, {result['total_decisions']} 次决策")


def show_memories(npc_id, npc_name):
    r = requests.get(f"{BASE}/npcs/{npc_id}/memories")
    memories = r.json()
    print(f"\n{npc_name} 的记忆 ({len(memories)} 条):")
    for m in memories:
        print(f"  [{m['game_time']}s] ({m['memory_type']}): {m['content']}")


if __name__ == "__main__":
    import sys
    scenario = sys.argv[1] if len(sys.argv) > 1 else "1"

    reset()

    create_npc("a", "张暴", "暴躁易怒，好斗，被挑衅时一定会动手", {"anger": 0.9, "brave": 0.8}, "学校")
    create_npc("b", "李怯", "胆小怕事，遇到冲突第一反应是逃跑或求助", {"brave": 0.1, "cautious": 0.9}, "学校")
    create_npc("c", "王正", "正义感强，看不得欺凌弱小，会主动劝架或保护弱者", {"justice": 0.9, "brave": 0.7}, "学校")

    if scenario == "1":
        print("\n>>> 场景 1: 纯情境 — LLM 自主推演 <<<")
        simulate_scene(
            description="放学后的学校走廊，张暴和李怯迎面相遇，往常张暴就喜欢欺负李怯",
            location="学校",
            characters=["a", "b"],
            intensity=1.0,
            game_time=0,
        )
    else:
        print("\n>>> 场景 2: 预设事件 — 强制'张暴推李怯' <<<")
        simulate_scene(
            description="放学后的学校走廊",
            location="学校",
            characters=["a", "b"],
            intensity=1.0,
            game_time=0,
            preset_event={
                "description": "张暴推了李怯一把",
                "actor_npc_id": "a",
                "affected_npc_ids": ["b"],
            },
        )

    print(f"\n{'='*60}")
    print("记忆状态")
    print(f"{'='*60}")
    for npc_id, name in [("a", "张暴"), ("b", "李怯"), ("c", "王正")]:
        show_memories(npc_id, name)
