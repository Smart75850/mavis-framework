#!/usr/bin/env python3
"""
mavis team plan v3 - 借鉴 CrewAI 4 组件 (2026-07-11)
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #35: CrewAI 4 组件 (Role/Goal/Backstory/Tools) = mavis Agent 模板

来源: 高强文书第 14 章 §5.2.2 (基于 CrewAI 的多角色 Agent 应用开发)

CrewAI 4 组件 -> mavis 映射:
- Agent (Role + Goal + Backstory + Tools) -> mavis worker
- Task (description + expected_output + agent) -> mavis 单步任务
- Crew (Agents + Tasks + Process) -> mavis team
- Process (sequential/hierarchical) -> mavis cycle_report 路由

用法: python team_plan_v2.py "<objective>" [max_turns]
"""
import sys
import json
import os
import urllib.request
import urllib.error
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

# === 永久 invariant #12: Ollama 兼容名 + P1.2 改造: 14B 优先 ===
LLM_BASE = "http://127.0.0.1:11434/v1"
LLM_MODELS_CHAIN = os.environ.get("MAVIS_LLM_MODELS", "qwen2.5:14b,gpt-3.5-turbo").split(",")
LLM_RETRY_PER_MODEL = int(os.environ.get("MAVIS_LLM_RETRY", "2"))
LLM_TIMEOUT = int(os.environ.get("MAVIS_LLM_TIMEOUT", "45"))
LLM_RETRY_SLEEP = int(os.environ.get("MAVIS_LLM_RETRY_SLEEP", "2"))

# === 路径配置 ===
PLAN_DIR = Path.home() / "workspace" / "mavis-team-plan-v2"
STATE_FILE = PLAN_DIR / "mavis-state.json"
CYCLE_REPORT = PLAN_DIR / "cycle-report.json"
PLAN_DIR.mkdir(parents=True, exist_ok=True)


# === LLM 工具 (同 mavis-devika-runtime) ===

def call_llm(system: str, user: str, timeout: Optional[int] = None) -> str:
    """调用 Ollama, 支持 retry + fallback 模型链"""
    if timeout is None:
        timeout = LLM_TIMEOUT
    last_error = None
    for model in LLM_MODELS_CHAIN:
        model = model.strip()
        for attempt in range(1, LLM_RETRY_PER_MODEL + 1):
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ]
                }
                req = urllib.request.Request(
                    f"{LLM_BASE}/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read())
                    content = data["choices"][0]["message"]["content"]
                    return content
            except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
                last_error = f"[{model} attempt {attempt}] {type(e).__name__}: {str(e)[:200]}"
                if attempt < LLM_RETRY_PER_MODEL:
                    time.sleep(LLM_RETRY_SLEEP)
                continue
            except Exception as e:
                last_error = f"[{model}] {type(e).__name__}: {str(e)[:200]}"
                break
    return f"[LLM_FALLBACK_FAILED] {last_error}"


# === CrewAI 4 组件 (借鉴第 14 章 §5.2.2) ===

@dataclass
class Agent:
    """CrewAI Agent 4 组件: Role + Goal + Backstory + Tools"""
    role: str               # 角色名 (系统分析师)
    goal: str               # 目标 (进行需求分析)
    backstory: str          # 背景知识 (在专业企业工作...)
    tools: List[Callable] = field(default_factory=list)  # 可用工具
    allow_delegation: bool = False  # 是否可委派任务
    verbose: bool = False

    def build_system_prompt(self) -> str:
        """借鉴第 14 章: 由 role + goal + backstory 拼成系统提示词"""
        delegation_note = "你可以委派任务给其他 Agent。" if self.allow_delegation else ""
        return f"""你是{self.role}。

🎯 目标: {self.goal}

📚 背景: {self.backstory}

{delegation_note}
"""


@dataclass
class Task:
    """CrewAI Task: description + expected_output + agent"""
    description: str             # 任务描述
    expected_output: str         # 期望输出
    agent: Agent                 # 负责的 Agent
    context_from: Optional['Task'] = None  # 上游 Task (Process 编排用)
    output: str = ""             # 任务结果 (执行后填)


class Process:
    """CrewAI Process: 顺序/层次 编排"""
    def __init__(self, tasks: List[Task], mode: str = "sequential"):
        self.tasks = tasks
        self.mode = mode  # sequential / hierarchical

    def run(self) -> List[Task]:
        """执行所有任务, 上一个的输出作为下一个的 context"""
        for i, task in enumerate(self.tasks):
            print(f"\n📌 Task {i+1}/{len(self.tasks)}: {task.description[:60]}...")

            # 准备 context (上一个 task 的输出)
            if task.context_from and task.context_from.output:
                task_with_context = f"""上游任务 ({task.context_from.description[:30]}) 的输出:
{task.context_from.output}

---

本任务 ({task.description}):"""
            else:
                task_with_context = task.description

            # 调用 Agent 执行
            user_msg = f"""任务: {task_with_context}

期望输出: {task.expected_output}

请完成这个任务。"""
            task.output = call_llm(task.agent.build_system_prompt(), user_msg)
            print(f"   Agent ({task.agent.role}) 输出 ({len(task.output)} 字符): {task.output[:150]}...")

        return self.tasks


class Crew:
    """CrewAI Crew: Agents + Tasks + Process"""
    def __init__(self, agents: List[Agent], tasks: List[Task], process_mode: str = "sequential"):
        self.agents = agents
        self.tasks = tasks
        self.process = Process(tasks, mode=process_mode)

    def kickoff(self) -> List[Task]:
        """启动 Crew, 跑 Process"""
        print(f"\n🚀 Crew kickoff: {len(self.agents)} agents, {len(self.tasks)} tasks, mode={self.process.mode}")
        return self.process.run()


# === 主流程 (mavis crew v3) ===

def init_state(objective: str, max_turns: int) -> dict:
    state = {
        "objective": objective,
        "created_at": datetime.now().isoformat(),
        "thread_id": os.getpid(),
        "max_turns": max_turns,
        "version": "v3 (CrewAI 4 组件)",
        "agents": [],
        "tasks": [],
        "crew_output": [],
        "node_history": []
    }
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def update_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_default_crew(objective: str) -> Crew:
    """构建默认 3 角色 Crew (借鉴第 14 章系统分析师/设计师/审核员)"""
    # 1. 系统分析师 (Analyst)
    analyst = Agent(
        role="系统分析师",
        goal="按照用户提出的任务, 进行需求分析, 撰写系统需求报告",
        backstory="""你在一家专业设计企业工作。
你的专长在于掌握各种专业系统分析的原则。
你具有需求分析、任务分解等技能。""",
        allow_delegation=True,
    )

    # 2. 系统设计师 (Designer)
    designer = Agent(
        role="系统设计师",
        goal="按照系统分析师的需求报告, 撰写详细的设计方案 (含技术选型 + 模块设计 + 实施步骤)",
        backstory="""你在一家专业设计企业工作。
你的专长在于掌握各种专业系统的设计原则。
你具有系统模块设计、技术选型、公式推导等技能。""",
        allow_delegation=False,
    )

    # 3. 审核员 (Reviewer)
    reviewer = Agent(
        role="质量审核员",
        goal="审核设计师的方案, 评估可行性 + 完整性 + 风险, 给出改进建议",
        backstory="""你是资深技术专家, 有 10 年架构经验。
你的专长是发现方案中的潜在问题和改进点。""",
        allow_delegation=False,
    )

    # 3 个 Task 串行 (Analyst → Designer → Reviewer)
    analyst_task = Task(
        description=f"分析用户目标: {objective}",
        expected_output="一份系统需求报告 (含功能需求 + 非功能需求 + 约束条件)",
        agent=analyst,
    )
    designer_task = Task(
        description="根据系统需求报告, 撰写详细设计方案",
        expected_output="一份技术设计方案 (含架构 + 模块 + 实施步骤 + 风险)",
        agent=designer,
        context_from=analyst_task,
    )
    reviewer_task = Task(
        description="审核技术方案, 给出最终评估",
        expected_output="一份审核报告 (含总体评价 + 改进建议 + 评分 1-10)",
        agent=reviewer,
        context_from=designer_task,
    )

    return Crew(
        agents=[analyst, designer, reviewer],
        tasks=[analyst_task, designer_task, reviewer_task],
        process_mode="sequential"
    )


def run_crew(objective: str, max_turns: int = 3):
    """主入口"""
    print("=" * 60)
    print("mavis team plan v3 - 借鉴 CrewAI 4 组件")
    print("永久 invariant #21: LangGraph StateGraph")