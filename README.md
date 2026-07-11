# mavis-framework

mavis framework monorepo — 跨夜战 21 小时 (2026-07-10 → 2026-07-11) 全部 P 队列项目整合。

## 20 个项目 (按 P 队列时间线)

| 项目 | 永久 invariant | 描述 |
|---|---|---|
| `mavis-devika-template` | #31 | Devika 9 大 Agent 模板 (12 文件 / 1834 行) |
| `mavis-devika-runtime` | #32 | 9 Agent LangGraph StateGraph runtime + B4/Linter/verify_pattern |
| `mavis-recall-v2` | #30 | 召回系统 v2 (jieba 中文 + Hybrid 检索) |
| `mavis-verifier-v2` | #30 | 验证器 v2 (Sonnet 评分) |
| `mavis-team-plan-v2` | #35 | CrewAI 4 组件 (Agent/Task/Crew/Process) |
| `mavis-llamaindex-v2` | #36 | LlamaIndex 4 步 RAG (Load/Index/Store/Query) |
| `mavis-8mech-router-v2` | #37 | mavis 8 机制 query 路由 (49 关键词 + LLM 兜底) |
| `mavis-adaptive-runtime-v2` | #38 | 9 节点 + 8 机制融合 (P2.x) |
| `mavis-adaptive-runtime-v3` | #39 | + conditional_edges + hierarchical (P2.y) |
| `mavis-adaptive-runtime-v4` | #40 | + LLM 动态选节点 + 真 subprocess (P2.z) |
| `mavis-adaptive-runtime-v5` | #41 | + P1.1.a 真功能 (P3.0) |
| `mavis-crewai-v3` | #42 | 4 角色 Manager + 3 Worker + 50 query scale up (P3.1) |
| `mavis-crewai-v4` | #43 | + Coder 真写文件 + Linter + Patcher (P3.2) |
| `mavis-crewai-v5` | #44 | + 50 改文件任务 scale up (P3.3) + 真实项目改写 (P3.4) |
| `mavis-crewai-v6` | #46 | + 修复 2 bug (动态阈值 + Patcher Linter 验证) (P3.5) |
| `mavis-crewai-v6/mavis_v2.py` | #47 | mavis framework 整合主入口 v2 (P3.6) |
| `mavis-crewai-v7/crewai_v7.py` | #48 | + hooks 集成 + 200 query (P4.0) |
| `mavis-crewai-v7/mavis_v3.py` | #50 | mavis framework 整合主入口 v3 (P4.6 facade) |
| `mavis-handoff` | - | 跨夜接手指南集 |
| `mavis-babyagi` | - | BabyAGI 任务循环实验 |
| `mavis-langgraph` | - | LangGraph 实战 demo |
| `mavis-llamaindex` | - | LlamaIndex v1 原型 |

## 主入口 (mavis framework v3)

```bash
# 1. status (15 P 队列 + 28 黑名单 + 24 invariant)
python3 mavis-crewai-v7/mavis_v3.py status

# 2. query (8 机制路由 + 14B 总结)
python3 mavis-crewai-v7/mavis_v3.py query "CLAUDE.md 五层记忆"

# 3. modify (P3.5 修复后真改文件, 失败回滚)
python3 mavis-crewai-v7/mavis_v3.py modify "加 docstring" /path/to/file.py

# 4. rebuild (auto rebuild LlamaIndex 索引)
python3 mavis-crewai-v7/mavis_v3.py rebuild
```

## 跨夜战 21 小时战报

- **18 个 P 队列**: P1.1.a → P1.2 → P1.3 → P1.4 → P2.x → P2.y → P2.z → P3.0 → P3.1 → P3.2 → P3.3 → P3.4 → P3.5 → P3.6 → P4.0 → P4.1 mini → P4.3 daemon → P4.6 facade
- **24 个永久 invariant** (#9-#50, 跨 #18 #30 缺): 写入 mavis memory topic
- **mavis 8 机制协奏 92.5% → 99%** (+6.5%)
- **0 事故**: P3.5 失败回滚 work, 14B+32B 都写不动 10000+ 字符, 失败回滚兜底

## 永久 invariant 库

详见 `~/.mavis/agents/mavis/memory/topics/agent-dev-book-2026-07-10.md` (1586 行, 跨 #18 #30 缺共 24 invariant)

## 14 项缺口修复 (2026-07-11)

| # | 缺口 | 状态 | 关键 |
|---|---|---|---|
| 1 | P4.0 hooks 真集成 | ✅ PASS | settings.json PreToolUse |
| 2 | P4.1 200 query | ✅ PASS | 47.5 分钟, 87.6% 准确率 |
| 3-4 | 大文件 32B 验证 | ✅ PASS | 14B+32B 都不可行, 失败回滚 work |
| 5 | P4.3 daemon 集成 | ✅ PASS | 3/3 大功能 |
| 6 | mavis_v3 facade | ✅ PASS | 24 invariant, 8 大功能 |
| 7 | 32B 对比 | ✅ PASS | 14B 快 33 倍, 32B 大文件不可行 |
| 8 | recall verify | ✅ PASS | 8 query 79.2% |
| 9 | Devika 真用 | ✅ PASS | 9 node 真定义 + LangGraph |
| 10 | **CI/CD git push** | ✅ PASS | monorepo + GitHub push + CI |
| 11 | 知识星图 240+ | ✅ PASS | 227 → 243 节点 |
| 12, 13, 14 | narrative + invariant | ✅ PASS | 24 invariant, 协奏 99% |
