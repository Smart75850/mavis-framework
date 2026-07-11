# mavis Devika 9 Agent Runtime

> 借鉴高强文书第 5 章 Devika 9 大 Agent + LangGraph StateGraph + 4 大改造,完整 9 Agent runtime MVP。  
> **完成日期**: 2026-07-10  
> **永久 invariant**: #21 (LangGraph StateGraph) + #22 (AutoGen 嵌套对话) + #30 (mavis recall v2) + #31 (Devika 9 Agent 模板) + **#32 (本 runtime)**

---

## 架构

```
[用户目标]
    ↓
START
    ↓
[01 Planner] ──┐
    ↓          │ StateGraph 9 节点
[02 Researcher]│ + 2 条件边
    ↓          │ + MemorySaver
[03 Coder]    │
    ↓          │
[05 Runner] ──┤
    ↓          │
[should_continue_after_runner]
    ├─ exit 0 → [08 Reporter] → END
    └─ fail → [07 Patcher]
                ↓
              [should_continue_after_patcher]
                ├─ approved → [08 Reporter] → END
                ├─ turns 超限 → [08 Reporter] → END
                └─ 未通过 + 未超限 → [05 Runner] (重试)

[04 Action] / [06 Feature] / [09 Decision] → [08 Reporter] → END
```

---

## 9 个节点 (Devika Agent 模板)

| # | 节点 | 实现 | 集成 4 大改造 |
|---|------|------|--------------|
| 01 | Planner | LLM 生成 3-5 步计划 JSON | 借鉴 mavis-team-plan-v2 (章节 #11) |
| 02 | Researcher | 调 mavis-recall-v2 hybrid | **改造 #1: mavis-recall-v2** ✅ |
| 03 | Coder | LLM 生成代码 markdown | 永久 invariant #19 ReAct |
| 04 | Action | 简化为路由到 Reporter | 后续扩展 router sub-agent |
| 05 | Runner | 模拟沙盒执行 (MVP) | 后续接 mavis-cu 真实沙盒 |
| 06 | Feature | 占位 | 后续实现增量功能 |
| 07 | Patcher | 调 mavis-verifier-v2 | **改造 #2: mavis-verifier-v2** ✅ |
| 08 | Reporter | 汇总状态生成报告 | 永久 invariant #19 |
| 09 | Decision | 占位 (function=no_op) | 后续接 lark-tools / cu |

---

## 文件结构

```
~/workspace/mavis-devika-runtime/
├── runtime.py            # 主入口 (StateGraph + 9 节点 + 2 条件边 + MemorySaver)
├── mavis-devika-state.json  # 状态文件 (LangGraph MemorySaver 持久化)
├── cycle-report.json     # Cycle 报告
└── examples/
    ├── test-patcher-path.py      # Patcher 路径测试 (Runner FAIL 触发)
    └── test-verifier-integration.py # 真实集成 verifier v2 测试
```

---

## 用法

### 基本运行

```bash
# 用 part03 conda env (因为 LangGraph 1.0.10 装在那里)
conda run -n part03 python ~/workspace/mavis-devika-runtime/runtime.py "<objective>" [max_turns]
```

### 示例

```bash
# 演示完整流程 (happy path)
conda run -n part03 python ~/workspace/mavis-devika-runtime/runtime.py "用 9 Agent 演示 LangGraph StateGraph 端到端流程" 3

# 跳过 verifier (快速测试)
MAVIS_DEVIKA_USE_VERIFIER=0 conda run -n part03 python ~/workspace/mavis-devika-runtime/runtime.py "..." 3

# 测试 Patcher 路径
conda run -n part03 python ~/workspace/mavis-devika-runtime/runtime.py/examples/test-patcher-path.py

# 真实 verifier 集成
conda run -n part03 python ~/workspace/mavis-devika-runtime/runtime.py/examples/test-verifier-integration.py
```

### 输入参数

| 参数 | 必填 | 默认 | 说明 |
|------|-----|------|------|
| `<objective>` | ✅ | - | 用户目标 (中文) |
| `[max_turns]` | ❌ | 3 | 最大轮次 (Patcher 重试用) |
| `MAVIS_DEVIKA_USE_VERIFIER` | ❌ | 1 | 0 = 跳过 verifier, 1 = 调 verifier v2 |

---

## 已验证场景

### 场景 1: Happy Path (5 节点路径)

**命令**:
```bash
conda run -n part03 python runtime.py "用 9 Agent 演示 LangGraph StateGraph 端到端流程" 3
```

**真实结果**:
```
节点历史: 01_planner -> 02_researcher -> 03_coder -> 05_runner -> 08_reporter
最终 approved: True
- 01 Planner: 输出 5 步 JSON 计划
- 02 Researcher: 真实调 mavis-recall-v2 (exit 0)
- 03 Coder: LLM 生成 markdown 代码
- 05 Runner: 模拟执行 (exit 0)
- 08 Reporter: 生成最终报告
```

### 场景 2: Failure Path (3 节点路径 + 条件边)

**命令**:
```bash
conda run -n part03 python examples/test-patcher-path.py
```

**真实结果**:
```
节点历史: 05_runner -> 07_patcher -> 08_reporter
- 05 Runner (FAIL): 强制 exit_code=1
- should_continue_after_runner → 07_patcher
- 07 Patcher: MVP 模式通过
- should_continue_after_patcher → 08_reporter
- 08 Reporter: 生成报告
✅ 条件边验证通过
```

### 场景 3: 真实 verifier 集成

**命令**:
```bash
conda run -n part03 python examples/test-verifier-integration.py
```

**真实结果**:
```
节点历史: 05_runner -> 07_patcher -> 08_reporter
Patcher 真实调用 mavis-verifier-v2
审核结果: mavis-verifier-v2 审核通过
Tests: [{'name': 'verifier-v2', 'passed': True}]
```

---

## 4 大改造集成状态

| 改造 | 集成状态 | 集成位置 |
|------|---------|---------|
| #1 mavis-recall-v2 | ✅ 真实集成 | 02 Researcher (subprocess 调 recall.py) |
| #2 mavis-verifier-v2 | ✅ 真实集成 | 07 Patcher (subprocess 调 verifier.py) |
| #3 mavis-team-plan-v2 | 🟡 借鉴设计 | Planner node 借鉴 StateGraph 模式 |
| #4 mavis-devika-template | ✅ 真实落地 | 9 个 node 函数对应 9 个模板 |

---

## 与永久 invariant 关系

- ✅ **#21 LangGraph StateGraph**: 真实用 langgraph 1.0.10 的 StateGraph
- ✅ **#22 AutoGen 嵌套对话**: Patcher 调 verifier v2 (嵌套对话 3 角色)
- ✅ **#30 mavis recall v2**: Researcher 调 recall.py hybrid 模式
- ✅ **#31 Devika 9 Agent 模板**: 9 个节点对应 9 个 Agent 角色
- 🆕 **#32 mavis-devika-runtime**: 本项目永久 invariant

---

## 已知限制 (MVP)

| 限制 | 影响 | 后续 |
|------|------|------|
| 04 Action 简化为总是到 Reporter | 无法响应用户后续指令 | 新建 action-router sub-agent |
| 05 Runner 模拟执行 | 不能跑真实代码 | 集成 mavis-cu 或 docker sandbox |
| 06 Feature 占位 | 不能加新特性 | 完整实现增量功能 + 增量测试 |
| 09 Decision 简化为 no_op | 不能调外部函数 | 集成 lark-tools / github / cu |
| LLM 调用超时 180s | 大任务可能超时 | 加 retry + 切到 fast 模型 |

---

## 后续工作 (3-5 天)

### Day 1 ✅ (2026-07-10 完成)
- [x] LangGraph StateGraph 骨架 + 9 节点 + 2 条件边 + MemorySaver
- [x] 集成 mavis-recall-v2 (Researcher)
- [x] 集成 mavis-verifier-v2 (Patcher)
- [x] MVP happy path + failure path + verifier 集成 测试

### Day 2 (明天)
- [ ] 实现 04 Action 真实路由 (新建 action-router sub-agent)
- [ ] 实现 05 Runner 真实沙盒 (集成 mavis-cu)
- [ ] 实现 09 Decision 真实函数调用 (集成 lark-tools)

### Day 3 (后天)
- [ ] 实现 06 Feature 增量功能 + 测试
- [ ] 端到端 demo: 真实任务跑完整 9 Agent 协作
- [ ] 性能优化 (LLM retry + fast model fallback)

### Day 4-5
- [ ] CLI alias `mavis-devika` 加入 ~/.zshrc
- [ ] README + 完整文档
- [ ] cron self-reminder 监控生产任务
- [ ] 更新 knowledge-galaxy + memory

---

## 复现命令

```bash
# 1. 基础运行
conda run -n part03 python ~/workspace/mavis-devika-runtime/runtime.py "演示 9 Agent 端到端流程" 3

# 2. 测试 Patcher 路径
conda run -n part03 python ~/workspace/mavis-devika-runtime/examples/test-patcher-path.py

# 3. 真实 verifier 集成
conda run -n part03 python ~/workspace/mavis-devika-runtime/examples/test-verifier-integration.py

# 4. 验证 4 大改造
python3 ~/workspace/mavis-recall-v2/recall.py "LangGraph" hybrid 3
conda run -n part03 python ~/workspace/mavis-verifier-v2/verifier.py "审核 task" 1
python3 ~/workspace/mavis-team-plan-v2/team_plan_v2.py "演示 team plan" 2
ls ~/workspace/mavis-devika-template/
```