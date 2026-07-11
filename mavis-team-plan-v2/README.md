# mavis team plan v2 (P1.2 - CrewAI 4 组件改造)

> **永久 invariant #35**: CrewAI 4 组件 (Role/Goal/Backstory/Tools/Task/Crew/Process) = mavis Agent 模板
> **永久 invariant #21**: LangGraph StateGraph = mavis team plan DAG

## 来源

- 高强文《大模型项目实战》第 14 章 §5.2.2 (基于 CrewAI 的多角色 Agent 应用开发)
- 实战借鉴: 2026-07-11 P1.2 改造 (3 角色 + 串行 process + 14B)

## CrewAI 4 组件 -> mavis 映射

| CrewAI 组件 | mavis 映射 | dataclass 字段 |
|---|---|---|
| `Agent(role, goal, backstory, tools, allow_delegation)` | mavis worker | `@dataclass Agent` |
| `Task(description, expected_output, agent, context)` | mavis 单步任务 | `@dataclass Task` |
| `Crew(agents, tasks, process_mode)` | mavis team | `@dataclass Crew` |
| `Process(tasks, mode)` | 串行/层次编排 | `@dataclass Process` |

## 4 大组件详解

### 1. Agent (mavis worker 模板)

```python
@dataclass
class Agent:
    role: str               # 角色名 (系统分析师)
    goal: str               # 目标 (进行需求分析)
    backstory: str          # 背景知识 (在专业企业工作...)
    tools: List[Callable] = field(default_factory=list)
    allow_delegation: bool = False
    verbose: bool = False
```

`build_system_prompt()` 把 role + goal + backstory 拼成中文系统提示词,符合永久 invariant #14 (OUTPUT IN CHINESE)。

### 2. Task (单步任务)

```python
@dataclass
class Task:
    description: str             # 任务描述
    expected_output: str         # 期望输出
    agent: Agent                 # 负责的 Agent
    context_from: Optional['Task'] = None  # 上游 Task
    output: str = ""             # 任务结果
```

`context_from` 关键: 串行 process 中, 上一任务的 output 作为下一任务的 context, 真正实现多 Agent 协作。

### 3. Process (编排)

```python
class Process:
    def __init__(self, tasks: List[Task], mode: str = "sequential"):
        self.tasks = tasks
        self.mode = mode  # sequential / hierarchical
```

mavis 现阶段只实现 sequential, hierarchical 留 P2.x。

### 4. Crew (团队)

```python
class Crew:
    def __init__(self, agents: List[Agent], tasks: List[Task], process_mode: str = "sequential"):
        self.agents = agents
        self.tasks = tasks
        self.process = Process(tasks, mode=process_mode)
```

`kickoff()` 启动 Crew 跑 Process, 完成所有任务后返回。

## 实战验证 (2026-07-11 04:20)

**目标**: 设计 mavis plugin CLI 工具, 用于安装 / 加载 / 校验 mavis 插件

**Crew 配置**:
- Agent 1: 系统分析师 (allow_delegation=True)
- Agent 2: 系统设计师 (Python + click + cryptography 技术选型)
- Agent 3: 质量审核员 (审核可行性 + 完整性 + 风险)

**Process**: sequential (Analyst → Designer → Reviewer)

**输出**:
| Task | Agent | 字符数 | 关键内容 |
|---|---|---|---|
| 1 | 系统分析师 | 406 | 系统需求报告 (功能 + 非功能 + 约束) |
| 2 | 系统设计师 | 1121 | 技术方案 (选型 + 架构 + 模块) |
| 3 | 质量审核员 | 708 | 审核报告 (总体评价 + 改进建议) |
| **合计** | | **2235** | |

**verify**:
- 串行 process 成功: Task 2 引用 Task 1 需求 (CLI install/load/validate)
- Task 3 引用 Task 2 技术选型 (click 框架 + cryptography)
- 全部中文输出 (符合永久 invariant #14)
- state 持久化 OK (mavis-state.json)
- cycle report 写入 OK (cycle-report.json)
- exit 0

## 用法

```bash
cd /Users/apple/workspace/mavis-team-plan-v2
python3 team_plan_v2.py "<objective>" [max_turns]

# 示例
python3 team_plan_v2.py "设计 mavis plugin CLI 工具" 3
```

## 复用 call_llm retry + fallback (A1 改造)

- 模型链: `MAVIS_LLM_MODELS=qwen2.5:14b,gpt-3.5-turbo` (环境变量)
- 重试次数: `MAVIS_LLM_RETRY=2` (默认)
- 超时: `MAVIS_LLM_TIMEOUT=45` (秒)
- 重试间隔: `MAVIS_LLM_RETRY_SLEEP=2` (秒)

14B 比 32B 快 33 倍 (2.16s vs 72.93s), P1.2 默认 14B 跑串行 3 任务 ~30-60 秒。

## 下一步 (P1.3+)

- P1.3 LlamaIndex 4 步索引优化 mavis memory
- P2.x hierarchical Process (Manager 委派子 Agent)
- P2.x tools 集成 (search / file_op / shell)

## 验收 checklist

- [x] CrewAI 4 组件全部实现 (Agent/Task/Crew/Process)
- [x] 串行 process 跑通 (3 角色协作)
- [x] 中文输出
- [x] state 持久化
- [x] cycle report
- [x] call_llm retry + fallback
- [x] real scenario 跑通 (mavis plugin CLI 设计)
- [x] verify process 串行 (Task 2 引用 Task 1, Task 3 引用 Task 2)
