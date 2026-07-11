# 09. 决策 Agent (Decision Router)

> 借鉴 Devika §5.1.2 (9) 决策 Agent + Function-calling 6 步流程 (永久 invariant #18)。

## 职责

处理不适合其他 Agent 处理的特殊指令,将命令映射到特定功能 (git clone、浏览器交互等),使用特定参数执行相应函数。

## 输入

```json
{
  "command": "string (特殊指令, 例如: git clone ...)",
  "context": {
    "available_functions": [
      {
        "name": "git_clone",
        "params": ["url", "target_dir"],
        "description": "克隆 GitHub 仓库"
      }
    ]
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 Decision`

```json
{
  "function": "string",
  "params": {},
  "fallback": "string (可选)"
}
```

## 工作流 (Function-calling 6 步)

1. **解析指令**: 识别是哪种特殊指令
2. **匹配函数**: 从 available_functions 找匹配的 function
3. **提取参数**: 用 LLM 提取 function params
4. **校验参数**: 类型 + 必填字段校验
5. **执行函数**: 通过 MCP server 调用
6. **返回结果**: 输出 Decision JSON

## 特殊指令清单

| 指令 (中文) | function | 必需 params | 可选 params |
|-----------|----------|-------------|------------|
| git clone / 克隆仓库 | `git_clone` | url, target_dir | branch |
| 打开网页 / 访问 URL | `browser_navigate` | url | wait_until |
| 截图网页 | `browser_screenshot` | url | path, full_page |
| 发送邮件 | `send_email` | to, subject, body | cc, attachments |
| 创建日历事件 | `create_calendar_event` | title, start_time | duration_minutes |
| 发送飞书消息 | `send_lark_message` | chat_id, content | msg_type |
| 查 GitHub issue | `github_list_issues` | repo | state, labels |
| 创建 PR | `github_create_pr` | repo, title, body | base, head |
| 部署 Netlify | `deploy_netlify` | project_dir | site_name |
| 跑 SQL 查询 | `run_sql_query` | query | database_url |

## 与 04-action 的区别

| 维度 | 04-action | 09-decision |
|------|-----------|-------------|
| 触发 | 用户后续指令 | 通用特殊指令 |
| 复杂度 | 简单关键字匹配 | 复杂参数提取 |
| 模型 | llama3 (快) | qwen3:32b (准) |
| 函数库 | 内置 6 个 | 外挂 (可扩展) |
| Fallback | 路由到 run | 直接执行或拒绝 |

## 约束

- 必须从 available_functions 选 (不凭空创造)
- 参数必须类型匹配
- 不执行危险函数 (没有 delete_repo / drop_database 这类)
- 中文输出
- 失败时返回 fallback 字段

## 工具

- **git MCP**: git clone / push / commit
- **playwright MCP**: browser 操作
- **lark-tools**: 飞书集成
- **github MCP**: GitHub API
- **filesystem MCP**: 文件操作

## mavis 现有对应

- `~/.mavis/agents/mavis/devil-advocate/` - 决策辅助
- `~/.mavis/agents/mavis/system-architect/` - 架构决策
- `~/.mavis/agents/mavis/cron-master/` - 定时任务
- `~/.mavis/skills/lark-tools` - 飞书全套
- `mavis-cu` - 桌面控制

## Prompt 骨架

```markdown
你是决策 Agent,负责处理特殊指令 + 函数调用。

# 输入
从 JSON 上下文读 command + context.available_functions。

# 输出
输出 Decision JSON (见 CONVENTIONS.md §2.2)。

# 工作流 (Function-calling 6 步)
1. 解析指令
2. 匹配函数
3. 提取参数 (LLM)
4. 校验参数
5. 执行函数 (MCP)
6. 返回结果

# 约束
- 从 available_functions 选
- 参数类型匹配
- 不执行危险函数
- 失败返回 fallback
```

## 示例

输入: { command: "克隆 https://github.com/foo/bar 到 ~/code/", context: { available_functions: [{name: "git_clone", params: ["url", "target_dir"]}] } }

输出:

```json
{
  "function": "git_clone",
  "params": {
    "url": "https://github.com/foo/bar",
    "target_dir": "/Users/apple/code/bar"
  },
  "fallback": null
}
```

输入: { command: "在飞书上给张三发消息说『代码已部署』", context: { available_functions: [{name: "send_lark_message", params: ["chat_id", "content"]}] } }

输出:

```json
{
  "function": "send_lark_message",
  "params": {
    "chat_id": "zhangsan_chat_id (需 lookup)",
    "content": "代码已部署"
  },
  "fallback": "如果查不到 chat_id,改用 send_email"
}
```

## 失败处理

- function 不在 available_functions → 返回 NEEDS_INPUT
- 参数缺失 → 反问用户补全
- 函数执行失败 → 用 fallback 字段记录替代方案
- 危险函数 → 拒绝 + 提示用户手动确认