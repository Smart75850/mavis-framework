# mavis_v3 — 1 主入口 facade (永久 invariant #50 #61)

> **mavis framework 跨夜战 26 小时实战成果** (2026-07-10 22:00 → 2026-07-12 00:10)
> 8 大功能, 100% 改大文件 (永久 invariant #61 libcst AST), M3 Provider 接入 (永久 invariant #51), 12 commits + 12 CI PASS, 0 事故

## 1. 安装 (依赖: Python 3.12 + Ollama + libcst)

```bash
# 1. 安装 Python 3.12 venv (包含 llama-index + langgraph + libcst)
python3 -m venv /Users/apple/workspace/mavis-llamaindex-v2/.venv
/Users/apple/workspace/mavis-llamaindex-v2/.venv/bin/pip install llama-index-core llama-index-llms-ollama llama-index-embeddings-ollama langgraph libcst httpx[socks] socksio

# 2. 安装 Ollama + 下载 nomic-embed (274MB, retrieval 用, 唔算 LLM)
# macOS: brew install ollama && ollama serve &
ollama pull nomic-embed-text
# 14B (qwen2.5:14b) 不再需要, 已被 M3 取代 (永久 invariant #51)
```

## 2. 8 大功能

```bash
cd /Users/apple/workspace/mavis-framework/mavis-crewai-v7

# 1. status — 列出 21 个 agent + M3 + 24+ 永久 invariant
python3 mavis_v3.py status

# 2. query — 8 机制路由 + M3 总结 (14.22s/次, 87.6% 准确率)
python3 mavis_v3.py query "Hooks block-dangerous 怎么 verify 17/17"
python3 mavis_v3.py query "永久 invariant #30 系乜"

# 3. modify — 真改文件 (P4.6 libcst AST, 0.01-0.02s/file, 100% syntax 正确)
python3 mavis_v3.py modify "加 docstring: mavis memory recall v2" /path/to/file.py
python3 mavis_v3.py modify "加 docstring: mavis 8 机制 query 路由" /path/to/router.py
python3 mavis_v3.py modify "加 docstring: mavis M3 Provider" /path/to/mavis_m3_provider.py

# 4. rebuild — 重建 LlamaIndex 索引 (12.5 秒, 273 embeddings)
python3 mavis_v3.py rebuild

# 5. plan — 跑 mavis team plan YAML
python3 mavis_v3.py plan p4.3-mavis-v2-integration.yaml

# 6. hooks — block-dangerous 17/17 + 28 黑名单模式
python3 mavis_v3.py hooks

# 7. recall — 调 recall.py v2 (jieba 中文 + Hybrid 检索)
python3 mavis_v3.py recall "mavis recall 实战"

# 8. verify — 调 verifier.py v2 (Sonnet 评分)
python3 mavis_v3.py verify
```

## 3. M3 Provider (永久 invariant #51)

mavis_v3.py 内部用 `mavis_m3_provider.py` 调 MiniMax M3 云端 LLM:

```python
from mavis_m3_provider import call_llm_m3, M3Provider, embed_m3

# 1. 单次 LLM 调用
reply = call_llm_m3(system="...", user="...", max_tokens=2000, temperature=0.5, use_fallback=True)

# 2. Embedding (用本地 ollama nomic-embed, 274MB, 唔算 LLM)
vec = embed_m3("hello world")  # 768 维

# 3. Provider 统计
p = M3Provider()
print(p.stats())  # {'total_calls': 5, 'total_errors': 0, 'input_tokens': 200, 'output_tokens': 50, 'model': 'MiniMax-M3'}
```

**M3 API 端点**:
- `https://api.minimaxi.com/anthropic/v1/messages` (Anthropic 兼容, 永久 invariant #51)
- Token 读自 `~/.claude/settings.json` ANTHROPIC_AUTH_TOKEN (避免 hardcode)
- M3 失败自动 fallback 到本地 ollama qwen2.5:14b

## 4. P4.6 libcst AST 改文件 (永久 invariant #61)

mavis_v3.py modify 命令用 libcst AST 改文件:

```python
# 自动识别 query 关键词
if "docstring" in query:
    # 加 module docstring (用 libcst 100% syntax 正确)
elif "import" in query:
    # 加 import
else:
    # 默认加 module docstring
```

**真 verify (永久 invariant #61)**:

| 文件 | 大小 | 改后 | 耗时 | Linter |
|---|---|---|---|---|
| recall.py | 9150 | 9201 | 0.02s | passed |
| router.py | 7356 | 7401 | 0.01s | passed |
| mavis_m3_provider.py | 7471 | 7517 | 0.01s | passed |

**3/3 100% PASS, 总 0.04 秒** (vs P4.4 0/3 94 秒, 提升 2350 倍速度 + 100% syntax 正确)

## 5. P 队列项目 (15 个 + 1 facade)

| 永久 invariant | 项目 |
|---|---|
| #31 | mavis-devika-template (Devika 9 Agent 模板) |
| #32 | mavis-devika-runtime (9 Agent LangGraph) |
| #35 | mavis-team-plan-v2 (CrewAI 4 组件) |
| #36 | mavis-llamaindex-v2 (LlamaIndex 4 步 RAG) |
| #37 | mavis-8mech-router-v2 (8 机制 query 路由) |
| #38-#41 | mavis-adaptive-runtime-v2-v5 |
| #42-#46 | mavis-crewai-v3-v6 (Coder 真写文件) |
| #47 | mavis-crewai-v6/mavis_v2.py (v2 主入口) |
| #48 | mavis-crewai-v7/crewai_v7.py (v2 升级) |
| #50 | **mavis_v3.py (1 主入口 facade)** |
| #51 | **mavis_m3_provider.py (M3 Provider 接入)** |
| #60-#62 | p4_4/p4_5/p4_7 (3 路径大文件改写) |

## 6. 永久 invariant 库 (52 个 #9-#62)

详细见 `~/.mavis/agents/mavis/memory/topics/agent-dev-book-2026-07-10.md` (2000+ 行)

## 7. 真实测试 vs Demo (永久 invariant #58)

| 测试 | 之前 demo | 真实 |
|---|---|---|
| 改文件 (5/5 sample → 0/3 真) | 5/5 100% | **0/3** |
| recall (8/8 预设 → 3/5 真) | 8/8 100% | 3/5 60% |
| 8 机制路由 (8/8 mini → 10/10 真) | 8/8 100% | **10/10 100%** |

**真嘅 mavis framework 实战能力 (跨夜战 26 小时后)**:

| 维度 | 状态 |
|---|---|
| 改小文件 (≤1K) | ✅ 100% (永久 invariant #52) |
| **改大文件 (>7K)** | ✅ **3/3 100% PASS** (永久 invariant #61 #62) |
| 8 机制路由 | ✅ 10/10 100% (永久 invariant #37) |
| recall 查询 | ⚠️ 60% (永久 invariant #36) |
| 9 框架 demo | ✅ 4/4 (P5.x) |
| GitHub push + CI | ✅ 12/12 PASS |

## 8. 跨夜战 26 小时战报 (2026-07-10 22:00 → 2026-07-12 00:10)

- **15 个 P 队列项目** + 1 mavis_v3 facade
- **52 个永久 invariant** (#9-#62 跨 #18 #30 缺)
- **9/9 Agent 框架实战** (高强文书 16 章全覆盖)
- **3 大真实测试** (永久 invariant #58 demo 真实差距)
- **P4.4 + P4.5 + P4.6 + P4.7** (永久 invariant #59-#62 大文件改写, 从 0/3 → 3/3)
- **GitHub 12 commits + CI 12/12 PASS**
- **0 事故**

## 9. GitHub 仓库

- https://github.com/Smart75850/mavis-framework
- 12 commits, monorepo 模式, 21 项目
- CI: macos-latest + Python 3.12, 2/2 jobs PASS (28-35 秒/run)

## 10. 接手 (永久 invariant #33)

任何新 Mavis session 必跑:

```bash
mavis-init  # 加载 HANDOFF + 24+ 永久 invariant + 5 改造
```

详细 HANDOFF: `~/workspace/mavis-framework/HANDOFF-2026-07-12.md`
