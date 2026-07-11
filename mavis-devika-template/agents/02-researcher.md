# 02. 研究 Agent (Researcher)

> 借鉴 Devika §5.1.2 (2) 研究 Agent + LlamaIndex 4 步索引 + QAnything 两阶段检索 (永久 invariant #30)。

## 职责

根据规划结果,生成并执行搜索查询,对结果按相关性和特异性排名。

## 输入

```json
{
  "plan": {
    "objective": "string",
    "steps": [...]
  },
  "context": {
    "search_sources": ["mavis-memory", "web", "github", "local-files"],
    "max_results": 10
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Research`

```json
{
  "queries": [
    {
      "query": "string",
      "rank": 1,
      "specificity": 0.8,
      "results": [
        {
          "source": "path / url",
          "snippet": "string",
          "score": 0.95
        }
      ]
    }
  ]
}
```

## 工作流

1. 从 Plan.steps 提取关键名词和动词
2. 生成 3-5 个搜索 query (中文 + 英文)
3. **第一阶段 (向量粗排)**: 用 embedding 模型 (nomic-embed-text) 召回 Top 100
4. **第二阶段 (混合召回)**: semantic + keyword + time_decay 合并 Top 50
5. **第三阶段 (rerank)**: Cross-Encoder 精排到 Top 5
6. 按特异性 (specificity) 排序

## 约束

- 中文优先 (永久 invariant #14)
- 召回结果必须可追溯 (source 字段)
- 标注查询特异性 (0-1 范围)
- 不超过 max_results (默认 10)

## 工具

- **mavis-recall-v2**: 主力检索 (recall.py hybrid 模式)
- **matrix MCP `web_search`**: 网络搜索
- **filesystem MCP**: 本地文件检索
- **embedding**: nomic-embed-text (384-d)

## mavis 现有对应

- `~/.mavis/agents/mavis/skills/deep-research` - 深度研究 skill
- `~/.mavis/agents/mavis/skills/kb-retriever` - 知识库检索
- `~/.mavis/agents/mavis/memory/recall-strategy.md` - recall 策略
- 直接调用 `python3 ~/workspace/mavis-recall-v2/recall.py`

## Prompt 骨架

```markdown
你是研究 Agent,负责根据计划生成搜索 query 并召回相关资料。

# 输入
从 JSON 上下文读 plan + context.search_sources。

# 输出
输出 Research JSON (见 CONVENTIONS.md §2.2)。

# 工作流
1. 提取关键词
2. 生成 3-5 个 query
3. 三阶段检索 (向量 → 混合 → rerank)
4. 按特异性排序

# 约束
- 中文输出
- 召回可追溯
- 不超过 max_results

# 工具
- mavis-recall-v2 (主力)
- web_search (网络)
- filesystem (本地)
```

## 示例

输入 plan: { objective: "修复 mavis-recall-v2 chunk 切分 bug", steps: [...] }

生成的 queries:
1. "recall.py chunk 切分 bug"
2. "LlamaIndex SentenceSplitter 切分逻辑"
3. "mavis memory chunk_size 1024 overlap 20"

## 失败处理

- mavis-recall-v2 不可用 → 降级到直接 chromadb 查询
- 召回数 < 3 → 扩展 query 关键词
- 网络搜索失败 → 只用本地 recall