# mavis Adaptive Runtime - P2.x 融合

> **永久 invariant #38**: 9 节点 LangGraph + 8 机制 query 路由 = mavis adaptive runtime
> **永久 invariant #21**: LangGraph StateGraph = mavis team plan DAG
> **永久 invariant #36**: LlamaIndex 4 步索引 = mavis memory RAG
> **永久 invariant #37**: mavis 8 机制 query 路由

## 解决什么问题

P1.1.a 9 节点 LangGraph 每次跑全跑 (所有 query 都跑 9 个节点) — 不高效。
P1.4 8 机制 query 路由只路由 query, 不处理 LLM 任务。
**P2.x 融合 = 8 机制 query 路由 → 选节点子集 → 动态 LangGraph subgraph**。

效果: 节点调用数降低 33.3% ~ 66.7%, 平均 54.2%。

## 8 机制 → 节点子集映射

| 机制 | 节点数 | 节点列表 |
|---|---|---|
| 1 CLAUDE.md | 3/9 (66.7%) | 01_planner + 02_researcher + 08_reporter |
| 2 子智能体 | 6/9 (33.3%) | 01_planner + 02_researcher + 03_coder + 05_runner + 07_patcher + 08_reporter |
| 3 Skills | 3/9 (66.7%) | 02_researcher + 03_coder + 08_reporter |
| 4 Hooks | 4/9 (55.6%) | 02_researcher + 03_coder + 07_patcher + 08_reporter |
| 5 MCP | 4/9 (55.6%) | 02_researcher + 03_coder + 05_runner + 08_reporter |
| 6 Headless | 3/9 (66.7%) | 01_planner + 05_runner + 08_reporter |
| 7 Agent SDK | 6/9 (33.3%) | 01_planner + 02_researcher + 03_coder + 05_runner + 07_patcher + 08_reporter |
| 8 Plugins | 4/9 (55.6%) | 01_planner + 02_researcher + 03_coder + 08_reporter |

## 6 个轻量版节点 (P2.x 简化版)

P1.1.a 9 节点是完整实现 (700+ 行), P2.x 用 6 个**轻量版**节点 (复用 P1.4 query_engine + 14B):

- **01_planner**: 调 14B 制定 3 步子计划 (~3s)
- **02_researcher**: 调 P1.4 query_engine 检索 + 总结 (~8s)
- **03_coder**: 调 14B 生成代码/方案 (~22s, 最慢)
- **05_runner**: mock 运行 + 验证 (P2.x 简化, 0s)
- **07_patcher**: 修复 (P2.x 简化, 0s)
- **08_reporter**: 汇总所有 intermediate + 14B 输出最终答案 (~7s)

04_action / 06_feature / 09_decision P2.x 暂不实现 (留给 P2.y)。

## 实战验证 (2026-07-11 05:10)

**8 query 全部路由正确, 路由准确率 8/8 = 100%!**

| Test | Query | 机制 | 节点 | 节点节省 | 耗时 |
|---|---|---|---|---|---|
| 1 | CLAUDE.md 五层记忆 | CLAUDE.md | 3/9 | 66.7% | 10.6s |
| 2 | 子智能体 5 模式 | 子智能体 | 6/9 | 33.3% | 43.82s |
| 3 | Skills AWEL | Skills | 3/9 | 66.7% | 38.31s |
| 4 | Hooks block-dangerous | Hooks | 4/9 | 55.6% | 36.36s |
| 5 | MCP 6 server | MCP | 4/9 | 55.6% | 42.85s |
| 6 | Headless --max-turns | Headless | 3/9 | 66.7% | 9.93s |
| 7 | Agent SDK @tool | Agent SDK | 6/9 | 33.3% | 47.35s |
| 8 | Plugins plugin.json | Plugins | 4/9 | 55.6% | 34.38s |

**平均节点节省 54.2%** (33.3% ~ 66.7%)
**平均耗时 32.95 秒/次** (含 LLM 14B 多次调用)

## 用法

```bash
# 1. 激活 venv (含 langgraph + LlamaIndex + Ollama)
source ~/workspace/mavis-llamaindex/bin/activate

# 2. 跑 8 query 完整测试
python3 ~/workspace/mavis-adaptive-runtime-v2/adaptive_runtime.py

# 3. 自定义 query
python3 ~/workspace/mavis-adaptive-runtime-v2/adaptive_runtime.py "mavis 子智能体 怎么 work"
```

## 复用今晚经验 (P1.1.a + P1.2 + P1.3 + P1.4)

| 经验 | 来源 | P2.x 应用 |
|---|---|---|
| 9 节点 LangGraph | 永久 invariant #21 | P2.x 6 节点子集 (P1.1.a 是 9 节点) |
| CrewAI 4 组件 | 永久 invariant #35 | P2.x dynamic agent 模式 (后续融合) |
| LlamaIndex 4 步索引 | 永久 invariant #36 | P2.x 02_researcher 复用 P1.3 索引 |
| 8 机制 query 路由 | 永久 invariant #37 | P2.x 入口处路由 |
| 14B 模型 | 永久 invariant #34 | P2.x 各节点用 14B |
| HttpxOllamaEmbedding | P1.3 新增 | P2.x _call_llm_14b 绕过 ollama lib |
| LangGraph 1.0+ | P1.1.a | P2.x StateGraph + MemorySaver + END + START |

## 关键设计

1. **8 机制 → 节点子集**: 静态映射 (P2.x 简化), P2.y 可改成 LLM 动态决策
2. **节点串行**: P2.x 简化为顺序边, P1.1.a 的 conditional_edges 留给 P2.y
3. **MemorySaver**: 持久化 (P1.1.a 一样), 支持 thread_id
4. **cycle_report.json**: 每 query 写报告, 跟 P1.1.a 一致

## 下一步 (P2.y)

- **P2.y**: 04_action / 06_feature / 09_decision 3 节点实现 (P2.x 暂未实现)
- **P2.y**: conditional_edges 落地 (P1.1.a 已经有)
- **P2.y**: hierarchical Process (借鉴 CrewAI P1.2) + 8 机制 + 9 节点 三方融合
- **P2.y**: LLM 动态选节点 (替代 P2.x 静态映射)

## 验收 checklist

- [x] 8 机制 → 节点子集映射 (8 种配置)
- [x] 6 个轻量版节点 (复用 P1.4 query_engine + 14B)
- [x] 动态 LangGraph subgraph 构建
- [x] 8 query 实战验证
- [x] 路由准确率 8/8 = 100%
- [x] 平均节点节省 54.2%
- [x] cycle-report.json + adaptive-test-results.json

## 文件清单

- `adaptive_runtime.py` (主入口, 350 行)
- `cycle-report.json` (单 query 报告)
- `adaptive-test-results.json` (8 query 验证)
- `README.md` (本文)
