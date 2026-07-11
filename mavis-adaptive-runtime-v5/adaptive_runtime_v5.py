#!/usr/bin/env python3
"""
mavis Adaptive Runtime v5 - P3.0 完整版
永久 invariant #41: P1.1.a 真功能 + P2.z adaptive 框架 = mavis adaptive runtime v5
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #36: LlamaIndex 4 步索引 = mavis memory RAG
永久 invariant #37: mavis 8 机制 query 路由
永久 invariant #38: adaptive runtime (P2.x 基础)
永久 invariant #39: adaptive runtime v3 (P2.y 完整版)
永久 invariant #40: LLM 动态选节点 (P2.z)

P3.0 整合 (相对 P2.z):
- 02_researcher: 调 mavis-recall-v2/recall.py 真 subprocess (P1.1.a 真功能)
- 03_coder: B4 完整文件模式 + 长度检查 (P1.1.a B4 模式)
- 05_runner: 真 subprocess 60s timeout (P1.1.a 真功能)
- 07_patcher: 调 mavis-verifier-v2/verifier.py 真 subprocess (P1.1.a 真功能)

用法: python adaptive_runtime_v5.py "<query>" [max_turns]
"""
import sys
import os
import json
import time
import random
import subprocess
import re
import shutil
import httpx
from pathlib import Path
from datetime import datetime
from typing import TypedDict, Dict, List, Any, Optional, Annotated, Callable
from operator import add

# 关闭 SOCKS proxy
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 复用 P1.3 / P1.4 / P2.z
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL

from router import EIGHT_MECHANISMS, route_by_keywords, call_llm_router, EightMechRouter


# === P3.0 路径配置 ===
P30_DIR = Path(__file__).parent
CYCLE_REPORT = P30_DIR / "cycle-report.json"
P30_DIR.mkdir(parents=True, exist_ok=True)

# 集成 P1.1.a 路径
RECALL_V2_SCRIPT = Path.home() / "workspace" / "mavis-recall-v2" / "recall.py"
VERIFIER_V2_SCRIPT = Path.home() / "workspace" / "mavis-verifier-v2" / "verifier.py"

# 检查 P1.1.a 路径
assert RECALL_V2_SCRIPT.exists(), f"recall.py not found: {RECALL_V2_SCRIPT}"
assert VERIFIER_V2_SCRIPT.exists(), f"verifier.py not found: {VERIFIER_V2_SCRIPT}"


# === 10 节点 (跟 P2.z 一样) ===

ALL_10_NODES = [
    "00_router",
    "01_planner",
    "02_researcher",
    "03_coder",
    "04_action",
    "05_runner",
    "06_feature",
    "07_patcher",
    "08_reporter",
    "09_decision",
]


# === LangGraph State ===

class AdaptiveStateV5(TypedDict, total=False):
    query: str
    routed_mechanism: str
    routing_method: str
    dynamic_nodes: List[str]
    current_turn: int
    max_turns: int
    last_approved: bool
    exit_code: int
    current_node: str
    step_history: List[str]
    intermediate_outputs: Dict[str, Any]
    final_answer: str


# === 安全白名单 (P3.0 强化: 跟 P1.1.a 一致) ===

ALLOWED_COMMANDS = {
    "echo", "python3", "ls", "pwd", "whoami", "date",
    "cat", "wc", "head", "which", "env",
}

BLOCKED_PATTERNS = [
    r"\brm\b", r"\bmv\b", r"\bchmod\b", r"\bchown\b", r"\bsudo\b",
    r"\bcurl\b", r"\bwget\b", r"\bnc\b", r"\bssh\b", r"\bscp\b",
    r"\beval\b", r"\bexec\b", r"\bpip\b", r"\bnpm\b", r"\bbrew\b",
    r"\bkill\b", r"\bpkill\b", r"\bdd\b", r"\bmkfs\b", r"\bformat\b",
    r"\|\s*(bash|sh|zsh)", r"\$\(", r"`", r"&&\s*(rm|mv|chmod)",
    r"\bshutdown\b", r"\breboot\b",
]


def safe_subprocess_run(cmd: str, timeout: int = 30) -> dict:
    """P3.0 强化版 subprocess (白名单 + 黑名单 + timeout)"""
    for pat in BLOCKED_PATTERNS:
        if re.search(pat, cmd, re.IGNORECASE):
            return {"exit_code": -1, "stderr": f"BLOCKED: {pat}", "stdout": ""}

    cmd_first = cmd.strip().split()[0] if cmd.strip() else ""
    if cmd_first not in ALLOWED_COMMANDS:
        return {"exit_code": -1, "stderr": f"NOT_IN_WHITELIST: {cmd_first}", "stdout": ""}

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:200],
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stderr": f"TIMEOUT: {timeout}s", "stdout": ""}
    except Exception as e:
        return {"exit_code": -1, "stderr": f"ERROR: {e}", "stdout": ""}


# === LLM 工具 ===
# 永久 invariant #51: M3 Provider 接入 (用云端 LLM, 唔用本地大模型)
sys.path.insert(0, str(Path.home() / "workspace" / "mavis-framework" / "mavis-crewai-v7"))
try:
    from mavis_m3_provider import call_llm_m3
    USE_M3 = True
except ImportError:
    USE_M3 = False


def _call_llm_14b(system: str, user: str, timeout: int = 60) -> str:
    """调 LLM: 优先 M3, fallback 到本地 14B (永久 invariant #51)"""
    if USE_M3:
        for attempt in range(2):
            try:
                return call_llm_m3(
                    system=system,
                    user=user,
                    max_tokens=2048,
                    temperature=0.7,
                    use_fallback=True,  # M3 失败自动 fallback 到本地 14B
                ).strip()
            except Exception as e:
                if attempt == 1:
                    return f"[LLM_ERROR] {e}"
                time.sleep(2)
    # 无 M3 时, 用本地 ollama
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


# === P1.1.a 真功能: 02_researcher (调 recall.py) ===

def researcher_v5(query: str) -> dict:
    """P1.1.a 真 subprocess 调 recall.py"""
    print("   [02_researcher] 调 mavis-recall-v2 真 subprocess...")
    try:
        result = subprocess.run(
            ["python3", str(RECALL_V2_SCRIPT), query, "hybrid", "3"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        if result.returncode == 0:
            # 解析 recall.py 输出, 取 top-3
            lines = result.stdout.split("\n")
            top_results = []
            current = {}
            for line in lines:
                if line.startswith("[1]") or line.startswith("[2]") or line.startswith("[3]"):
                    if current:
                        top_results.append(current)
                    current = {"rank": line[:3], "content": "", "path": "", "score": ""}
                elif line.strip().startswith("Path:"):
                    current["path"] = line.split("Path:")[1].strip()
                elif line.strip().startswith("Content:"):
                    current["content"] = line.split("Content:")[1].strip()[:200]
                elif line.strip().startswith("Score:"):
                    current["score"] = line.split("Score:")[1].strip()
            if current:
                top_results.append(current)
            return {
                "research": top_results,
                "raw_output": result.stdout[:800],
                "source": "mavis-recall-v2 (P1.1.a 真功能)",
                "step": "research"
            }
        else:
            return {
                "research": [],
                "raw_output": f"recall.py exit {result.returncode}",
                "source": "mavis-recall-v2 (失败)",
                "step": "research",
                "error": result.stderr[:200]
            }
    except Exception as e:
        return {"research": [], "source": "mavis-recall-v2 (异常)", "error": str(e), "step": "research"}


# === P1.1.a 真功能: 03_coder (B4 完整文件模式) ===

def coder_v5(query: str, plan: str = "") -> dict:
    """P1.1.a B4 完整文件模式: 调 14B 生成代码 (不真写文件, query 任务是知识查询)"""
    # 简化: query 任务不真写文件, 但调 14B 生成代码供查看
    code = _call_llm_14b(
        system="""你是编码 Agent (Coder)。OUTPUT IN CHINESE。
        根据用户 query + plan 生成 Python 代码或方案。
        不真写文件, 仅生成代码供查看。""",
        user=f"用户 query: {query}\nplan: {plan}\n请生成代码或方案 (200 字内)。"
    )
    return {
        "code": code[:500],
        "written_file": None,  # P3.0 query 任务不真写文件
        "apply_status": "P3.0-query-mode (不真写文件)",
        "step": "code"
    }


# === P1.1.a 真功能: 05_runner (真 subprocess) ===

def runner_v5(query: str) -> dict:
    """P1.1.a 真 subprocess 跑白名单命令"""
    # 调 14B 决定跑什么白名单命令
    cmd_decision = _call_llm_14b(
        system=f"""你是 mavis 安全命令生成器, 只输出 1 个白名单命令。
        白名单: {','.join(ALLOWED_COMMANDS)}
        输出格式: 仅命令本身, 不要解释""",
        user=f"用户 query: {query}\n请输出 1 个白名单内的命令 (验证当前环境, 例如 pwd / whoami / date)。"
    )
    cmd = ""
    for line in cmd_decision.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            cmd = line
            break
    if not cmd:
        cmd = "echo test"

    result = safe_subprocess_run(cmd, timeout=10)
    return {
        "command": cmd,
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "step": "run",
        "sandbox": "P1.1.a 真 subprocess (白名单)"
    }


# === P1.1.a 真功能: 07_patcher (调 verifier.py) ===

def patcher_v5(run_result: dict) -> dict:
    """P1.1.a 真 subprocess 调 verifier.py"""
    print("   [07_patcher] 调 mavis-verifier-v2 真 subprocess...")
    try:
        result = subprocess.run(
            ["python3", str(VERIFIER_V2_SCRIPT),
             f"审核当前执行结果, exit_code={run_result.get('exit_code', -1)}",
             "1"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        approved = (result.returncode == 0)
        return {
            "patch": "mavis-verifier-v2 审核" + ("通过" if approved else "未通过"),
            "approved": approved,
            "raw_output": result.stdout[:300],
            "step": "patch",
            "source": "mavis-verifier-v2 (P1.1.a 真功能)"
        }
    except subprocess.TimeoutExpired:
        return {"patch": "verifier timeout", "approved": False, "step": "patch", "error": "60s timeout"}
    except Exception as e:
        return {"patch": "verifier 异常", "approved": False, "step": "patch", "error": str(e)}


# === 10 节点 (P3.0 整合 P1.1.a 真功能 + P2.z 框架) ===

def make_node_v5(node_name: str, eight_mech_router: EightMechRouter) -> Callable:
    def node_function(state: AdaptiveStateV5) -> AdaptiveStateV5:
        t0 = time.time()
        query = state.get("query", "")
        mechanism = state.get("routed_mechanism", "")
        turn = state.get("current_turn", 0) + 1
        history = state.get("step_history", [])
        intermediate = state.get("intermediate_outputs", {})
        history = history + [node_name]

        if node_name == "00_router":
            all_9 = ["01_planner", "02_researcher", "03_coder", "04_action", "05_runner", "06_feature", "07_patcher", "08_reporter", "09_decision"]
            decision = _call_llm_14b(
                system=f"从这 9 个节点中选 3-7 个: {','.join(all_9)}\n输出格式: 节点1,节点2,...",
                user=f"用户 query: {query}\n机制: {mechanism}\n请输出 3-7 个节点, 逗号分隔"
            )
            selected = []
            for n in decision.replace("\n", ",").split(","):
                n = n.strip()
                if n in all_9 and n not in selected:
                    selected.append(n)
            if len(selected) < 2:
                selected = ["01_planner", "02_researcher", "04_action", "08_reporter"]
            output = {"selected_nodes": selected, "step": "route"}

        elif node_name == "01_planner":
            plan = _call_llm_14b(
                system="你是 mavis 计划员 (Manager), 根据用户 query + 机制类型制定 3 步子计划。",
                user=f"用户 query: {query}\n机制: {mechanism}\n请输出 3 步子计划 (列表形式)。"
            )
            output = {"plan": plan[:500], "step": "plan", "turn": turn}

        elif node_name == "02_researcher":
            # P3.0 真功能: 调 recall.py
            output = researcher_v5(query)

        elif node_name == "03_coder":
            # P3.0 真功能: B4 完整文件模式 (P3.0 query 模式: 不真写文件)
            plan = intermediate.get("01_planner", {}).get("plan", "")
            output = coder_v5(query, plan)

        elif node_name == "04_action":
            action_decision = _call_llm_14b(
                system="你是 mavis 路由器, 决定下一步动作 (run/test/feature/decision/no_op)。",
                user=f"用户 query: {query}\n已执行: {history}\n请输出 1 个动作: run / test / feature / decision / no_op"
            )
            action = "no_op"
            for kw in ["run", "test", "feature", "decision"]:
                if kw in action_decision.lower():
                    action = kw
                    break
            output = {"action": action, "step": "action"}

        elif node_name == "05_runner":
            # P3.0 真功能: 真 subprocess 跑白名单命令
            output = runner_v5(query)

        elif node_name == "06_feature":
            feature = _call_llm_14b(
                system="你是 mavis 特性工程师。",
                user=f"用户 query: {query}\n请输出新特性建议 (100 字内)。"
            )
            output = {"feature": feature[:300], "step": "feature"}

        elif node_name == "07_patcher":
            # P3.0 真功能: 调 verifier.py
            run_result = intermediate.get("05_runner", {})
            output = patcher_v5(run_result)

        elif node_name == "08_reporter":
            context_parts = []
            for k, v in intermediate.items():
                if isinstance(v, dict):
                    context_parts.append(f"[{k}] {v.get('step', '?')}: {str(v)[:200]}")
                else:
                    context_parts.append(f"[{k}] {str(v)[:200]}")
            context = "\n".join(context_parts)
            final = _call_llm_14b(
                system="你是 mavis 报告员, 综合所有节点输出给出最终答案。",
                user=f"用户 query: {query}\n机制: {mechanism}\n\n节点输出汇总:\n{context}\n\n请给出最终答案 (中文, 简洁直接, 300 字内)。"
            )
            output = {"final": final, "step": "report"}

        elif node_name == "09_decision":
            decision = _call_llm_14b(
                system="你是 mavis 决策员, 决定 continue / terminate / revise",
                user=f"用户 query: {query}\n当前 turn: {turn}\n请输出 1 个决策"
            )
            decision_action = "continue"
            for kw in ["terminate", "revise", "continue"]:
                if kw in decision.lower():
                    decision_action = kw
                    break
            output = {"decision": decision_action, "step": "decision"}

        else:
            output = {"error": f"unknown node {node_name}"}

        elapsed = time.time() - t0
        intermediate = {**intermediate, node_name: output}
        new_state = {
            "current_node": node_name,
            "current_turn": turn,
            "step_history": history,
            "intermediate_outputs": intermediate,
        }
        if node_name == "00_router":
            new_state["dynamic_nodes"] = output.get("selected_nodes", [])
        if node_name == "07_patcher":
            new_state["last_approved"] = output.get("approved", False)
        if node_name == "05_runner":
            new_state["exit_code"] = output.get("exit_code", 0)
        if node_name == "08_reporter":
            new_state["final_answer"] = output.get("final", "")
        print(f"   [{node_name}] {elapsed:.2f}s | {output.get('step', '?')}")
        return new_state

    return node_function


# === Conditional Edges (跟 P2.y/z 一样) ===

def should_continue_after_runner(state: AdaptiveStateV5) -> str:
    return "08_reporter" if state.get("exit_code", 0) == 0 else "07_patcher"


def should_continue_after_patcher(state: AdaptiveStateV5) -> str:
    if state.get("last_approved", False):
        return "08_reporter"
    if state.get("current_turn", 0) >= state.get("max_turns", 3):
        return "08_reporter"
    return "05_runner"


def decision_route(state: AdaptiveStateV5) -> str:
    decision = state.get("intermediate_outputs", {}).get("09_decision", {}).get("decision", "continue")
    if decision == "revise":
        return "01_planner"
    return "08_reporter"


# === 动态 subgraph 构建 (P3.0 跟 P2.z 一样) ===

def build_adaptive_subgraph_v5(query: str, mechanism: str, eight_mech_router: EightMechRouter, max_turns: int = 3):
    router_func = make_node_v5("00_router", eight_mech_router)
    initial_state: AdaptiveStateV5 = {
        "query": query, "routed_mechanism": mechanism, "routing_method": "P1.4",
        "current_turn": 0, "max_turns": max_turns, "last_approved": False, "exit_code": 0,
        "current_node": "", "step_history": [], "intermediate_outputs": {}, "final_answer": "",
    }
    state_after_router = router_func(initial_state)
    nodes_to_run = state_after_router.get("dynamic_nodes", ["01_planner", "02_researcher", "04_action", "08_reporter"])
    if "08_reporter" not in nodes_to_run:
        nodes_to_run.append("08_reporter")

    print(f"\n🔀 动态 subgraph 构建 (P3.0 完整版)")
    print(f"   机制: {mechanism}")
    print(f"   00_router 决定: {nodes_to_run} ({len(nodes_to_run)}/{len(ALL_10_NODES)-1})")
    print(f"   max_turns: {max_turns}")

    state: AdaptiveStateV5 = {
        **initial_state,
        "dynamic_nodes": nodes_to_run,
        "intermediate_outputs": {**state_after_router.get("intermediate_outputs", {})},
    }

    workflow = StateGraph(AdaptiveStateV5)
    for n in nodes_to_run:
        workflow.add_node(n, make_node_v5(n, eight_mech_router))

    workflow.add_edge(START, nodes_to_run[0])
    for i in range(len(nodes_to_run) - 1):
        cur, nxt = nodes_to_run[i], nodes_to_run[i + 1]
        if cur == "05_runner" and nxt == "07_patcher":
            workflow.add_conditional_edges("05_runner", should_continue_after_runner, {"07_patcher": "07_patcher", "08_reporter": "08_reporter"})
        elif cur == "07_patcher" and nxt == "05_runner":
            workflow.add_conditional_edges("07_patcher", should_continue_after_patcher, {"05_runner": "05_runner", "08_reporter": "08_reporter"})
        elif cur == "09_decision" and nxt == "08_reporter":
            workflow.add_conditional_edges("09_decision", decision_route, {"01_planner": "01_planner", "08_reporter": "08_reporter"})
        else:
            workflow.add_edge(cur, nxt)

    workflow.add_edge(nodes_to_run[-1], END)
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)
    return app, state, nodes_to_run


# === 主入口 ===

def run_adaptive_v5(query: str, max_turns: int = 3) -> dict:
    print("=" * 60)
    print("mavis Adaptive Runtime v5 - P3.0 完整版")
    print("永久 invariant #41: P1.1.a 真功能 + P2.z adaptive 框架")
    print("=" * 60)
    print(f"Query: {query}")

    kw_matches = route_by_keywords(query)
    if kw_matches:
        mechanism = kw_matches[0][0]
        routing_method = "关键词"
    else:
        mechanism = call_llm_router(query, EIGHT_MECHANISMS) or "子智能体"
        routing_method = "LLM 兜底"
    print(f"\n🎯 路由结果: {mechanism} (方法: {routing_method})")

    eight_mech_router = EightMechRouter(top_k=3)
    app, initial_state, nodes_to_run = build_adaptive_subgraph_v5(query, mechanism, eight_mech_router, max_turns)

    t0 = time.time()
    config = {"configurable": {"thread_id": "p3-session-1"}}
    result = app.invoke(initial_state, config=config)
    elapsed = time.time() - t0

    cycle_report = {
        "query": query,
        "routed_mechanism": mechanism,
        "routing_method": routing_method,
        "00_router_decision": result.get("dynamic_nodes", []),
        "nodes_run": nodes_to_run,
        "node_count": len(nodes_to_run),
        "step_history": result.get("step_history", []),
        "intermediate_outputs": result.get("intermediate_outputs", {}),
        "final_answer": result.get("final_answer", ""),
        "elapsed_s": round(elapsed, 2),
        "all_10_nodes": ALL_10_NODES,
        "max_turns": max_turns,
        "current_turn": result.get("current_turn", 0),
        "completed_at": datetime.now().isoformat(),
    }
    CYCLE_REPORT.write_text(json.dumps(cycle_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 最终答案 ===")
    print(cycle_report["final_answer"][:500] if cycle_report["final_answer"] else "(无)")
    print(f"\n⏱️  总耗时: {cycle_report['elapsed_s']}s, turn: {cycle_report['current_turn']}/{max_turns}")
    print(f"📋 报告: {CYCLE_REPORT}")
    return cycle_report


# === 8 query 实战验证 ===

ADAPTIVE_V5_TEST_QUERIES = [
    "CLAUDE.md 五层记忆 怎么 auto-inject",
    "mavis 子智能体 5 模式 怎么用",
    "mavis Skills AWEL 三层架构 是什么",
    "mavis Hooks block-dangerous 怎么拦截",
    "mavis MCP 6 server 怎么注册",
    "mavis Headless --max-turns CI/CD 怎么跑",
    "mavis Agent SDK @tool 装饰器 怎么定义",
    "mavis Plugins plugin.json install CLI",
]


def run_8mech_adaptive_v5_test():
    print("=" * 60)
    print("P3.0 实战验证 - 8 机制 query 跑 adaptive runtime v5 (P1.1.a 真功能)")
    print("=" * 60)

    results = []
    for i, q in enumerate(ADAPTIVE_V5_TEST_QUERIES, 1):
        print(f"\n[Test {i}/8] {q}")
        try:
            report = run_adaptive_v5(q)
            expected = EIGHT_MECHANISMS[i-1]["name"]
            correct = (report["routed_mechanism"] == expected)
            report["expected_mechanism"] = expected
            report["routing_correct"] = correct
            results.append(report)
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append({"query": q, "error": str(e)})

    report_path = P30_DIR / "adaptive-v5-test-results.json"
    valid_results = [r for r in results if "error" not in r]
    avg_elapsed = round(sum(r.get("elapsed_s", 0) for r in valid_results) / len(valid_results), 2) if valid_results else 0
    avg_nodes = round(sum(len(r.get("00_router_decision", [])) for r in valid_results) / len(valid_results), 1) if valid_results else 0
    # 统计 P1.1.a 真功能调用
    p1_1a_calls = {"researcher": 0, "coder": 0, "runner": 0, "patcher": 0}
    for r in valid_results:
        for n in r.get("step_history", []):
            if n == "02_researcher": p1_1a_calls["researcher"] += 1
            elif n == "03_coder": p1_1a_calls["coder"] += 1
            elif n == "05_runner": p1_1a_calls["runner"] += 1
            elif n == "07_patcher": p1_1a_calls["patcher"] += 1

    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "routing_accuracy": sum(1 for r in results if r.get("routing_correct")) / len(results) if results else 0,
        "avg_elapsed_s": avg_elapsed,
        "avg_node_count": avg_nodes,
        "p1_1a_real_calls": p1_1a_calls,
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"📊 8 机制路由准确率: {sum(1 for r in results if r.get('routing_correct'))}/{len(results)}")
    print(f"⏱️  平均耗时: {avg_elapsed} 秒/次")
    print(f"📊 P1.1.a 真功能调用: {p1_1a_calls}")
    print(f"📋 报告: {report_path}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        run_8mech_adaptive_v5_test()
    else:
        q = sys.argv[1]
        mt = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        run_adaptive_v5(q, max_turns=mt)
