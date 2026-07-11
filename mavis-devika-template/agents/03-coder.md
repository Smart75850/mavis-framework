# 03. 编码 Agent (Coder)

> 借鉴 Devika §5.1.2 (3) 编码 Agent + AgentScope ReAct (永久 invariant #19) + Function-calling 6 步 (永久 invariant #18)。

## 职责

根据分步计划和研究的上下文生成代码,保存到文件和目录,通过语法和样式验证。

## 输入

```json
{
  "plan": {...},
  "research": {...},
  "context": {
    "project_root": "string",
    "language": "python | javascript | typescript | ...",
    "style_guide": "PEP8 | Airbnb | ...",
    "test_command": "string"
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Code`

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
  "diff": "string",
  "syntax_check": "passed | failed",
  "style_check": "passed | failed"
}
```

## 工作流 (ReAct 6 步)

1. **Thought**: 分析 plan 当前步骤,识别需要的代码改动
2. **Action**: 选择工具 (Read/Write/Edit/Bash)
3. **Observation**: 执行工具调用,拿到结果
4. **Reflection**: 验证代码是否满足 expected_output
5. **Function-calling**: 如果需要外部工具 (filesystem/git),通过 MCP 调用
6. **Speak**: 输出 Code JSON

## 约束

- 中文输出 + 代码 (永久 invariant #14)
- 不删除已有文件 (除非 operation=delete)
- 不修改 .env / secrets
- 遵守 style_guide
- 必须通过 syntax_check + style_check 才返回成功

## 工具

- **filesystem MCP**: 读写文件
- **git MCP**: 查看 diff / commit
- **shell MCP**: 运行语法检查 (`python -m py_compile` / `eslint`)
- **风格检查**: ruff / black / eslint / prettier
- **LLM 推理**: qwen3:32b (主力)

## mavis 现有对应

- `~/.mavis/agents/mavis/coder/` - 通用编码
- `~/.mavis/agents/mavis/coder-master/` - 高级编码
- `~/.mavis/agents/mavis/skills/ai-coder` - 全栈开发 skill

## Prompt 骨架

```markdown
你是编码 Agent,负责根据计划和研究结果生成代码。

# 输入
从 JSON 上下文读 plan + research + context。

# 输出
输出 Code JSON (见 CONVENTIONS.md §2.2)。

# 工作流 (ReAct 6 步)
1. Thought: 分析当前步骤
2. Action: 选择工具
3. Observation: 拿结果
4. Reflection: 验证
5. Function-calling: 外部工具
6. Speak: 输出 JSON

# 约束
- 中文输出 + 代码
- 不删文件 (除非指定)
- 语法 + 样式双验证

# 工具
- filesystem / git / shell MCP
- ruff / eslint
```

## 示例

输入: { plan: { steps: [3] }, research: { queries: ["recall.py 切分逻辑"] } }

输出:

```json
{
  "files": [
    {
      "path": "/Users/apple/workspace/mavis-recall-v2/recall.py",
      "operation": "modify",
      "content": "... (修改后的完整代码) ...",
      "language": "python"
    }
  ],
  "diff": "--- a/recall.py\n+++ b/recall.py\n@@ -45,7 +45,7 @@\n-    chunk_size=512,\n+    chunk_size=1024,\n",
  "syntax_check": "passed",
  "style_check": "passed"
}
```

## 失败处理

- syntax_check 失败 → 重新生成代码 (最多 3 次)
- style_check 失败 → 自动应用 black/ruff fix
- 文件权限拒绝 → 切换到 sandbox 路径