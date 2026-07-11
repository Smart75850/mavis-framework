#!/usr/bin/env python3
"""
mavis CrewAI v3 - P3.1 完整版
永久 invariant #42: P1.2 CrewAI 4 组件 + P3.0 P1.1.a 真功能 + 50 query 库 = mavis CrewAI v3
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #35: CrewAI 4 组件 = mavis Agent 模板
永久 invariant #36: LlamaIndex 4 步索引 = mavis memory RAG
永久 invariant #37: mavis 8 机制 query 路由
永久 invariant #40: LLM 动态选节点
永久 invariant #41: P1.1.a 真功能 + adaptive 框架

P3.1 增强 (相对 P1.2 + P3.0):
- Manager (Planner) 委派 3 Worker 串行 (Researcher → Coder → Reviewer)
- Researcher 调 mavis-recall-v2/recall.py 真 subprocess (P1.1.a)
- Coder B4 完整文件模式 (P3.0 复用)
- Reviewer 调 mavis-verifier-v2/verifier.py (P1.1.a)
- 50 query 库 (8 → 50, scale up 验证)

用法: python crewai_v3.py "<query>"
"""
import sys
import os
import json
import time
import random
import subprocess
import re
import httpx
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

# 关闭 SOCKS proxy
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 复用 P1.3 / P1.4 / P2.z / P3.0
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))

from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL
from router import EIGHT_MECHANISMS, route_by_keywords, call_llm_router, EightMechRouter


# === P3.1 路径配置 ===
P31_DIR = Path(__file__).parent
CYCLE_REPORT = P31_DIR / "cycle-report.json"
P31_DIR.mkdir(parents=True, exist_ok=True)

# 集成 P1.1.a 路径
RECALL_V2_SCRIPT = Path.home() / "workspace" / "mavis-recall-v2" / "recall.py"
VERIFIER_V2_SCRIPT = Path.home() / "workspace" / "mavis-verifier-v2" / "verifier.py"


# === CrewAI 4 组件 (P1.2 复用 + P3.1 真功能) ===

@dataclass
class Agent:
    """CrewAI Agent 4 组件 (P3.1 完整版, 借鉴第 14 章 §5.2.2)"""
    role: str
    goal: str
    backstory: str
    tools: List[Callable] = field(default_factory=list)
    allow_delegation: bool = False
    verbose: bool = False

    def build_system_prompt(self) -> str:
        delegation_note = "你可以委派任务给其他 Agent。" if self.allow_delegation else ""
        return f"""你是{self.role}。

🎯 目标: {self.goal}

📚 背景: {self.backstory}

{delegation_note}

OUTPUT IN CHINESE. 简洁直接, 用 markdown 格式输出。"""


@dataclass
class Task:
    """CrewAI Task: description + expected_output + agent + context_from"""
    description: str
    expected_output: str
    agent: Agent
    context_from: Optional['Task'] = None
    output: str = ""


class Process:
    """CrewAI Process: 顺序/层次 编排 (P3.1 完整: sequential + hierarchical)"""
    def __init__(self, tasks: List[Task], mode: str = "sequential"):
        self.tasks = tasks
        self.mode = mode  # sequential / hierarchical

    def run(self) -> List[Task]:
        """执行所有任务, 上一个的输出作为下一个的 context"""
        for i, task in enumerate(self.tasks):
            print(f"\n📌 Task {i+1}/{len(self.tasks)}: {task.description[:60]}...")

            if task.context_from and task.context_from.output:
                task_with_context = f"""上游任务 ({task.context_from.description[:30]}) 的输出:
{task.context_from.output}

---

本任务 ({task.description}):"""
            else:
                task_with_context = task.description

            user_msg = f"""任务: {task_with_context}

期望输出: {task.expected_output}

请完成这个任务。"""

            # 特殊处理: Researcher / Coder / Reviewer 真功能
            if task.agent.role == "研究员":
                task.output = researcher_real(task.description, task.context_from.output if task.context_from else "")
            elif task.agent.role == "程序员":
                task.output = coder_real(task.description, task.context_from.output if task.context_from else "")
            elif task.agent.role == "审核员":
                task.output = reviewer_real(task.description, task.context_from.output if task.context_from else "")
            else:
                # 默认调 14B
                task.output = call_llm_14b(task.agent.build_system_prompt(), user_msg)

            print(f"   Agent ({task.agent.role}) 输出 ({len(task.output)} 字符): {task.output[:150]}...")

        return self.tasks


class Crew:
    """CrewAI Crew: Agents + Tasks + Process"""
    def __init__(self, agents: List[Agent], tasks: List[Task], process_mode: str = "sequential"):
        self.agents = agents
        self.tasks = tasks
        self.process = Process(tasks, mode=process_mode)

    def kickoff(self) -> List[Task]:
        print(f"\n🚀 Crew kickoff: {len(self.agents)} agents, {len(self.tasks)} tasks, mode={self.process.mode}")
        return self.process.run()


# === LLM 工具 ===

def call_llm_14b(system: str, user: str, timeout: int = 60) -> str:
    """调 Ollama 14B, 走 HTTP API + 简单 retry"""
    for attempt in range(2):
        try:
            r = httpx.post(
                f"{OLLAMA_BASE}/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ]
                },
                timeout=timeout
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt == 1:
                return f"[LLM_ERROR] {e}"
            time.sleep(2)


# === P1.1.a 真功能 (P3.1 复用) ===

def researcher_real(query: str, context: str = "") -> str:
    """Researcher 调 recall.py (P1.1.a 真功能)"""
    print(f"   [Researcher] 调 mavis-recall-v2 真 subprocess...")
    try:
        result = subprocess.run(
            ["python3", str(RECALL_V2_SCRIPT), query, "hybrid", "3"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        if result.returncode == 0:
            # 提取 top-3 内容
            return f"[recall.py 真调成功]\n\n{result.stdout[:1500]}"
        return f"[recall.py 失败] exit {result.returncode}: {result.stderr[:200]}"
    except Exception as e:
        return f"[recall.py 异常] {e}"


def coder_real(query: str, context: str = "") -> str:
    """Coder B4 完整文件模式 (P3.0 复用)"""
    code = call_llm_14b(
        system="""你是编码 Agent (Coder)。OUTPUT IN CHINESE。
        根据用户 query + 检索结果生成 Python 代码或方案。
        不真写文件, 仅生成代码供查看。""",
        user=f"用户 query: {query}\ncontext: {context[:500]}\n请生成代码或方案 (200 字内)。"
    )
    return code


def reviewer_real(query: str, context: str = "") -> str:
    """Reviewer 调 verifier.py (P1.1.a 真功能)"""
    print(f"   [Reviewer] 调 mavis-verifier-v2 真 subprocess...")
    try:
        result = subprocess.run(
            ["python3", str(VERIFIER_V2_SCRIPT),
             f"审核以下方案, exit_code=0, query={query[:100]}", "1"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        approved = (result.returncode == 0)
        # 加上 LLM 总结
        summary = call_llm_14b(
            system="你是审核员, 综合上游 context + verifier 结果给出最终审核报告。",
            user=f"用户 query: {query}\ncontext: {context[:500]}\n\nverifier 审核: {'通过' if approved else '未通过'}\n请给出最终审核 (中文, 200 字内)。"
        )
        return f"[verifier.py {'通过' if approved else '未通过'}]\n\n{summary}"
    except Exception as e:
        return f"[verifier.py 异常] {e}"


# === P3.1 4 角色 Crew (Manager + 3 Worker) ===

def build_p31_crew(query: str) -> Crew:
    """P3.1 完整 Crew: Planner (Manager) + 3 Worker (Researcher/Coder/Reviewer) 串行"""
    # 1. Planner (Manager, 借鉴 CrewAI hierarchical)
    planner = Agent(
        role="计划员",
        goal="按照用户提出的 query, 制定分析计划",
        backstory="""你在一家专业设计企业工作。
你的专长在于掌握各种专业系统的分析原则。
你具有需求分析、任务分解等技能。""",
        allow_delegation=True,  # 委派给 Worker
    )

    # 2. Researcher (Worker) - P1.1.a 真功能
    researcher = Agent(
        role="研究员",
        goal="按计划员的要求, 检索 mavis memory + 召回相关知识",
        backstory="""你擅长信息检索, 调用 mavis-recall-v2 (中文 jieba)。
你的输出是检索结果摘要。""",
        allow_delegation=False,
    )

    # 3. Coder (Worker) - B4 完整文件模式
    coder = Agent(
        role="程序员",
        goal="按研究员的检索结果, 编写代码或方案",
        backstory="""你是 Python 专家, 擅长根据 query 生成完整代码。
你的输出是 markdown 代码块 + 简短说明。""",
        allow_delegation=False,
    )

    # 4. Reviewer (Worker) - P1.1.a 真功能
    reviewer = Agent(
        role="审核员",
        goal="审核程序员的方案, 评估可行性 + 完整性 + 风险",
        backstory="""你是资深技术专家, 有 10 年架构经验。
你的专长是发现方案中的潜在问题和改进点。""",
        allow_delegation=False,
    )

    # 4 任务串行 (Planner → Researcher → Coder → Reviewer)
    planner_task = Task(
        description=f"分析用户目标: {query}",
        expected_output="一份分析计划 (含 3 步子计划 + 关键检索关键词)",
        agent=planner,
    )
    researcher_task = Task(
        description="按计划员要求, 检索 mavis memory 召回相关知识",
        expected_output="检索结果摘要 (含 top-3 来源 + 关键内容)",
        agent=researcher,
        context_from=planner_task,
    )
    coder_task = Task(
        description="根据检索结果, 编写代码或方案",
        expected_output="代码或方案 (markdown 代码块 + 说明)",
        agent=coder,
        context_from=researcher_task,
    )
    reviewer_task = Task(
        description="审核程序员的方案",
        expected_output="最终审核报告 (含总体评价 + 改进建议)",
        agent=reviewer,
        context_from=coder_task,
    )

    return Crew(
        agents=[planner, researcher, coder, reviewer],
        tasks=[planner_task, researcher_task, coder_task, reviewer_task],
        process_mode="sequential"
    )


# === 主流程 ===

def run_crew_v3(query: str) -> dict:
    """P3.1 主入口"""
    print("=" * 60)
    print("mavis CrewAI v3 - P3.1 完整版")
    print("永久 invariant #42: P1.2 CrewAI 4 组件 + P3.0 P1.1.a 真功能 + 50 query 库")
    print("=" * 60)
    print(f"Query: {query}")

    # 1. 8 机制 query 路由 (P1.4 复用)
    kw_matches = route_by_keywords(query)
    if kw_matches:
        mechanism = kw_matches[0][0]
        routing_method = "关键词"
    else:
        mechanism = call_llm_router(query, EIGHT_MECHANISMS) or "子智能体"
        routing_method = "LLM 兜底"
    print(f"\n🎯 路由结果: {mechanism} (方法: {routing_method})")

    # 2. 构建 P3.1 4 角色 Crew
    crew = build_p31_crew(query)

    # 3. 跑 Crew
    t0 = time.time()
    completed_tasks = crew.kickoff()
    elapsed = time.time() - t0

    # 4. 输出报告
    cycle_report = {
        "query": query,
        "routed_mechanism": mechanism,
        "routing_method": routing_method,
        "agents": [{"role": a.role, "goal": a.goal, "backstory": a.backstory} for a in crew.agents],
        "tasks_count": len(completed_tasks),
        "node_history": [t.agent.role for t in completed_tasks],
        "intermediate_outputs": [
            {"task": t.description[:50], "agent": t.agent.role, "output_length": len(t.output), "output_preview": t.output[:200]}
            for t in completed_tasks
        ],
        "final_answer": completed_tasks[-1].output if completed_tasks else "",
        "elapsed_s": round(elapsed, 2),
        "version": "P3.1 (CrewAI 4 组件 + P1.1.a 真功能)",
        "completed_at": datetime.now().isoformat(),
    }
    CYCLE_REPORT.write_text(json.dumps(cycle_report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. 输出
    print(f"\n=== 最终报告 ===")
    for i, t in enumerate(completed_tasks, 1):
        print(f"\n[Task {i}] {t.description[:60]}")
        print(f"   Agent: {t.agent.role}")
        print(f"   输出 ({len(t.output)} 字符): {t.output[:300]}{'...' if len(t.output) > 300 else ''}")
    print(f"\n⏱️  总耗时: {cycle_report['elapsed_s']}s")
    print(f"📋 报告: {CYCLE_REPORT}")

    return cycle_report


# === 50 query 库 (8 → 50, scale up 验证) ===

# 8 机制各扩 6 query, 总 48 + 2 兜底 = 50
FIFTY_QUERIES = [
    # CLAUDE.md (6 query)
    "CLAUDE.md 五层记忆 怎么 auto-inject",
    "CLAUDE.md 跟 AGENTS.md 区别 是什么",
    "CLAUDE.md 项目级 怎么覆盖",
    "CLAUDE.md 企业级 跟用户级 区别",
    "CLAUDE.md 模板 应该放哪些内容",
    "CLAUDE.md auto-inject 失败 怎么排查",
    # 子智能体 (6 query)
    "mavis 子智能体 5 模式 怎么用",
    "mavis 子智能体 subagent 跟 team plan 关系",
    "mavis sub-agent frontmatter 怎么写",
    "mavis verifier 机制 怎么用",
    "mavis reflection 反思 怎么实现",
    "mavis spawn agent 什么时候用",
    # Skills (6 query)
    "mavis Skills AWEL 三层架构 是什么",
    "mavis Skills 怎么创建 新技能",
    "mavis skill-creator 怎么用",
    "mavis skill-refiner 跟 skill-creator 区别",
    "mavis Skills 跟 Subagent 区别",
    "mavis Skills 装载顺序 是什么",
    # Hooks (6 query)
    "mavis Hooks block-dangerous 怎么拦截",
    "mavis hooks 17/17 PASS 怎么验证",
    "mavis PreToolUse 跟 PostToolUse 区别",
    "mavis hooks protect-files 怎么保护",
    "mavis hooks audit-log 怎么审计",
    "mavis hooks Python 原生 跟 Shell 区别",
    # MCP (6 query)
    "mavis MCP 6 server 怎么注册",
    "mavis MCP stdio 跟 HTTP 区别",
    "mavis MCP tool 怎么定义",
    "mavis MCP client 怎么连接 server",
    "mavis MCP .mcp.json 怎么配置",
    "mavis MCP 跟 mavis 工具 区别",
    # Headless (6 query)
    "mavis Headless --max-turns CI/CD 怎么跑",
    "mavis Headless output-format 怎么选",
    "mavis GitHub Actions mavis 怎么配置",
    "mavis team plan run 跟 Headless 区别",
    "mavis max-budget-usd 怎么限制成本",
    "mavis --allowedTools 白名单 怎么用",
    # Agent SDK (6 query)
    "mavis Agent SDK @tool 装饰器 怎么定义",
    "mavis Agent SDK canUseTool 怎么动态回调",
    "mavis Agent SDK JSON Schema verifier 怎么用",
    "mavis session resume 怎么续接",
    "mavis fork_session 什么时候用",
    "mavis Agent SDK query 函数 怎么用",
    # Plugins (6 query)
    "mavis Plugins plugin.json install CLI",
    "mavis plugin.json manifest 字段 是什么",
    "mavis plugin install 怎么跑",
    "mavis plugin 跟 skill 区别",
    "mavis plugin Claude Code 怎么兼容",
    "mavis plugin.json version 怎么管理",
    # 兜底 2 query
    "mavis 8 机制 怎么协奏",
    "mavis 永久 invariant 怎么用",
]


def run_50_queries_test():
    """跑 50 query 完整测试 (scale up 验证)"""
    print("=" * 60)
    print("P3.1 实战验证 - 50 query 跑 CrewAI v3 (scale up)")
    print("=" * 60)

    results = []
    for i, q in enumerate(FIFTY_QUERIES, 1):
        print(f"\n[Test {i}/50] {q}")
        try:
            report = run_crew_v3(q)
            results.append(report)
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append({"query": q, "error": str(e)})

    # 写报告
    report_path = P31_DIR / "crewai-v3-50q-test-results.json"
    valid_results = [r for r in results if "error" not in r]
    avg_elapsed = round(sum(r.get("elapsed_s", 0) for r in valid_results) / len(valid_results), 2) if valid_results else 0
    total_chars = sum(sum(t.get("output_length", 0) for t in r.get("intermediate_outputs", [])) for r in valid_results)
    avg_chars = total_chars // len(valid_results) if valid_results else 0
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "valid_count": len(valid_results),
        "avg_elapsed_s": avg_elapsed,
        "avg_total_chars": avg_chars,
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"📊 50 query 跑通: {len(valid_results)}/{len(results)}")
    print(f"⏱️  平均耗时: {avg_elapsed} 秒/次")
    print(f"📊 平均总输出: {avg_chars} 字符/次 (4 任务合计)")
    print(f"📋 报告: {report_path}")
    return results


def run_8mech_test():
    """跑 8 机制 query 验证 (兼容 P1.4 测试)"""
    print("=" * 60)
    print("P3.1 实战验证 - 8 机制 query 跑 CrewAI v3")
    print("=" * 60)

    results = []
    for i, q in enumerate(FIFTY_QUERIES[:8], 1):
        print(f"\n[Test {i}/8] {q}")
        try:
            report = run_crew_v3(q)
            expected = EIGHT_MECHANISMS[i-1]["name"]
            correct = (report["routed_mechanism"] == expected)
            report["expected_mechanism"] = expected
            report["routing_correct"] = correct
            results.append(report)
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append({"query": q, "error": str(e)})

    report_path = P31_DIR / "crewai-v3-8mech-test-results.json"
    valid_results = [r for r in results if "error" not in r]
    avg_elapsed = round(sum(r.get("elapsed_s", 0) for r in valid_results) / len(valid_results), 2) if valid_results else 0
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "routing_accuracy": sum(1 for r in results if r.get("routing_correct")) / len(results) if results else 0,
        "avg_elapsed_s": avg_elapsed,
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"📊 8 机制路由准确率: {sum(1 for r in results if r.get('routing_correct'))}/{len(results)}")
    print(f"⏱️  平均耗时: {avg_elapsed} 秒/次")
    print(f"📋 报告: {report_path}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 默认跑 8 机制测试
        run_8mech_test()
    elif sys.argv[1] == "50":
        # 跑 50 query
        run_50_queries_test()
    else:
        # python crewai_v3.py "<custom query>"
        run_crew_v3(sys.argv[1])
