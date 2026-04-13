# NPC Agent 叙事系统 - 设计文档

## 项目概述

AI 驱动的游戏 NPC 叙事系统。NPC 拥有独立记忆、性格、目标，通过 LLM 自主决策行为，事件在 NPC 之间自然传播，形成涌现叙事。

## 项目位置

```
/Users/mac08/ai/embedding/
├── backend/              # 独立项目：多租户向量数据库 Web 服务（与 narrative 无关）
├── frontend/             # backend 的 Vue 前端（与 narrative 无关）
└── narrative/            # 叙事系统
    ├── .env              # ANTHROPIC_API_KEY
    ├── DESIGN.md         # 本文件
    └── npc-agent/        # NPC Agent 服务
        ├── config.py
        ├── models.py
        ├── api_models.py
        ├── embedding_service.py
        ├── vector_store.py
        ├── metadata_store.py
        ├── npc_memory_manager.py
        ├── llm_service.py
        ├── decision_engine.py
        ├── app.py
        ├── requirements.txt
        ├── test_fight.py
        └── data/           # 运行时数据（.gitignore）
```

## 技术栈

- **向量数据库**: Qdrant 嵌入式模式（本地，无需 Docker）
- **Embedding 模型**: intfloat/multilingual-e5-large（1024 维，fastembed/ONNX，离线可用）
- **关系数据库**: SQLite（NPC 性格 + 目标）
- **LLM**: Anthropic Claude Sonnet（通过 anthropic SDK）
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
  memory_type,      # background / witnessed / heard / action / thought / relationship
  game_time,        # 游戏内时间（有序字符串，如 T001, T002）
  content,          # 记忆文本（embedding 来源）
  source_npc_id,    # 信息来源 NPC（纯溯源，不做可信度判断）
  related_npc_ids,  # 关联的 NPC 数组（可多个）
  location          # 地点
}
```

**关键点：**
- NPC = 租户，记忆按 npc_id 隔离
- 同一事件在不同 NPC 记忆中内容不同（信息不对称是核心机制）
- 关系也存记忆库（memory_type: relationship），不单独建表，因为关系会随事件变化
- source_npc_id 纯粹是信息溯源，方便 NPC 之间交流时追踪信息链条
- Embedding 用 passage_embed（文档）和 query_embed（查询）区分，支持跨语言

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
- 目标来源：初始预设、API 手动添加、LLM 决策时自动产生
- LLM 也可以完成或放弃目标

### 4. 情感系统

**不存储，不做状态机。** LLM 每次决策时从记忆 + 性格自行推断当前情绪。原因：
- 情感是"性格 + 近期经历"的函数，这两样已经有了
- 存下来需要显式更新和衰减逻辑，增加复杂度
- LLM 天然能从上下文推断情绪

### 5. 事件系统 & LLM 决策循环

**外部只注入起始事件，后续连锁反应由 LLM 自主推演。**

```
外部注入起始事件（POST /api/events/inject）
  → 根据 location + intensity 确定在场 NPC
  → 给在场 NPC 写入目击记忆
  → 逐个 NPC 调 LLM 决策：
      prompt = 性格 + 目标 + 相关记忆（语义搜索） + 当前事件
      output = { action, dialogue, memory_note, new_events, goal_changes }
  → 处理 LLM 输出：写记忆、更新目标
  → 如果 action 产生 new_events → 下一轮继续触发相关 NPC 决策
  → 循环，直到无新事件 或 达到最大轮次（默认 10 轮）
```

**事件传播规则：**
- 不按"三级"硬分类，用 location + intensity（0-1）连续参数控制
- intensity=1.0 → 该 location 所有 NPC 知道
- intensity=0.2 → 该 location 20% 的 NPC 知道
- 当事人（involved_npc_ids）一定在列表中
- 后续传播（谁告诉谁、是否失真）由 NPC 的 LLM 决策行为产生，不是算法

**不存储客观事实：** 事件由 NPC 行为产生，当事人的记忆就是"真相"。不需要上帝视角。

**游戏时间：** 纯有序字符串标识（T001, T002...），不需要跟真实时间对应。

### 6. LLM 决策 prompt 结构

```
[System] 你是游戏NPC行为决策引擎...输出JSON格式...

[User]
## NPC信息
ID / 姓名 / 性格 / 特征 / 当前位置

## 当前目标
- [short_term] 找到宝藏（优先级9）

## 相关记忆（语义搜索 top 10）
- [T001] (witnessed): 张暴在走廊推了李怯
- [T001] (relationship): 李四是我多年的朋友

## 当前发生的事件
时间 / 地点 / 事件描述 / 相关人物

请决定NPC的行为。
```

LLM 输出结构化 JSON：
```json
{
  "action": "还手",
  "dialogue": "你先动手的，别怪我！",
  "memory_note": "A先动手打了我，我必须还手",
  "new_events": [{"description": "B还手打了A", "location": "学校", "intensity": 1.0, "involved_npc_ids": ["a","b"]}],
  "goal_changes": [{"action": "add", "description": "打败A", "goal_type": "short_term", "priority": 9}]
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
| `GET /api/npcs/{id}/memories` | 列出记忆 |
| `POST /api/npcs/{id}/memories/search` | 语义搜索记忆 |
| `DELETE /api/npcs/{id}/memories/{mid}` | 删除记忆 |
| `POST /api/npcs/{id}/goals` | 添加目标 |
| `GET /api/npcs/{id}/goals` | 列出目标（默认 active） |
| `PUT /api/npcs/{id}/goals/{gid}` | 更新目标 |
| `DELETE /api/npcs/{id}/goals/{gid}` | 删除目标 |
| `POST /api/events/inject` | 注入事件，触发 LLM 决策循环 |

## 启动方式

```bash
cd /Users/mac08/ai/embedding/narrative/npc-agent
uvicorn app:app --port 8001
```

环境变量在 `narrative/.env`（ANTHROPIC_API_KEY）。

## 已验证的测试场景

**学校打架事件（test_fight.py）：**
- 张暴（暴躁）推了李怯（胆小），王正（正义）在场目击
- LLM 推演结果：张暴继续威胁 → 李怯逃跑求助 → 王正挺身劝架 → 张暴怒转向王正
- 每个 NPC 产生了 7-9 条记忆，2-4 个目标
- 行为完全符合性格设定，连锁反应自然展开

## 开发规范与约定

### 存储边界

什么存 Qdrant（向量库）：
- 所有叙事性、会随时间变化的信息：记忆、关系、背景经历
- 需要语义检索的内容

什么存 SQLite（关系库）：
- 结构化状态数据：NPC 性格/特征、目标（需要枚举，有生命周期）
- 不需要语义搜索，需要精确查询的数据

什么不存：
- 情感状态 — LLM 从记忆+性格推断，不持久化
- 客观事实/上帝视角 — 不维护，当事人的记忆就是真相
- 事件步骤表 — 事件是 NPC 行为产生的，每步直接写入在场 NPC 的记忆

### 记忆写入原则

- 每条记忆是最小语义单元，不做切分
- content 是唯一做 embedding 的字段，其他字段是 payload 用于过滤
- 性格不影响记忆内容（记忆是"看到什么记什么"），只影响决策
- source_npc_id 只做溯源，不做可信度判断
- related_npc_ids 是数组，一条记忆可关联多个 NPC

### 事件传播原则

- 事件系统只负责"谁在场"（location + intensity），不负责后续传播
- 后续传播（谁告诉谁、内容是否失真）是 NPC 决策行为的结果
- 传播动机来自 NPC 的性格、目标、关系记忆，由 LLM 决定
- 不做独立的图算法传播，不维护社交网络图

### LLM 调用原则

- 无事不调：只有 NPC 面临需要抉择的情境才调 LLM
- 决策循环有最大轮次限制（MAX_DECISION_ROUNDS=10），防止无限循环
- LLM 输出必须是结构化 JSON，包含 action/dialogue/memory_note/new_events/goal_changes
- new_events 为空数组时循环自然终止
- LLM 可以自主产生新目标、完成或放弃现有目标

### 新增模块规范

- narrative/ 下按功能模块建子目录（如 npc-agent/、未来的 world-engine/）
- 每个模块独立的 FastAPI 服务、独立的 data/ 目录、独立的端口
- 模块间不共享运行时数据，通过 API 或消息通信
- Qdrant 和 SQLite 都用本地嵌入式模式，不依赖外部服务
- .env 放在 narrative/ 层级，各模块共享

### 游戏时间约定

- 纯有序字符串（T001, T002...），不解析，不跟真实时间对应
- 只要保证有序性即可，格式由调用方决定

### Git 约定

- data/ 目录不提交（.gitignore: `narrative/*/data/`）
- .env 不提交（含 API key）
- 测试脚本（test_*.py）跟随代码提交

## 后续待实现

- **成本控制**：事件驱动无事不调、批处理、休眠机制（当前少量 NPC 不需要）
- **前端**：暂无，纯 API 服务
- **世界引擎**：narrative/ 下可扩展 world-engine 等模块
