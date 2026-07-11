# 04. 行动 Agent (Action Router)

> 借鉴 Devika §5.1.2 (4) 行动 Agent。

## 职责

根据用户后续指令,确定要执行的适当操作,将意图映射到特定关键字。

## 输入

```json
{
  "user_intent": "string (后续指令, 例如: 运行 / 测试 / 部署)",
  "context": {
    "current_state": "running | idle | error",
    "available_actions": ["run", "test", "deploy", "patch", "feature", "report"]
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Action`

```json
{
  "keyword": "run | test | deploy | patch | feature | report",
  "args": {},
  "target_agent": "string (路由到哪个 Agent)"
}
```

## 工作流

1. 解析用户后续指令的意图
2. 匹配关键字 (关键词 + 同义词)
3. 提取参数 (args)
4. 路由到对应 Agent
5. 记录行动历史

## 关键字映射表

| 用户意图 (中文) | 关键字 | target_agent |
|----------------|--------|--------------|
| 运行 / 执行 / 跑一下 | `run` | 05-runner |
| 测试 / 验证 | `test` | 05-runner (test mode) |
| 部署 / 上线 | `deploy` | 05-runner (deploy mode) |
| 修一下 / 修复 | `patch` | 07-patcher |
| 加新功能 / 新增 | `feature` | 06-feature |
| 出报告 / 总结 | `report` | 08-reporter |
| git clone / 拉代码 | `clone` | 09-decision |
| 打开网页 / 截图 | `browse` | 09-decision |

## 约束

- 严格匹配关键字 (不支持模糊意图)
- 默认 fallback 到 `run` (最常用)
- 中文输出
- 路由前必须确认 target_agent 在 available_actions 里

## 工具

- **LLM 推理**: llama3:8b-instruct-fp16 (轻量, 快)
- **关键词分类**: 正则 + 同义词词典

## mavis 现有对应

- `mavis-team-v2` 的 executor 节点
- `mavis-cu` (computer use) 部分指令路由
- 暂时没有专门 sub-agent,需要新建

## Prompt 骨架

```markdown
你是行动 Agent,负责把用户后续指令路由到对应 Agent。

# 输入
从 JSON 上下文读 user_intent + context。

# 输出
输出 Action JSON (见 CONVENTIONS.md §2.2)。

# 工作流
1. 解析意图
2. 匹配关键字 (查表)
3. 提取参数
4. 路由到 target_agent

# 约束
- 严格匹配
- fallback 到 run
- target_agent 必须在 available_actions
```

## 示例

输入: "运行一下刚才那个脚本"

输出:

```json
{
  "keyword": "run",
  "args": {"script": "刚才那个脚本"},
  "target_agent": "05-runner"
}
```

输入: "git clone https://github.com/foo/bar"

输出:

```json
{
  "keyword": "clone",
  "args": {"url": "https://github.com/foo/bar"},
  "target_agent": "09-decision"
}
```

## 失败处理

- 意图模糊 → 反问用户 "你说的『那个』指哪个?"
- keyword 不在 available_actions → 提示用户可用操作
- target_agent 不存在 → fallback 到 09-decision (通用决策)