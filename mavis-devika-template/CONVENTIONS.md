# mavis Devika 模板通用约定

> 9 大 Agent 角色模板共用的 LLM 接口 + JSON 上下文 schema + prompt 骨架。

## 1. LLM 接口约定

### 1.1 OpenAI 兼容 API

所有 Agent 都通过 OpenAI 兼容接口调用 LLM,统一 base URL:

```bash
# 本地 Ollama (兼容名)
OLLAMA_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama  # 任意非空字符串

# 远程 OpenAI
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxx
```

### 1.2 mavis 3 模型策略

| 模型 | 用途 | 适用 Agent |
|------|------|-----------|
| `qwen3:32b` | 主力推理 (复杂规划/编码/决策) | 规划 / 编码 / 决策 / 报告 |
| `llama3:8b-instruct-fp16` | 快速响应 (关键词抽取/分类) | 研究 / 行动 / 运行结果分析 |
| `glm4` / `nomic-embed-text` | Embedding | 研究 Agent 内部用 |

详见永久 invariant #10。

### 1.3 兼容名 alias

```bash
# ~/.zshrc
alias ollama-compat-qwen="ollama run qwen3:32b"
alias ollama-compat-llama3="ollama run llama3:8b-instruct-fp16"
```

详见永久 invariant #12。

## 2. JSON 上下文 Schema

9 大 Agent 之间通过统一 JSON 上下文传递数据。

### 2.1 顶层结构

```json
{
  "project_id": "string",
  "session_id": "string",
  "user_intent": "string",
  "plan": {...},
  "research": {...},
  "code": {...},
  "run_result": {...},
  "patch": {...},
  "report": {...},
  "decision": {...},
  "metadata": {
    "created_at": "ISO8601",
    "updated_at": "ISO8601",
    "version": "1.0"
  }
}
```

### 2.2 关键子结构

#### Plan (规划 Agent 输出)

```json
{
  "objective": "string",
  "steps": [
    {
      "step_number": 1,
      "action": "string (动词开头, 例如: 打开文本编辑器...)",
      "expected_output": "string",
      "depends_on": [0]
    }
  ],
  "estimated_turns": 3
}
```

#### Research (研究 Agent 输出)

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

#### Code (编码 Agent 输出)

```json
{
  "files": [
    {
      "path": "string",
      "operation": "create | modify | delete",
      "content": "string",
      "language": "string"
    }
  ],
  "diff": "string (unified diff)",
  "syntax_check": "passed | failed",
  "style_check": "passed | failed"
}
```

#### RunResult (运行 Agent 输出)

```json
{
  "exit_code": 0,
  "stdout": "string",
  "stderr": "string",
  "duration_ms": 1234,
  "sandbox": "local | docker | none",
  "stream_url": "string (可选, WebSocket)"
}
```

#### Patch (补丁 Agent 输出)

```json
{
  "root_cause": "string",
  "fix": {
    "files": [...],
    "diff": "string",
    "explanation": "string"
  },
  "tests": [
    {
      "name": "string",
      "passed": true
    }
  ]
}
```

#### Action (行动 Agent 输出)

```json
{
  "keyword": "run | test | deploy | patch | feature | report | clone | browse",
  "args": {},
  "target_agent": "string (路由到哪个 Agent)"
}
```

#### Report (报告 Agent 输出)

```json
{
  "summary": "string",
  "sections": [
    {
      "title": "string",
      "content": "string"
    }
  ],
  "format": "markdown | pdf | html",
  "export_path": "string"
}
```

#### Decision (决策 Agent 输出)

```json
{
  "function": "string (git_clone | browser_navigate | send_email | ...)",
  "params": {},
  "fallback": "string (可选, fallback 指令)"
}
```

## 3. Prompt 骨架

每个 Agent 的 prompt 都遵循以下结构:

```markdown
# 角色
你是 [Agent 名称],负责 [一句话职责]。

# 输入
[从统一 JSON 上下文读取字段,例如: {plan}]

# 输出
[生成统一 JSON 上下文里的某个字段,例如: {research}]

# 工作流
1. [步骤 1]
2. [步骤 2]
3. [步骤 N]

# 约束
- [约束 1]
- [约束 2]

# 工具
- [工具 1: 描述]
- [工具 2: 描述]

# 失败处理
- 如果 [场景],返回 [fallback JSON]
```

## 4. 错误处理约定

| 错误类型 | 处理 | 返回 JSON |
|---------|------|-----------|
| LLM 不可用 | 重试 3 次后切换兼容名 | `{error: "llm_unavailable", retry_count: 3}` |
| 上下文缺失 | 返回 NEEDS_INPUT | `{error: "needs_input", missing_fields: [...]}` |
| 执行超时 | 切到快速模型 | `{error: "timeout", switched_to: "llama3"}` |
| 沙盒执行失败 | 触发补丁 Agent | `{error: "execution_failed", stderr: "...", route_to: "patcher"}` |

## 5. 与 mavis 8 机制协奏

每个 Agent 都注册到 mavis 8 机制:

| 机制 | Agent 角色映射 |
|------|--------------|
| Agent SDK | 9 大 Agent 都是 Agent SDK 实例 |
| Memory | 每个 Agent 共享统一 JSON 上下文 |
| Tools | 通过 MCP server 调用 (filesystem/git/playwright/cu) |
| Hooks | 每个 Agent 都配 PreToolUse / PostToolUse hook |
| Skills | Agent 内部用 skill 完成子任务 |
| Sub-agents | 9 大 Agent 互相委派 |
| Teams | 通过 mavis-team-v2 编排 |
| Cron | 异步任务通过 cron 监控 |

## 6. 验证 checklist

创建新 Agent 后,跑以下验证:

- [ ] LLM 接口 (兼容名 + OpenAI API) 调通
- [ ] 输入 JSON 上下文字段完整
- [ ] 输出 JSON 上下文字段符合 schema
- [ ] Prompt 骨架 4 段齐全 (角色/输入输出/工作流/约束)
- [ ] 错误处理 4 种类型都覆盖
- [ ] 注册到 mavis 8 机制
- [ ] 跑通一个端到端 demo (见 examples/)