# mavis 8 机制 query 路由 - P1.4

> **永久 invariant #37**: mavis 8 机制 query_engine 路由 = 永久 invariant #36 落地
> **来源**: mavis-2-roadmap.md §四、与 8 机制协奏嘅映射

## 解决什么问题

mavis 8 机制协奏 (CLAUDE.md / 子智能体 / Skills / Hooks / MCP / Headless / Agent SDK / Plugins) 需要按 query 自动路由到对应机制, 让 LLM 总结能精确定位文档。

P1.4 实现 2 级路由:
1. **关键词路由 (优先)**: 中英文关键词匹配 + 权重评分
2. **LLM 兜底**: 关键词不命中时, 用 14B 决策

## 8 机制配置

| # | 机制 | 关键词数 | 描述 | 状态 |
|---|---|---|---|---|
| 1 | CLAUDE.md | 8 | 项目级 AGENTS.md, init script auto-inject | ✅ 13+ 项目 |
| 2 | 子智能体 | 8 | 5 模式 (P1.1.a 9 Agent 模式) | ✅ 5 模式 |
| 3 | Skills | 7 | 技能系统, AWEL 三层架构 | ✅ 3 个 skill |
| 4 | Hooks | 7 | Shell hooks 17/17 PASS | ✅ Shell 17/17 |
| 5 | MCP | 7 | Model Context Protocol, 6 server | ✅ 6 server |
| 6 | Headless | 7 | Headless 模式 + CI/CD | ✅ GitHub Actions |
| 7 | Agent SDK | 7 | 完整 Agent SDK | 🟡 50% (Phase 4) |
| 8 | Plugins | 6 | plugin.json manifest + install CLI | ✅ plugin.json |

## 路由策略

### 1. 关键词路由 (优先)

```python
def route_by_keywords(query: str) -> List[Tuple[str, float]]:
    query_lower = query.lower()
    matches = []
    for mech in EIGHT_MECHANISMS:
        score = 0
        for kw in mech["keywords"]:
            if kw.lower() in query_lower:
                # 多字关键词权重更高
                score += len(kw) / 5.0
        if score > 0:
            matches.append((mech["name"], score))
    matches.sort(key=lambda x: -x[1])
    return matches
```

**权重设计**: `score = len(关键词) / 5.0` (中文字符 3 字符 = 0.6, 英文 5 字符 = 1.0)

### 2. LLM 兜底

```python
def call_llm_router(query: str, mechanisms: List[dict]) -> Optional[str]:
    system = "你是 mavis 8 机制路由器, ... 只输出机制名称"
    user = "8 个机制: ... 用户 query: ..."
    return ollama_chat(model="qwen2.5:14b", system, user)
```

## 实战验证 (2026-07-11 04:55)

8 个 query 全部路由正确, **准确率 8/8 = 100%**!

| # | Query | 路由结果 | Score | 召回文件 |
|---|---|---|---|---|
| 1 | CLAUDE.md 五层记忆 | CLAUDE.md | 2.60 | mavis-orchestration + book-learning |
| 2 | 子智能体 5 模式 | 子智能体 | 0.80 | MEMORY + mavis-orchestration |
| 3 | Skills AWEL | Skills | 3.80 | agent-dev-book + MEMORY |
| 4 | Hooks block-dangerous | Hooks | 4.80 | security-guards |
| 5 | MCP 6 server | MCP | 2.20 | mcp-reference |
| 6 | Headless --max-turns | Headless | 4.40 | mavis-orchestration |
| 7 | Agent SDK @tool | Agent SDK | 2.80 | mavis-orchestration + book-learning |
| 8 | Plugins plugin.json | Plugins | 6.20 | mavis-orchestration + mavis-2-roadmap |

**单次 query 耗时 5-12 秒** (含 LLM 14B 总结)。

## 用法

```bash
# 1. 激活 venv
source ~/workspace/mavis-llamaindex/bin/activate

# 2. 跑 8 机制 query 验证
python3 ~/workspace/mavis-8mech-router-v2/router.py

# 3. 自定义 query
python3 ~/workspace/mavis-8mech-router-v2/router.py "mavis Skills 怎么用"
```

## 复用 P1.3 经验

- **索引持久化**: P1.3 已建好 17 文件 → 241 chunks 索引, P1.4 直接 `load_index_from_storage` 复用
- **HttpxOllamaEmbedding**: P1.4 关键词 + LLM 路由都绕过 ollama lib, 走 httpx HTTP API
- **14B 模型 (永久 invariant #34)**: LLM 兜底路由用 qwen2.5:14b
- **OUTPUT IN CHINESE (永久 invariant #14)**: 路由决策 LLM prompt 强制中文

## 下一步 (P2.x)

- **P2.x**: 8 机制 query_engine 跟 P1.1.a 9 节点 LangGraph 编排融合 (变成 9 节点 + 8 路由)
- **P2.x**: hierarchical Process (借鉴 CrewAI P1.2) + 8 机制 query 路由 (P1.4) 融合
- **P2.x**: 自动 rebuild 索引 (mavis memory 更新时)

## 验收 checklist

- [x] 8 机制配置 (CLAUDE.md / 子智能体 / Skills / Hooks / MCP / Headless / Agent SDK / Plugins)
- [x] 关键词路由 (中英, 57 个关键词)
- [x] LLM 兜底 (14B)
- [x] 8 个 query 实战验证
- [x] 路由准确率 8/8 = 100%
- [x] 复用 P1.3 索引
- [x] HttpxOllamaEmbedding 模式
- [x] 8mech-test-results.json 报告

## 文件清单

- `router.py` (主入口, 250 行)
- `8mech-test-results.json` (8 query 验证)
- `README.md` (本文)
