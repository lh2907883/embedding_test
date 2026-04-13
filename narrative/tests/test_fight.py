"""
测试场景：学校走廊冲突

使用方法：
  终端1: cd narrative && uvicorn app:app --port 8001
  终端2: cd narrative && python tests/test_fight.py
"""

import requests

BASE = "http://localhost:8001/api"


def reset():
    """删除所有 NPC（级联删除记忆和目标）"""
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


def inject_event(description, location, intensity, involved, game_time):
    print(f"\n{'='*60}")
    print(f"注入事件 (时间={game_time}s): {description}")
    print(f"{'='*60}\n")

    r = requests.post(f"{BASE}/events/inject", json={
        "description": description,
        "location": location,
        "intensity": intensity,
        "involved_npc_ids": involved,
        "game_time": game_time,
    })

    if r.status_code != 200:
        print(f"错误: {r.status_code} — {r.text}")
        return

    result = r.json()

    for rnd in result["rounds"]:
        print(f"\n--- 第 {rnd['round']} 轮 | 事件: {rnd['event_description'][:60]} ---")
        for d in rnd["decisions"]:
            print(f"  [{d['npc_name']}] {d['action']}")
            if d.get("new_events"):
                for ne in d["new_events"]:
                    print(f"    → 新事件: {ne.get('description', '')}")

    print(f"\n共 {len(result['rounds'])} 轮, {result['total_decisions']} 次决策")


def show_memories(npc_id, npc_name):
    r = requests.get(f"{BASE}/npcs/{npc_id}/memories")
    memories = r.json()
    print(f"\n{npc_name} 的记忆 ({len(memories)} 条):")
    for m in memories:
        print(f"  [{m['game_time']}s] ({m['memory_type']}): {m['content']}")


if __name__ == "__main__":
    print("=" * 60)
    print("测试：学校走廊冲突")
    print("=" * 60)

    reset()

    create_npc("a", "张暴", "暴躁易怒，好斗，被挑衅时一定会动手", {"anger": 0.9, "brave": 0.8}, "学校")
    create_npc("b", "李怯", "胆小怕事，遇到冲突第一反应是逃跑或求助", {"brave": 0.1, "cautious": 0.9}, "学校")
    create_npc("c", "王正", "正义感强，看不得欺凌弱小，会主动劝架或保护弱者", {"justice": 0.9, "brave": 0.7}, "学校")

    inject_event(
        description="张暴在学校走廊拦住李怯，大声辱骂他并推了他一把",
        location="学校",
        intensity=1.0,
        involved=["a", "b"],
        game_time=0,
    )

    print(f"\n{'='*60}")
    print("事件结束后的状态")
    print(f"{'='*60}")
    for npc_id, name in [("a", "张暴"), ("b", "李怯"), ("c", "王正")]:
        show_memories(npc_id, name)
