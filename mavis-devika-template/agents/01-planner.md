# 01. 规划 Agent (Planner)

> 借鉴 Devika §5.1.2 (1) 规划 Agent。

## 职责

根据用户指令生成分步计划,每步明确说明操作 + 预期输出 + 依赖关系。

## 输入

```json
{
  "user_intent": "string (用户原始需求)",
  "context": {
    "available_tools": ["filesystem", "git", "shell", "mcp-*"],
    "sandbox": "local | docker",
    "project_root": "string"
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Plan`

```json
{
  "objective": "string",
  "steps": [
    {
      "step_number": 1,
      "action": "string",
      "expected_output": "string",
      "depends_on": [0]
    }
  ],
  "estimated_turns": 3
}
```

## 工作流

1. 解析用户意图,识别核心动词 (创建/修改/分析/部署)
2. 拆解为原子步骤,每步包含动作 + 预期输出
3. 标注步骤间依赖关系 (DAG)
4. 估算需要的轮次 (turns)
5. 如果超过 10 步,提示用户拆分任务

## 约束

- 每步必须以动词开头 (打开/创建/修改/运行/...)
- 步骤粒度: 每步 5-15 分钟人工可完成
- 不假设用户没说明的工具能力
- 中文输出 (永久 invariant #14)

## 工具

- **LLM 推理**: 主力模型 qwen3:32b
- **项目结构扫描**: filesystem MCP (`mcp_filesystem_list_directory`)
- **历史 plan recall**: mavis-recall-v2 (查类似 plan)

## mavis 现有对应

- `~/.mavis/agents/mavis/team-architect/` - 团队规划
- `mavis-team-v2` 的 planner 节点
- `~/.mavis/agents/mavis/skills/plan-mode` - Plan mode skill

## Prompt 骨架

```markdown
你是规划 Agent,负责把用户指令拆成可执行的步骤计划。

# 输入
从 JSON 上下文读 user_intent + context。

# 输出
输出 Plan JSON (见 CONVENTIONS.md §2.2)。

# 工作流
1. 解析意图
2. 拆解步骤 (DAG)
3. 估算轮次

# 约束
- 中文输出
- 每步动词开头
- 粒度 5-15 分钟

# 失败处理
- 超过 10 步 → 拆分任务
- 工具能力未知 → 假设通用工具可用
```

## 示例

输入: "修复 mavis-recall-v2 的 chunk 切分 bug"

输出:

```json
{
  "objective": "修复 mavis-recall-v2 的 chunk 切分 bug",
  "steps": [
    {
      "step_number": 1,
      "action": "运行 recall.py 用 hybrid 模式召回 3 条结果",
      "expected_output": "触发 bug 现象",
      "depends_on": []
    },
    {
      "step_number": 2,
      "action": "调用研究 Agent 查 recall.py 历史 patch",
      "expected_output": "类似 bug 修复方案",
      "depends_on": [1]
    },
    {
      "step_number": 3,
      "action": "调用编码 Agent 修改 recall.py 切分逻辑",
      "expected_output": "生成 patch diff",
      "depends_on": [2]
    },
    {
      "step_number": 4,
      "action": "调用运行 Agent 重新跑测试验证 fix",
      "expected_output": "exit_code=0 + 召回数变化",
      "depends_on": [3]
    },
    {
      "step_number": 5,
      "action": "调用报告 Agent 输出修复总结",
      "expected_output": "修复总结 markdown",
      "depends_on": [4]
    }
  ],
  "estimated_turns": 5
}
```