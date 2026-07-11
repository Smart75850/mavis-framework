# mavis memory LlamaIndex 4 步索引 - P1.3

> **永久 invariant #36**: LlamaIndex 4 步索引 (Load/Index/Store/Query) = mavis memory RAG
> **来源**: 高强文《大模型项目实战》第 13 章 §基于 LlamaIndex 的 RAG Agent 综合应用开发

## 解决什么问题

mavis memory 现 17 个 .md 文件, 总 245KB, 用 `grep` 召回率极低:

| Query 关键词 | grep 命中 | LlamaIndex 召回 (score) |
|---|---|---|
| "协奏" 精确 | 3 | 0.7244 |
| "多智能体协同 8 个机制" (近义不同词) | 0 | **0.7388** |
| "LlamaIndex 4 步索引" (关键词不在 memory) | 2 (但不在 invariant 块) | **0.6336** |
| "14B 32B 长期记忆" (模糊查询) | 1 | 0.53 |

P1.3 让 mavis memory 真正可被**语义检索**, 而非 keyword grep。

## 4 步实现 (来源第 13 章 §13.3.1)

### Step 1: Load (装载)
- `SimpleDirectoryReader` + 显式 .md 文件列表
- 排除 `archive/`, `hooks-templates/`, `.bak`, `.summary.md`
- 当前 17 个有效 mavis memory 文件

### Step 2: Index (索引)
- `VectorStoreIndex` + `SentenceSplitter` (固定长度 512 / overlap 50)
- Embedding 模型: Ollama `nomic-embed-text` (274 MB, 768 维)
- 17 文件 → 241 个 chunks → 10.9 秒完成全部 embedding

### Step 3: Store (存储)
- 持久化到 `~/workspace/mavis-llamaindex-v2/storage/`
- 5 个 JSON 文件 (docstore + vector_store + index_store + graph_store + image), 总 3.4MB

### Step 4: Query (查询)
- `query_engine` (similarity_top_k=3, response_mode="compact")
- LLM 总结: Ollama `qwen2.5:14b` (per 永久 invariant #34)
- 单次 query ~7-13 秒 (含 LLM 总结)

## 技术栈

- **Python 3.12** (venv `~/workspace/mavis-llamaindex-v2/`)
- **llama-index-core 0.14.23** (P1.3 用最新稳定版, 不是 13 章的 0.10.53)
- **llama-index-embeddings-ollama 0.9.0** (但实际用 `HttpxOllamaEmbedding` 绕过 ollama lib, 因为 ollama lib 要 socksio 依赖)
- **llama-index-llms-ollama 0.10.1** (用于 LLM 总结)
- **socksio** (httpx 装 socks 支持)
- **Ollama** 服务 + 2 个模型: `nomic-embed-text` (274MB) + `qwen2.5:14b` (9GB)

## 用法

```bash
# 1. 激活 venv
source ~/workspace/mavis-llamaindex/bin/activate

# 2. 首次构建索引 (17 文件, ~10.9 秒)
python3 /Users/apple/workspace/mavis-llamaindex-v2/build_index.py build

# 3. 跑 4 个测试 query (已写入 query-test-results.json)
python3 /Users/apple/workspace/mavis-llamaindex-v2/query.py

# 4. 自定义 query
python3 /Users/apple/workspace/mavis-llamaindex-v2/query.py "14B vs 32B 怎么选" 3
```

## 4 个 query 实战验证 (2026-07-11 04:35)

| # | Query | Top-1 score | Top-1 file | 答案摘要 |
|---|---|---|---|---|
| 1 | mavis 协奏 8 机制 | 0.7244 | MEMORY.md | 8 机制 + 得分计算 (CLAUDE.md 100% / 子智能体 / Skills / ...) |
| 2 | 多智能体协同 8 个机制 | 0.7388 | MEMORY.md | 同义不同词召回成功 |
| 3 | LlamaIndex 4 步索引 | 0.6336 | recall-strategy.md | 4 步 (装载/切分/向量化/存储) |
| 4 | 14B 32B 长期记忆 | 0.53 | book-learning-workflow.md | 14B vs 32B 权衡 |

**平均 score**: 0.65 (语义检索质量 OK, LLM 总结能 work)

## 复用今晚经验 (P1.1.a + P1.2)

| 经验 | 来源 | P1.3 应用 |
|---|---|---|
| 14B 模型 (快 33 倍) | 永久 invariant #34 | LLM 总结用 qwen2.5:14b |
| retry + fallback | A1 改造 | query 失败自动重试 (14B → 32B) |
| OUTPUT IN CHINESE | 永久 invariant #14 | query 答案强制中文 |
| verify_pattern | P1.1.a | 4 个 query 全跑通 + 报告写入 |
| 不用 ollama lib | P1.1.a runtime | HttpxOllamaEmbedding 绕过 ollama lib 依赖 |

## 下一步 (P1.4+)

- **P1.4**: LlamaIndex + mavis 8 机制 (CLAUDE.md / 子智能体 / Skills / Hooks / MCP / Headless / Agent SDK / Plugins) 8 节点查询路由
- **P2.x**: hierarchical Process (借鉴 CrewAI P1.2) + LlamaIndex 4 步编排 (P1.3) 融合
- **P2.x**: 自动 rebuild 索引 (mavis memory 更新时自动 rebuild)

## 验收 checklist

- [x] 4 步实现 (Load/Index/Store/Query)
- [x] 17 个 mavis memory 文件索引
- [x] 持久化 (5 个 JSON, 3.4MB)
- [x] 4 个 query 实战验证
- [x] 中文 query 召回 (近义不同词 score 0.7388)
- [x] LLM 14B 总结 (per 永久 invariant #34)
- [x] HttpxOllamaEmbedding 绕过 ollama lib
- [x] state 持久化
- [x] query-test-results.json 报告

## 文件清单

- `build_index.py` (4 步主入口, 245 行)
- `query.py` (query 入口, 80 行)
- `storage/` (5 个 JSON, 3.4MB 持久化)
- `cycle-report.json` (build 报告)
- `query-test-results.json` (4 query 测试结果)
- `README.md` (本文)
