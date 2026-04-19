"""
测试场景：集市骗局 — 信息不对称下的涌现叙事

人物：
  赵六（奸商）— 贪婪狡猾，善于花言巧语。知道小明的玉佩是稀世珍品
  小明（新手）— 老实淳朴，初来乍到。不知道自己玉佩的真实价值
  陈七（知情者）— 见过赵六多次骗人，但为人冷漠，不爱多管闲事
  刘八（竞争者）— 赵六的同行对手，想揭穿赵六但动机是抢生意

信息不对称：
  - 赵六知道玉佩值千金，但会谎称只值几两银子
  - 小明以为玉佩只是普通家传物件
  - 陈七知道赵六的骗术，但不一定会出手
  - 刘八想揭穿但自己也想低价收购

使用方法：
  终端1: cd narrative && rm -rf data && uvicorn app:app --port 8001
  终端2: cd narrative && python tests/test_deception.py
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


def add_memory(npc_id, content, memory_type="background", game_time="0"):
    requests.post(f"{BASE}/npcs/{npc_id}/memories", json={
        "game_time": game_time,
        "content": content,
        "memory_type": memory_type,
    })


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
        print(f"  事件: {rnd['event_description']}")
        for d in rnd["decisions"]:
            print(f"    [{d['npc_name']}] {d['action']}")

    print(f"\n共 {len(result['rounds'])} 轮, {result['total_decisions']} 次决策")


def show_memories(npc_id, npc_name):
    r = requests.get(f"{BASE}/npcs/{npc_id}/memories")
    memories = r.json()
    print(f"\n{npc_name} 的记忆 ({len(memories)} 条):")
    for m in memories:
        print(f"  [{m['game_time']}s] ({m['memory_type']}): {m['content']}")


if __name__ == "__main__":
    print("=" * 60)
    print("测试：集市骗局 — 信息不对称下的涌现叙事")
    print("=" * 60)

    reset()

    # ── 创建人物 ──
    create_npc("zhao", "赵六",
               "贪婪狡猾，善于花言巧语和察言观色，擅长用低价骗取不知情者的贵重物品",
               {"greed": 0.9, "cunning": 0.9, "eloquence": 0.8}, "集市")
    create_npc("ming", "小明",
               "老实淳朴，容易相信别人的话，初来乍到对市场行情完全不了解",
               {"naive": 0.9, "trusting": 0.8, "knowledge": 0.1}, "集市")
    create_npc("chen", "陈七",
               "见多识广但为人冷漠，除非事情跟自己有直接利害关系否则不会插手",
               {"apathy": 0.8, "observant": 0.9, "brave": 0.2}, "集市")
    create_npc("liu", "刘八",
               "精明自利，是赵六的同行竞争者，一直想揭穿赵六抢走他的客源，但本质上也想从中获利",
               {"cunning": 0.7, "competitive": 0.9, "greedy": 0.6}, "集市")

    # ── 预设背景记忆（制造信息不对称） ──
    # print("\n--- 写入背景记忆 ---")

    # # 赵六知道玉佩的真实价值
    # add_memory("zhao", "我在古玩行混了二十年，一眼就能看出好东西。最近听说有个外地来的年轻人带着一块上等和田玉佩，至少值五百两银子")
    # add_memory("zhao", "这种生人最好骗，随便编个故事说玉佩不值钱，三五两就能收过来")

    # # 小明不知道玉佩值多少
    # add_memory("ming", "这块玉佩是爷爷留给我的，他说有纪念意义让我好好保管。我也不知道值多少钱，可能就是块普通玉石吧")
    # add_memory("ming", "我刚到这个镇上，人生地不熟，得找地方安顿下来，手头有点紧")

    # # 陈七知道赵六的底细
    # add_memory("chen", "赵六这个人我太了解了，专门骗外地人，上个月刚用十两银子骗走一个老农的祖传铜镜，那东西至少值两百两")
    # add_memory("chen", "不过这些事跟我没关系，多一事不如少一事")

    # # 刘八想抢赵六的生意
    # add_memory("liu", "赵六总是抢先一步骗走好东西，我恨死他了。如果能在他骗人的时候揭穿他，客人就会转投我这边")
    # add_memory("liu", "不过如果那东西真的值钱，最好是我自己能以合理的低价买到手")

    # print("背景记忆写入完成")

    # ── 场景推演 ──
    simulate_scene(
        description="集市上人来人往，赵六的古玩摊位前，小明正拿着一块玉佩询问价格。陈七在旁边的茶摊喝茶，刘八在对面自己的摊位上观察",
        location="集市",
        characters=["zhao", "ming"],
        intensity=1.0,
        game_time=0,
    )

    # ── 查看记忆 ──
    print(f"\n{'='*60}")
    print("场景结束后各人物记忆")
    print(f"{'='*60}")
    for npc_id, name in [("zhao", "赵六"), ("ming", "小明"), ("chen", "陈七"), ("liu", "刘八")]:
        show_memories(npc_id, name)
