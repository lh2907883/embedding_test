# NPC Agent 叙事系统 - 设计文档

## 项目概述

AI 驱动的游戏 NPC 叙事系统。NPC 拥有独立记忆、性格、目标，通过 LLM 自主决策行为，事件在 NPC 之间自然传播，形成涌现叙事。

## 项目结构

```
/Users/mac08/ai/embedding/
├── backend/              # 独立项目：多租户向量数据库 Web 服务（与 narrative 无关）
├── frontend/             # backend 的 Vue 前端（与 narrative 无关）
└── narrative/            # 叙事系统
    ├── .env              # DEEPSEEK_API_KEY
    ├── DESIGN.md         # 本文件
    ├── app.py            # 主入口（FastAPI，挂载子路由）
    ├── config.py         # 全局配置
    ├── requirements.txt
    ├── shared/           # 共享基础设施
    │   ├── models.py         # MemoryEntry, MemorySearchResult, MemoryType
    │   ├── embedding_service.py  # fastembed 封装
    │   ├── vector_store.py       # Qdrant CRUD
    │   └── llm_service.py        # DeepSeek LLM 封装（OpenAI SDK）
    ├── npc_agent/        # NPC 相关逻辑
    │   ├── api_models.py     # NPC/记忆/目标请求响应模型
    │   ├── metadata_store.py # SQLite: npcs + npc_goals
    │   ├── memory_manager.py # 记忆 CRUD + 语义搜索
    │   └── routes.py         # NPC/记忆/目标 API 路由
    ├── event/            # 事件/场景逻辑
    │   ├── api_models.py     # 场景请求响应模型
    │   ├── decision_engine.py # 场景推演 + 统一回合制决策 + 视角记忆生成
    │   └── routes.py         # 场景 API 路由
    ├── tests/
    │   └── test_fight.py     # 学校冲突测试（支持纯场景/预设事件两种模式）
    └── data/             # 运行时数据（.gitignore）
```

## 技术栈

- **向量数据库**: Qdrant 嵌入式模式（本地，无需 Docker）
- **Embedding 模型**: intfloat/multilingual-e5-large（1024 维，fastembed/ONNX，离线可用）
- **关系数据库**: SQLite（NPC 性格 + 目标）
- **LLM**: DeepSeek V3（通过 OpenAI SDK，api.deepseek.com）
- **Web 框架**: FastAPI
- **端口**: 8001

## 核心设计决策

### 1. 记忆系统（Qdrant 向量库）

每条记忆是一个离散 JSON 条目（不是文档，不做切分），直接作为一个向量点存储。

**Qdrant 向量点结构：**
```
id: memory_id (uuid)
vector: content 的 1024 维 embedding
payload: {
  npc_id,           # 主隔离字段，每个 NPC 只能搜到自己的记忆
  memory_type,      # background / affected / witnessed / heard / action / thought
  game_time,        # 游戏内时间（秒数，从 0 开始累加）
  content,          # 记忆文本（embedding 来源）
  source_npc_id,    # 信息来源 NPC（纯溯源，不做可信度判断）
  related_npc_ids,  # 关联的 NPC 数组（可多个）
  location          # 地点
}
```

**记忆类型语义：**
| 类型 | 语义 | 来源 |
|------|------|------|
| background | 初始背景 | 创建 NPC 时手动添加 |
| action | 我主动做了某事 | 场景推演后视角记忆生成 |
| affected | 某事发生在我身上（被动方） | 场景推演后视角记忆生成 |
| witnessed | 我在场但没参与（旁观者） | 场景推演后视角记忆生成 |
| heard | 从其他 NPC 那里听说的 | NPC 主动传播时产生 |
| thought | 内心想法 | 预留，暂未使用 |

**关键点：**
- NPC = 租户，记忆按 npc_id 隔离
- 同一事件在不同 NPC 记忆中内容不同（信息不对称是核心机制）
- source_npc_id 纯粹是信息溯源，方便 NPC 之间交流时追踪信息链条
- Embedding 用 passage_embed（文档）和 query_embed（查询）区分
- 记忆按 game_time（秒数）排序，list 接口按时间升序返回

### 2. NPC 性格（SQLite）

```sql
npcs: npc_id(PK), name, personality(TEXT), traits(JSON), faction, location, created_at
```

性格是相对稳定的结构化数据，只影响决策，不影响记忆内容。

### 3. 目标系统（SQLite）

```sql
npc_goals: goal_id(PK), npc_id(FK), goal_type, description, priority(1-10), status,
           created_game_time, deadline_game_time, created_at
```

- status: active / completed / failed / abandoned
- 只记录**长期人生目标**（如"为父报仇""控制贸易"），不记录当场反应（如"逃跑""找老师"）
- 目标来源：初始预设、API 手动添加、LLM 决策时自动产生

### 4. 情感系统

**不存储，不做状态机。** LLM 每次决策时从记忆 + 性格自行推断当前情绪。

### 5. 场景推演系统

**核心流程：**
```
外部注入场景（POST /api/scenes/simulate）
  → 确定在场 NPC（location + intensity）
  → 如果有 preset_event：写入既成事实记忆
  → 决策循环（每轮一次 LLM 调用）：
      输入：场景 + 所有在场 NPC 的性格/目标/记忆 + 上轮事件
      输出：统一协调的 round_event + 每个 NPC 的 action
      判断：should_continue（格局是否还在变化）
  → 场景结束后：为每个 NPC 生成第一人称视角记忆
```

**关键设计：**

**一轮 = 一次格局变化（不是一个动作）**
- ✅ 正确："张暴打李怯，王正介入，李怯逃跑"（格局：三人 → 李怯脱离）
- ❌ 错误："张暴推了李怯" → "王正上前" → "李怯逃跑"（拆太细）

**每轮一次 LLM 调用（统一回合制）**
- 所有在场 NPC 的信息一次性喂给 LLM
- LLM 输出整体协调的剧情，NPC 行为不会矛盾
- 每个 NPC 的记忆独立查询（保证信息不对称），但决策统一协调

**场景结束后生成视角记忆**
- 推演过程中不写记忆，只收集 round_events
- 推演结束后，为每个 NPC 调一次 LLM 生成第一人称视角记忆
- 连续相关事件合并为一条记忆（有前因后果）
- 旁观者只记录能看到的外在表现，不知道内幕

**场景描述规范**
- 只描述客观环境事实，不包含暗示、预测、NPC 意图
- ✅ "放学后的学校走廊，张暴和李怯迎面相遇"
- ❌ "张暴看到李怯，打算欺负他"（意图是 NPC 内部的，不该出现在场景描述中）

**NPC 约束**
- 只能使用在场人物列表中的 NPC，禁止 LLM 凭空引入新角色

**两种场景模式：**
1. 纯场景：只提供情境，LLM 自主决定所有 NPC 的行为
2. 预设事件：指定一个既成事实（actor + affected），LLM 推演后续反应

### 6. LLM 决策 prompt 结构

```
[System] 你是游戏剧情推演引擎...每轮输出一个整体协调的剧情阶段...

[User]
## 场景
放学后的学校走廊
地点: 学校
当前时间: 0秒

## 在场 NPC（共 3 人）
### a: 张暴
  性格: 暴躁易怒，好斗
  特征: {"anger": 0.9, "brave": 0.8}
  目标: 无
  相关记忆: ...

### b: 李怯
  性格: 胆小怕事
  特征: {"brave": 0.1, "cautious": 0.9}
  目标: 无
  相关记忆: ...

## 上一轮发生的事件（如果有）
...
```

LLM 输出：
```json
{
  "round_event": {
    "description": "张暴挑衅并攻击李怯，王正介入阻止，李怯趁机逃跑",
    "actor_npc_id": "a",
    "affected_npc_ids": ["b", "c"]
  },
  "elapsed_seconds": 30,
  "npc_actions": [
    {"npc_id": "a", "action": "挑衅并推搡李怯"},
    {"npc_id": "b", "action": "被推后挣扎逃跑"},
    {"npc_id": "c", "action": "上前阻止张暴"}
  ],
  "should_continue": true,
  "goal_changes": []
}
```

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /api/npcs` | 创建 NPC |
| `GET /api/npcs` | 列出 NPC |
| `GET /api/npcs/{id}` | NPC 详情 |
| `PUT /api/npcs/{id}` | 更新 NPC |
| `DELETE /api/npcs/{id}` | 删除 NPC + 全部记忆 |
| `POST /api/npcs/{id}/memories` | 添加记忆 |
| `POST /api/npcs/{id}/memories/batch` | 批量添加 |
| `GET /api/npcs/{id}/memories` | 列出记忆（按时间排序） |
| `POST /api/npcs/{id}/memories/search` | 语义搜索记忆 |
| `DELETE /api/npcs/{id}/memories/{mid}` | 删除记忆 |
| `POST /api/npcs/{id}/goals` | 添加目标 |
| `GET /api/npcs/{id}/goals` | 列出目标（默认 active） |
| `PUT /api/npcs/{id}/goals/{gid}` | 更新目标 |
| `DELETE /api/npcs/{id}/goals/{gid}` | 删除目标 |
| `POST /api/scenes/simulate` | 场景推演（支持纯场景 / 预设事件） |

## 启动方式

```bash
cd /Users/mac08/ai/embedding/narrative
uvicorn app:app --port 8001
```

环境变量在 `narrative/.env`（DEEPSEEK_API_KEY）。

## 测试

```bash
cd /Users/mac08/ai/embedding/narrative
rm -rf data && uvicorn app:app --port 8001
# 另一终端
python tests/test_fight.py      # 纯场景模式
python tests/test_fight.py 2    # 预设事件模式
```

## 开发规范与约定

### 存储边界

什么存 Qdrant（向量库）：
- 所有叙事性、会随时间变化的信息：记忆、背景经历
- 需要语义检索的内容

什么存 SQLite（关系库）：
- 结构化状态数据：NPC 性格/特征、目标（需要枚举，有生命周期）
- 不需要语义搜索，需要精确查询的数据

什么不存：
- 情感状态 — LLM 从记忆+性格推断，不持久化
- 客观事实/上帝视角 — 不维护，当事人的记忆就是真相
- 关系 — 已从记忆类型中移除，关系通过 NPC 的叙事记忆自然体现

### 记忆写入原则

- 记忆在场景推演结束后统一生成（不在推演过程中逐轮写入）
- 每个 NPC 由 LLM 从第一人称视角生成记忆
- 连续相关事件合并为一条叙事记忆（有前因后果）
- 不相关 / 时间跨度大的事件拆成多条记忆
- 性格不影响记忆内容（记忆是"看到什么记什么"），只影响决策
- 旁观者不能描述内幕，只能记录直接观察到的现象

### 场景推演原则

- 场景描述只写客观事实，不带暗示或预测
- 每轮 = 一次格局变化（不是一个动作）
- 每轮一次 LLM 调用，所有 NPC 行为统一协调
- 只能使用在场 NPC，禁止引入新角色
- should_continue 判断格局是否还在变化
- MAX_DECISION_ROUNDS = 10（防止无限循环）

### LLM 调用原则

- 无事不调：只有场景推演时才调 LLM
- 决策调用：每轮 1 次（统一回合制）
- 记忆生成调用：场景结束后每个 NPC 1 次
- 总调用数 = 推演轮次 + 在场 NPC 数

### 游戏时间约定

- 整数秒数，从 0 开始累加
- 每轮 elapsed_seconds 由 LLM 判断（合理即可）
- 记忆按 game_time 排序

### 模块规范

- narrative/ 下按功能模块建子目录（shared/、npc_agent/、event/）
- 主入口 app.py 在 narrative/ 根目录，挂载子路由
- 共享服务通过 app.state 传递
- .env 放在 narrative/ 层级

### Git 约定

- data/ 目录不提交（.gitignore: `narrative/data/`）
- .env 不提交（含 API key）
- 测试脚本（test_*.py）跟随代码提交

## 后续待实现

- **成本控制**：事件驱动无事不调、批处理、休眠机制（当前少量 NPC 不需要）
- **前端**：暂无，纯 API 服务
- **世界引擎**：narrative/ 下可扩展 world-engine 等模块
