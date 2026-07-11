# 2 本书核心总结 (贴任何 AI 都识我哋读过, 2026-07-10)

> **用法**: 大佬喺任何新 AI 第一条消息贴呢个文件, 咁个 AI 就会知道我哋读过呢 2 本书 + 31 个永久 invariant。

---

## 我哋读过嘅 2 本书

### 书 1: 黄佳《让 Claude Code 带你学 Claude Code》 (10 章闭环扫读, 2026-07-09)

**核心内容**:
- 第 1-3 章: Harness 4 层架构 (System / Developer / User / Tool Result)
- 第 4 章: Hooks 5 事件 × 3 类型 (PreToolUse / PostToolUse / Stop)
- 第 5 章: Agent SDK (chat / run / resume / fork_session)
- 第 6 章: MCP 8 核心概念 + 4 接入点
- 第 7 章: Headless + CI/CD (cron / active-hours / max-turns)
- 第 8 章: Agent SDK 实战
- 第 9 章: Plugins 生态
- 第 10 章: 工程化实战 (SDD 4 层 + 8 机制协奏)

**mavis 永久 invariant #1-#8** (从本书提炼):
- 量化 prompt + 反问 fallback
- 跑 LangChain/CrewAI/AutoGen 4 大通用前置 (socksio + qwen3:32b + AutoGen model_info + CrewAI max_execution_time=600)
- 整片 verify 铁律 (发出去前自己 verify)
- Recall 优先级 protocol (先 recall memory 再 web_search)
- Answer transparency header (📌 来源 | 验证 | 适用)
- Web 搜索年份铁律 (用 2026)
- 沟通铁律 v4 加强版 (严格正规普通话)
- mavis 8 机制协奏: CLAUDE.md + 子智能体 + Skills + Hooks + MCP + Headless + Agent SDK + Plugins

### 书 2: 高强文《大模型项目实战: Agent 开发与应用》 (16 章完整扫读, 2026-07-10)

**核心内容**:
- 第 1-2 章: Agent 基础 (4 大组件 + 4 思考框架 + 3 LLM 服务)
- 第 3-6 章: 6 大应用 (AutoGPT/MemGPT/BabyAGI/Camel/Devika/CodeFuse/DB-GPT/QAnything)
- 第 7 章: GLM-4/Llama3 微调 (LoRA + PEFT 合并)
- 第 8-16 章: 9 大开发框架 (Function-calling/ReAct/Plan-Execute/LangGraph/AutoGen/LlamaIndex/CrewAI/Qwen-Agent/CogVLM2)

**mavis 永久 invariant #9-#26** (从本书提炼):
- #9: Agent 4 大组件架构 (Planning/Memory/Tools/Action)
- #10: LLM 服务 3 选 1 (Ollama/vLLM/GLM-4)
- #11: OpenAI 兼容接口 3 大端点
- #12: AutoGPT 兼容名技巧 (--served-model-name gpt-3.5-turbo)
- #13: MemGPT 虚拟上下文 = mavis 5 层记忆
- #14: OUTPUT IN CHINESE 强制中文
- #15: AWEL 3 层架构 (算子/DSL/AgentFrame)
- #16: 两阶段检索 (向量 + rerank)
- #17: LoRA 微调 + PEFT 模型合并
- #18: Function-calling 6 步流程
- #19: ReAct 3 要素 (thought/speak/function)
- #20: Plan-and-Execute 4 阶段
- **#21 ⭐**: LangGraph StateGraph = mavis team plan DAG (业界 SOTA 验证)
- #22: AutoGen 嵌套对话 = mavis verifier
- #23: LlamaIndex 4 步索引 = mavis memory
- #24: CrewAI 4 组件 = mavis team plan
- #25: Qwen-VL 流式推理
- #26: CogVLM2 以文搜图

**mavis 5 大改造项目 (今晚应用, #27-#30)**:
- mavis-recall-v2: 借鉴 LlamaIndex + QAnything + AWEL
- mavis-verifier-v2: 借鉴 AutoGen 嵌套对话
- mavis-team-plan-v2: 借鉴 LangGraph StateGraph
- mavis-babyagi: 借鉴 BabyAGI 6 步循环
- mavis-langgraph: 验证 mavis team plan = LangGraph DAG

**mavis 协议 (#31)**:
- 任何新 mavis session 启动必跑 `mavis-init`
- 加载 HANDOFF + 31 永久 invariant + 5 改造

---

## 大佬 31 个永久 invariant (浓缩表)

| # | 类别 | Invariant |
|---|---|---|
| 1-8 | 黄佳本书 | 量化 + 反问 + 4 大前置 + verify + recall + transparency + 2026 + v4 普通话 + 8 机制 |
| 9-11 | 基础 | Agent 4 组件 + LLM 3 选 1 + OpenAI 3 端点 |
| 12-17 | 应用 | 兼容名 + 5 层记忆 + OUTPUT IN CHINESE + AWEL + 两阶段检索 + LoRA |
| 18-26 | 开发 | Function-calling 6 步 + ReAct 3 要素 + Plan-Execute 4 阶段 + **LangGraph ⭐** + AutoGen + LlamaIndex + CrewAI + Qwen-VL + CogVLM2 |
| 27-31 | mavis | 验证 + BabyAGI + recall v2 + init 协议 |

---

## 沟通铁律 (贴任何 AI 都要遵守)

- **严格正规普通话** (唔夹杂英文/粤语/闽南语/上海话)
- 称呼: **大佬**
- 短句 + 直接 + 必要时举例
- 语气词保留: 啊/嘛/吧/呢/嗯/行/好

---

## mavis 5 大改造 (今晚真正跑通)

```
~/workspace/mavis-recall-v2/recall.py           233 行, LlamaIndex 4 步 + QAnything 2 阶段
~/workspace/mavis-verifier-v2/verifier.py       4908 bytes, AutoGen 嵌套对话
~/workspace/mavis-team-plan-v2/team_plan_v2.py  191 行, LangGraph StateGraph
~/workspace/mavis-babyagi/babyagi.py            4103 bytes, BabyAGI 6 步
~/workspace/mavis-langgraph/langgraph-sample.py  3208 bytes, 对比 demo
```

**5 个测试 100% 通过** ✅

---

## 适用场景

- 大佬喺新 mavis session 启动: 跑 `mavis-init`
- 大佬喺 Claude.ai / GPT-4 / Gemini: 贴呢个文件嘅内容
- 大佬喺新 device: 复制 HANDOFF-2026-07-10.md + 呢个文件

---

**大佬嘅心血: 2 本书 + 31 永久 invariant + 5 大改造**。
EOFMARKER
cp /Users/apple/workspace/mavis-handoff/2BOOKS-SUMMARY-FOR-ANY-AI.md /Users/apple/Desktop/🚨-START-HERE-高强文书-Agent开发/2本书总结-贴任何AI.md
ls -la /Users/apple/workspace/mavis-handoff/2BOOKS-SUMMARY-FOR-ANY-AI.md /Users/apple/Desktop/🚨-START-HERE-高强文书-Agent开发/2本书总结-贴任何AI.md