# 05. 运行 Agent (Runner)

> 借鉴 Devika §5.1.2 (5) 运行 Agent + CodeFuse-ChatBot 沙盒设计。

## 职责

在沙盒环境执行 AI 编写的代码,适配不同操作系统 (macOS / Linux / Windows),实时流式输出命令结果,处理错误和异常。

## 输入

```json
{
  "code": {
    "files": [...],
    "language": "python | javascript | ..."
  },
  "context": {
    "sandbox": "local | docker | none",
    "command": "string (可选, 例如: pytest)",
    "timeout_seconds": 180
  }
}
```

## 输出

见 `CONVENTIONS.md §2.2 RunResult`

```json
{
  "exit_code": 0,
  "stdout": "string",
  "stderr": "string",
  "duration_ms": 1234,
  "sandbox": "local | docker | none",
  "stream_url": "string (可选)"
}
```

## 工作流

1. 校验沙盒可用性 (local 检查 PATH / docker 检查 daemon)
2. 决定执行模式:
   - **直接执行** (脚本类): `python3 script.py`
   - **测试执行** (test mode): `pytest tests/`
   - **部署执行** (deploy mode): `kubectl apply` / `git push`
3. **流式输出** (WebSocket): stdout/stderr 实时推送给用户
4. **超时处理**: 超时强制 kill,记录超时时长
5. **错误捕获**: 异常 exit_code != 0 → 触发 07-patcher

## 约束

- 沙盒隔离 (避免污染主环境)
- 强制 timeout (默认 180 秒)
- macOS / Linux / Windows 兼容
- 不执行破坏性命令 (`rm -rf /`, `mkfs`, etc.)
- 流式输出必须支持中文

## 工具

- **shell MCP**: 执行 shell 命令
- **playwright MCP**: 浏览器操作 (browse 命令)
- **filesystem MCP**: 文件读写
- **mavis-cu (Computer Use)**: 桌面 GUI 自动化

## mavis 现有对应

- `mavis-cu` MCP server - Computer Use (25 个桌面工具)
- `~/.mavis/agents/mavis/skills/comfyui-workflow-recipe` - workflow 启动
- 暂时没有专门 sub-agent,需要新建

## 沙盒策略

| sandbox | 适用场景 | 实现 |
|---------|---------|------|
| `local` | 测试 / 验证 | 直接 subprocess.run + timeout |
| `docker` | 部署 / 隔离 | docker run + bind mount |
| `none` | 纯函数 (无副作用) | 跳过执行,只验证语法 |

## Prompt 骨架

```markdown
你是运行 Agent,负责在沙盒里执行代码。

# 输入
从 JSON 上下文读 code + context。

# 输出
输出 RunResult JSON (见 CONVENTIONS.md §2.2)。

# 工作流
1. 校验沙盒
2. 决定执行模式
3. 流式输出
4. 超时处理
5. 错误捕获

# 约束
- 沙盒隔离
- 强制 timeout 180s
- 不执行破坏性命令

# 工具
- shell / playwright / filesystem / cu MCP
```

## 示例

输入: { code: { files: [{path: "test_recall.py"}] }, context: { command: "pytest test_recall.py -v", timeout_seconds: 60 } }

输出:

```json
{
  "exit_code": 0,
  "stdout": "test_recall.py::test_hybrid PASSED\ntest_recall.py::test_rerank PASSED\n====== 2 passed in 1.23s ======",
  "stderr": "",
  "duration_ms": 1234,
  "sandbox": "local"
}
```

## 失败处理

- 沙盒不可用 → fallback 到 `none` (只验证语法)
- 超时 → 强制 kill,记录 stderr,触发 07-patcher
- exit_code != 0 → 路由到 07-patcher,带上 stderr
- 破坏性命令 → 拒绝执行,返回 NEEDS_CONFIRM