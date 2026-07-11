# 06. 新特性 Agent (Feature Builder)

> 借鉴 Devika §5.1.2 (6) 新特性 Agent。

## 职责

根据用户要求实现新功能,修改已生成的项目文件,同时保持代码结构和样式,执行增量测试验证功能是否按预期工作。

## 输入

```json
{
  "plan": {...},
  "research": {...},
  "existing_code": {
    "files": [...],
    "structure": "tree"
  },
  "context": {
    "feature_spec": "string (新功能规格)",
    "preserve_style": true,
    "incremental_test": true
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Code` (增量修改)

```json
{
  "files": [
    {
      "path": "string",
      "operation": "create | modify",
      "content": "string (完整文件, 而非 diff)",
      "language": "string"
    }
  ],
  "diff": "string",
  "incremental_tests": [
    {
      "name": "string",
      "command": "string",
      "passed": true
    }
  ]
}
```

## 工作流

1. 扫描现有项目结构,识别受影响文件
2. 复用 03-coder 的能力生成新代码
3. **增量测试**: 只跑相关测试 (不全量)
4. 验证风格一致 (black/ruff + 命名约定)
5. 输出 Code JSON + 测试结果

## 与编码 Agent 的区别

| 维度 | 03-coder | 06-feature |
|------|----------|-----------|
| 输入 | plan + research | plan + research + existing_code |
| 行为 | 从零生成 | 修改现有项目 |
| 测试 | syntax + style | syntax + style + 增量测试 |
| 风格 | 任意 | 必须保持现有风格 |
| 输出 | Code JSON | Code JSON + incremental_tests |

## 约束

- 不破坏现有 API
- 不删除公开函数
- 增量测试必须 100% 通过
- 命名风格必须与现有代码一致 (snake_case / camelCase)
- 中文输出

## 工具

- 复用 03-coder 的所有工具
- **filesystem MCP**: 读现有代码
- **git MCP**: 看历史 commit 学习风格
- **shell MCP**: 跑增量测试 (`pytest tests/test_xxx.py`)

## mavis 现有对应

- 暂时没有专门 sub-agent
- 复用 `~/.mavis/agents/mavis/coder-master/` 的高级能力
- 扩展点: 加一个 `feature-builder` sub-agent

## Prompt 骨架

```markdown
你是新特性 Agent,负责在现有项目上加新功能。

# 输入
从 JSON 上下文读 plan + research + existing_code + context。

# 输出
输出 Code JSON + incremental_tests (见 CONVENTIONS.md §2.2)。

# 工作流
1. 扫描现有结构
2. 复用 03-coder 生成
3. 增量测试
4. 风格一致性验证

# 约束
- 不破坏 API
- 增量测试 100% 通过
- 风格一致
```

## 示例

输入: { existing_code: { files: [{path: "recall.py"}] }, feature_spec: "支持 time_decay 权重配置" }

输出:

```json
{
  "files": [
    {
      "path": "recall.py",
      "operation": "modify",
      "content": "... (修改后的完整代码, 添加 time_decay_weight 参数) ...",
      "language": "python"
    }
  ],
  "diff": "--- a/recall.py\n+++ b/recall.py\n@@ -10,6 +10,7 @@\n+    time_decay_weight: float = 0.3,\n",
  "incremental_tests": [
    {
      "name": "test_time_decay",
      "command": "pytest tests/test_recall.py::test_time_decay -v",
      "passed": true
    }
  ]
}
```

## 失败处理

- 增量测试失败 → 回滚 + 重新生成 (最多 3 次)
- 风格不一致 → 自动应用 black/ruff + 重命名
- API 破坏 → 返回 NEEDS_INPUT (问用户是否破坏兼容)