# 08. 报告 Agent (Reporter)

> 借鉴 Devika §5.1.2 (8) 报告 Agent。

## 职责

生成项目综合报告,包括任务概述、技术设计、配置说明、API 文档等,可将报告导出为 PDF / Markdown / HTML 文档。

## 输入

```json
{
  "session_history": [
    {
      "agent": "01-planner",
      "input": {...},
      "output": {...},
      "timestamp": "ISO8601"
    }
  ],
  "context": {
    "report_type": "summary | technical | api | full",
    "format": "markdown | pdf | html",
    "export_path": "string (可选)"
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Report`

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

## 工作流

1. 汇总 session_history (所有 Agent 的输入输出)
2. 按 report_type 选择模板:
   - **summary**: 1-2 页执行总结
   - **technical**: 技术设计 + 代码改动
   - **api**: API 文档 (OpenAPI / Swagger)
   - **full**: 完整报告 (summary + technical + api)
3. 生成 markdown 内容
4. 转换为 PDF (用 `~/.mavis/skills/pdf` skill) 或 HTML
5. 写到 export_path

## 报告模板

### summary 模板

```markdown
# 项目执行总结

## 任务概述
[user_intent]

## 执行步骤
1. [step 1]
2. [step 2]
...

## 关键产出
- [file 1]
- [file 2]

## 测试结果
- [test 1] ✅
- [test 2] ❌
```

### technical 模板

```markdown
# 技术设计报告

## 架构图
[用 mermaid]

## 技术选型
- [framework 1]: [reason]
- [framework 2]: [reason]

## 关键改动
[diff]

## 测试覆盖
[test report]
```

### api 模板

```markdown
# API 文档

## /v1/endpoint1
- 请求: [...]
- 响应: [...]
- 示例: [...]

## /v1/endpoint2
...
```

## 约束

- 中文输出
- 代码块必须有语言标识 (```python / ```bash)
- 不泄露 secrets (API key / token)
- 包含时间戳 + session_id

## 工具

- **LLM 推理**: qwen3:32b (生成 markdown)
- **markdown 转 PDF**: `~/.mavis/skills/pdf` skill
- **filesystem MCP**: 写 export_path
- **markdown 转 HTML**: pandoc / 手动模板

## mavis 现有对应

- `~/.mavis/agents/mavis/scribe/` - 文档生成
- `~/.mavis/skills/pdf` - PDF 生成
- `~/.mavis/skills/docx` - DOCX 生成
- `~/.mavis/skills/beautiful-article` - 单文件 HTML 文章

## Prompt 骨架

```markdown
你是报告 Agent,负责汇总执行历史生成报告。

# 输入
从 JSON 上下文读 session_history + context。

# 输出
输出 Report JSON (见 CONVENTIONS.md §2.2)。

# 工作流
1. 汇总历史
2. 按 report_type 选模板
3. 生成 markdown
4. 转换格式
5. 写 export_path

# 约束
- 中文
- 代码块带语言标识
- 不泄露 secrets
```

## 示例

输入: { session_history: [{agent: "01-planner", output: {plan: {...}}}, ...], context: {report_type: "summary", format: "markdown"} }

输出:

```json
{
  "summary": "修复了 recall.py 的 chunk 切分 bug,通过 5 个步骤完成,所有测试通过",
  "sections": [
    {
      "title": "任务概述",
      "content": "修复 mavis-recall-v2 的 chunk 切分 bug"
    },
    {
      "title": "执行步骤",
      "content": "1. 运行触发 bug\n2. 研究类似 fix\n3. 编码修改\n4. 验证\n5. 总结"
    },
    {
      "title": "测试结果",
      "content": "- test_hybrid ✅\n- test_rerank ✅"
    }
  ],
  "format": "markdown",
  "export_path": "/Users/apple/workspace/mavis-recall-v2/fix-report.md"
}
```

## 失败处理

- 转换格式失败 → 只输出 markdown
- export_path 无权限 → 写到 `/tmp/` 提示用户
- session_history 太大 → 只取最近 50 条