# 07. 补丁 Agent (Patcher)

> 借鉴 Devika §5.1.2 (7) 补丁 Agent + AutoGen 嵌套对话 (永久 invariant #22) + mavis-verifier-v2。

## 职责

根据用户的描述或错误消息调试和修复问题,分析现有代码识别潜在根本原因并实施修复,解释所做的更改。

## 输入

```json
{
  "error": {
    "message": "string",
    "stack_trace": "string",
    "exit_code": -1
  },
  "existing_code": {
    "files": [...],
    "language": "string"
  },
  "context": {
    "root_cause_hint": "string (可选)",
    "test_command": "string"
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Patch`

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

## 工作流 (嵌套对话)

1. **第一轮 (诊断)**: 分析错误 + 现有代码,识别根本原因
2. **第二轮 (修复)**: 调用 03-coder 生成 patch
3. **第三轮 (验证)**: 调用 05-runner 跑测试
4. **第四轮 (审核)**: 调用 mavis-verifier-v2 审核 patch 质量
5. **循环**: 如果审核失败,反馈给 03-coder 重新生成 (max_turns=3)

## 根本原因分析框架

| 错误类型 | 诊断方法 | 修复策略 |
|---------|---------|---------|
| SyntaxError | 看代码 + traceback | 直接 syntax fix |
| ImportError | 查包名 + 版本 | pip install / 修改 import |
| AttributeError | 看 attribute 路径 | 添加属性 / 重命名 |
| TypeError | 看类型不匹配 | 类型转换 / 类型注解 |
| TimeoutError | 看耗时 + timeout | 增加 timeout / 优化算法 |
| TestFailure | 看断言信息 | 改实现 / 改测试 |

## 约束

- 必须解释 root_cause (不只是改代码)
- patch 必须通过原测试 + 新测试
- max_turns 3 (避免无限循环)
- 中文输出 + 代码

## 工具

- 复用 03-coder + 05-runner
- **mavis-verifier-v2**: 审核 patch
- **git MCP**: 看 git blame / git log 找历史 fix

## mavis 现有对应

- `~/.mavis/agents/mavis/lint-master/` - lint 修复
- `~/.mavis/agents/mavis/verifier/` - 审核
- `mavis-verifier-v2` - AutoGen 嵌套对话 (永久 invariant #22)

## Prompt 骨架

```markdown
你是补丁 Agent,负责诊断错误 + 修复 + 验证 + 审核。

# 输入
从 JSON 上下文读 error + existing_code + context。

# 输出
输出 Patch JSON (见 CONVENTIONS.md §2.2)。

# 工作流 (嵌套对话 4 轮)
1. 诊断 root_cause
2. 03-coder 生成 patch
3. 05-runner 验证测试
4. mavis-verifier-v2 审核
5. 失败 → 反馈 03-coder 重试 (max 3)

# 约束
- 必须解释 root_cause
- patch 通过原测试 + 新测试
- max_turns 3
```

## 示例

输入: { error: { message: "ImportError: No module named 'langchain_core.prompts'", stack_trace: "..." }, existing_code: { files: [{path: "recall.py"}] } }

输出:

```json
{
  "root_cause": "Devika 章 5 提到的 langchain 1.0+ 把 prompts 模块从 langchain 移到了 langchain_core,需要修改 import 路径",
  "fix": {
    "files": [
      {
        "path": "recall.py",
        "operation": "modify",
        "content": "... (完整修改后代码) ..."
      }
    ],
    "diff": "--- a/recall.py\n+++ b/recall.py\n@@ -5,7 +5,7 @@\n-from langchain.prompts import PromptTemplate\n+from langchain_core.prompts import PromptTemplate\n",
    "explanation": "langchain 1.0+ 重构了 prompts 模块,从 langchain.prompts 迁移到 langchain_core.prompts。这是永久坑 #1 (HANDOFF 第九节)。"
  },
  "tests": [
    {
      "name": "test_imports",
      "passed": true
    },
    {
      "name": "test_recall_basic",
      "passed": true
    }
  ]
}
```

## 失败处理

- 3 轮嵌套对话都失败 → 报告给 09-decision 决定 (回滚 / 人工介入)
- 测试无法跑 → 至少保证 syntax_check 通过
- root_cause 找不到 → 返回 NEEDS_INPUT (问用户更多上下文)