# Narrative — AI NPC 推演服务

基于 LLM 的 NPC 记忆/目标/场景推演引擎。详细设计见 [`DESIGN.md`](./DESIGN.md)。

## 环境准备

### 1. 安装依赖

仓库已带共享虚拟环境 `../​.venv`，已包含全部依赖。如需重新安装：

```bash
cd narrative
pip install -r requirements.txt
# 此外还需要：openai、python-dotenv（DeepSeek 调用 + .env 加载）
pip install openai python-dotenv
```

### 2. 配置 LLM Key

在 `narrative/.env` 中填入 DeepSeek key：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

## 启动服务

方式 A — 激活 venv 再启动：

```bash
source /home/lihao/code/embedding/.venv/bin/activate
cd narrative
uvicorn app:app --port 8001 --reload
```

方式 B — 直接用 venv 里的 uvicorn（无需 activate）：

```bash
cd narrative
/home/lihao/code/embedding/.venv/bin/uvicorn app:app --port 8001 --reload
```

启动后：

- 服务地址：<http://127.0.0.1:8001>
- API 文档：<http://127.0.0.1:8001/docs>

数据落盘到 `narrative/data/`：
- `metadata.db` — SQLite，存 NPC 资料/目标
- `qdrant_storage/` — Qdrant 本地嵌入存储，存记忆向量

## 运行测试场景

测试脚本位于 `tests/`，需要先启动服务再在另一终端执行。

### 场景 1：学校走廊冲突（`test_fight.py`）

```bash
# 终端 1：启动服务（先激活 venv）
source /home/lihao/code/embedding/.venv/bin/activate
cd narrative && uvicorn app:app --port 8001

# 终端 2：跑测试
source /home/lihao/code/embedding/.venv/bin/activate
cd narrative
python tests/test_fight.py        # 纯情境模式 — LLM 自主推演
python tests/test_fight.py 2      # 预设事件模式 — 强制"张暴推李怯"，看其他人反应
```

### 场景 2：集市骗局（`test_deception.py`）

四个角色信息不对称下的涌现叙事（奸商 / 新手 / 知情者 / 竞争者）：

```bash
source /home/lihao/code/embedding/.venv/bin/activate
cd narrative
python tests/test_deception.py
```

## 重置数据

测试脚本会在开始时清理已有 NPC。如需手工清空全部数据：

```bash
rm -rf narrative/data/
```

下次启动会自动重建。
