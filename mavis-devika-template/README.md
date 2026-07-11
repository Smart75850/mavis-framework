# mavis Devika 9 大 Agent 模板

> 借鉴高强文《大模型项目实战》第 5 章 §5.1 Devika 的 9 大 Agent 架构,沉淀到 mavis sub-agent 体系。

## 设计理念

**不是新建 9 个独立 sub-agent,而是定义 9 个标准化角色模板**:
- 创建新 mavis sub-agent 时,先看属于 9 个角色里的哪个
- 复用对应角色的职责描述 + 输入输出契约 + 上下文 schema
- 避免每次创建 agent 都从零设计 prompt 和接口

## 9 大 Agent 角色 (Devika 原文 §5.1.2)

| # | Agent | 一句话职责 | mavis 现有对应 | 输入 | 输出 |
|---|-------|----------|---------------|------|------|
| 1 | 规划 Agent | 用户指令 → 分步计划 | `team-architect` / `mavis-team-v2 planner` | 用户原始需求 | `Plan {steps[]}` |
| 2 | 研究 Agent | 计划 → 检索 + 排名 | `analyst` / `mavis-recall-v2` | Plan + 上下文 | `Research {queries, ranked[]}` |
| 3 | 编码 Agent | 计划 + 研究 → 代码 | `coder` / `coder-master` | Plan + Research | `Code {files[], diff}` |
| 4 | 行动 Agent | 用户后续指令 → 操作关键字 | `action-router` (待建) | 用户 intent | `Action {keyword, args}` |
| 5 | 运行 Agent | 代码 → 沙盒执行结果 | `mavis-cu` (computer use) | Code | `RunResult {stdout, stderr, exit_code}` |
| 6 | 新特性 Agent | 新需求 → 增量代码 | `feature-builder` (待建) | Plan + 现有代码 | `Feature {diff, tests}` |
| 7 | 补丁 Agent | 错误 → 修复代码 | `lint-master` / `verifier` | Error + Code | `Patch {diff, explanation}` |
| 8 | 报告 Agent | 项目状态 → 综合报告 | `scribe` / `reporter` | 完整执行历史 | `Report {markdown, pdf}` |
| 9 | 决策 Agent | 特殊指令 → 函数调用 | `devil-advocate` / 路由层 | 异常指令 | `Decision {function, params}` |

## 上下文流转

```
[用户指令]
    ↓
[1 规划 Agent] → Plan
    ↓
[2 研究 Agent] → Research
    ↓
[3 编码 Agent] → Code
    ↓
[5 运行 Agent] → RunResult ──┐
    ↓                        │
[4 行动 Agent] (判断继续)   │
    ↓                        │
[6 新特性 / 7 补丁] ←────────┘
    ↓
[8 报告 Agent] → Report
    ↓
[9 决策 Agent] (处理特殊指令)
```

## 文件结构

```
mavis-devika-template/
├── README.md                # 本文件 - 总览
├── CONVENTIONS.md           # 通用约定 (LLM 接口 + JSON 上下文 schema + prompt 骨架)
├── agents/                  # 9 个 Agent 角色模板
│   ├── 01-planner.md
│   ├── 02-researcher.md
│   ├── 03-coder.md
│   ├── 04-action.md
│   ├── 05-runner.md
│   ├── 06-feature.md
│   ├── 07-patcher.md
│   ├── 08-reporter.md
│   └── 09-decision.md
└── examples/
    ├── recall-v2-bug-fix.md            # 设计图 demo (概念演示)
    └── e2e-validation-report-2026-07-10.md # 真实验证报告 (真实工具链跑通)
```

## 使用方法

### A. 创建新 sub-agent 时

1. 先看新 agent 的职责,确定属于 9 个角色里的哪个 (可能是 1 个主角色 + 几个辅助角色)
2. 打开对应 `agents/XX-name.md` 模板
3. 复制**职责定义** + **输入输出契约** + **JSON 上下文字段** + **prompt 骨架**
4. 填入具体场景 (例如: mavis-recall 专属的 recall 逻辑)

### B. 编排多 Agent 协作时

1. 打开 `CONVENTIONS.md` 里的**上下文流转 schema**
2. 确认每个 Agent 的输入输出字段在 schema 里都能找到
3. 用 `mavis-team-v2` 或者直接 `mavis communication send` 编排

### C. 复用 mavis 现有 sub-agent

- 30+ 现有 sub-agent 都可以归类到这 9 个角色里
- 详见每个 agent 模板里的 "mavis 现有对应" 字段
- 不重复造轮子,新场景优先复用现有 agent

## 与永久 invariant 的关系

- **Invariant #1 (Agent 4 大组件)**: 每个角色模板都标注 Planning/Memory/Tools/Action 4 大组件
- **Invariant #21 (LangGraph StateGraph = mavis team plan DAG)**: 9 大 Agent 编排用 LangGraph StateGraph 实现
- **Invariant #30 (mavis recall v2)**: 研究 Agent 直接调用 mavis-recall-v2

## 下一步

- [x] 创建 9 个 agent 模板文件 (agents/01-09.md)
- [x] 创建 CONVENTIONS.md (通用约定)
- [x] 创建端到端 demo (examples/recall-v2-bug-fix.md 设计图 + e2e-validation-report 真实验证)
- [x] 验证 demo 跑通 (用 recall v2 / team plan v2 / verifier v2 实际执行,见验证报告)
- [x] 更新 mavis memory (#31 invariant) + knowledge-galaxy (+12 节点)