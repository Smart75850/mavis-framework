#!/usr/bin/env python3
"""
mavis Adaptive Runtime - P2.x 融合
永久 invariant #38: 9 节点 LangGraph + 8 机制 query 路由 = mavis adaptive runtime
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #36: LlamaIndex 4 步索引 = mavis memory RAG
永久 invariant #37: mavis 8 机制 query 路由

P2.x 融合 P1.1.a (9 节点) + P1.4 (8 机制 query 路由):
- 入口: user query
- 8 机制 query 路由 → 选节点子集
- 动态构建 LangGraph subgraph
- 跑 subgraph
- 输出 cycle 报告

用法: python adaptive_runtime.py "<query>"
"""
import sys
import os
import json
import time
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

# 复用 P1.3 / P1.4
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))

from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL
from llama_index.core import Settings
from llama_index.llms.ollama import Ollama

from router import EIGHT_MECHANISMS, route_by_keywords, call_llm_router, EightMechRouter


# === P2.x 路径配置 ===
P2_DIR = Path(__file__).parent
CYCLE_REPORT = P2_DIR / "cycle-report.json"
P2_DIR.mkdir(parents=True, exist_ok=True)


# === 8 机制 → 节点子集映射 (P2.x 核心) ===

# 9 节点名称 (跟 P1.1.a 一致)
ALL_NODES = [
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

# 8 机制 → 节点子集
MECHANISM_TO_NODES = {
    "CLAUDE.md": ["01_planner", "02_researcher", "08_reporter"],
    "子智能体": ["01_planner", "02_researcher", "03_coder", "05_runner", "07_patcher", "08_reporter"],
    "Skills": ["02_researcher", "03_coder", "08_reporter"],
    "Hooks": ["02_researcher", "03_coder", "07_patcher", "08_reporter"],
    "MCP": ["02_researcher", "03_coder", "05_runner", "08_reporter"],
    "Headless": ["01_planner", "05_runner", "08_reporter"],
    "Agent SDK": ["01_planner", "02_researcher", "03_coder", "05_runner", "07_patcher", "08_reporter"],
    "Plugins": ["01_planner", "02_researcher", "03_coder", "08_reporter"],
}


# === LangGraph State ===

class AdaptiveState(TypedDict, total=False):
    """P2.x adaptive runtime state"""
    query: str                    # 用户 query
    routed_mechanism: str         # 8 机制路由结果
    routing_method: str           # 关键词 / LLM
    nodes_to_run: List[str]       # 选中的节点
    current_node: str             # 当前执行节点
    step_history: List[str]       # 节点历史
    intermediate_outputs: Dict[str, Any]  # 各节点输出
    final_answer: str             # 最终答案
    cycle_report: Dict[str, Any]  # cycle 报告


# === 6 个轻量版节点 (P2.x 简化版, 复用 P1.4 query_engine + 14B) ===

def make_node_function(node_name: str, eight_mech_router: EightMechRouter) -> Callable:
    """动态生成节点函数 (避免 9 个 hardcode 函数)"""

    def node_function(state: AdaptiveState) -> AdaptiveState:
        t0 = time.time()
        query = state.get("query", "")
        mechanism = state.get("routed_mechanism", "")
        history = state.get("step_history", [])
        intermediate = state.get("intermediate_outputs", {})
        history = history + [node_name]

        # 节点逻辑
        if node_name == "01_planner":
            # Planner: 制定子计划 (LLM 14B)
            plan = _call_llm_14b(
                system="你是 mavis 计划员, 根据用户 query 制定 3 步子计划。",
                user=f"用户 query: {query}\n机制: {mechanism}\n请输出 3 步子计划, 简洁直接。"
            )
            output = {"plan": plan, "step": "plan"}

        elif node_name == "02_researcher":
            # Researcher: 调 P1.4 query_engine 检索 + 总结
            result = eight_mech_router.query(query)
            output = {
                "research": result["answer"][:500],
                "sources": [s["file"] for s in result["sources"][:3]],
                "step": "research"
            }

        elif node_name == "03_coder":
            # Coder: 调 14B LLM 生成代码 / 方案
            code = _call_llm_14b(
                system="你是 mavis 程序员, 根据 query + 检索结果生成代码或方案。",
                user=f"用户 query: {query}\n请生成代码或方案。"
            )
            output = {"code": code[:500], "step": "code"}

        elif node_name == "04_action":
            # Action: 直接 action (P2.x 简化: skip, 输出 placeholder)
            output = {"action": "executed", "step": "action"}

        elif node_name == "05_runner":
            # Runner: mock 运行 + 验证 (P2.x 简化)
            output = {"run_result": "mock_ok", "exit_code": 0, "step": "run"}

        elif node_name == "06_feature":
            # Feature: 添加新特性 (P2.x 简化: skip)
            output = {"feature": "added", "step": "feature"}

        elif node_name == "07_patcher":
            # Patcher: 修复 (P2.x 简化: output "no patch needed")
            output = {"patch": "no patch needed", "step": "patch"}

        elif node_name == "08_reporter":
            # Reporter: 汇总所有 intermediate + 调 14B 输出最终答案
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
            # Decision: 决策 (P2.x 简化)
            output = {"decision": "approved", "step": "decision"}

        else:
            output = {"error": f"unknown node {node_name}"}

        # 更新 state
        elapsed = time.time() - t0
        intermediate = {**intermediate, node_name: output}
        new_state = {
            "current_node": node_name,
            "step_history": history,
            "intermediate_outputs": intermediate,
        }
        # Reporter 后写 final_answer
        if node_name == "08_reporter":
            new_state["final_answer"] = output.get("final", "")
        # 打印
        print(f"   [{node_name}] {elapsed:.2f}s | {output.get('step', '?')}")
        return new_state

    return node_function


def _call_llm_14b(system: str, user: str) -> str:
    """调 Ollama 14B, 走 HTTP API"""
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
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"[LLM_ERROR] {e}"


# === 动态 subgraph 构建 ===

def build_adaptive_subgraph(query: str, mechanism: str, eight_mech_router: EightMechRouter):
    """根据 8 机制 → 选节点 → 动态构建 LangGraph subgraph"""

    nodes_to_run = MECHANISM_TO_NODES.get(mechanism, ["01_planner", "02_researcher", "08_reporter"])
    print(f"\n🔀 动态 subgraph 构建")
    print(f"   机制: {mechanism}")
    print(f"   节点子集: {nodes_to_run} ({len(nodes_to_run)}/{len(ALL_NODES)})")

    # 状态
    state: AdaptiveState = {
        "query": query,
        "routed_mechanism": mechanism,
        "routing_method": "P1.4",
        "nodes_to_run": nodes_to_run,
        "current_node": "",
        "step_history": [],
        "intermediate_outputs": {},
        "final_answer": "",
    }

    # 构建 StateGraph
    workflow = StateGraph(AdaptiveState)

    # 加节点
    node_funcs = {}
    for n in nodes_to_run:
        node_funcs[n] = make_node_function(n, eight_mech_router)
        workflow.add_node(n, node_funcs[n])

    # 加边 (按 P1.1.a 默认顺序: 01→02→03→05→07→08, 简化: 顺序串联)
    workflow.add_edge(START, nodes_to_run[0])
    for i in range(len(nodes_to_run) - 1):
        workflow.add_edge(nodes_to_run[i], nodes_to_run[i + 1])
    workflow.add_edge(nodes_to_run[-1], END)

    # 编译
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app, state, nodes_to_run


# === 主入口 ===

def run_adaptive(query: str) -> dict:
    """P2.x 主入口"""
    print("=" * 60)
    print("mavis Adaptive Runtime - P2.x 融合")
    print("永久 invariant #38: 9 节点 LangGraph + 8 机制 query 路由")
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

    # 2. 初始化 8 机制 router
    eight_mech_router = EightMechRouter(top_k=3)

    # 3. 构建 + 跑 subgraph
    app, initial_state, nodes_to_run = build_adaptive_subgraph(query, mechanism, eight_mech_router)

    # 4. 跑 workflow
    t0 = time.time()
    config = {"configurable": {"thread_id": "p2x-session-1"}}
    result = app.invoke(initial_state, config=config)
    elapsed = time.time() - t0

    # 5. 输出报告
    cycle_report = {
        "query": query,
        "routed_mechanism": mechanism,
        "routing_method": routing_method,
        "nodes_to_run": nodes_to_run,
        "node_count": len(nodes_to_run),
        "node_savings_pct": round((1 - len(nodes_to_run) / len(ALL_NODES)) * 100, 1),
        "step_history": result.get("step_history", []),
        "intermediate_outputs": result.get("intermediate_outputs", {}),
        "final_answer": result.get("final_answer", ""),
        "elapsed_s": round(elapsed, 2),
        "all_nodes": ALL_NODES,
        "completed_at": datetime.now().isoformat(),
    }
    CYCLE_REPORT.write_text(json.dumps(cycle_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 最终答案 ===")
    print(cycle_report["final_answer"][:500] if cycle_report["final_answer"] else "(无)")
    print(f"\n📊 节点节省: {cycle_report['node_savings_pct']}% ({len(nodes_to_run)}/{len(ALL_NODES)})")
    print(f"⏱️  总耗时: {cycle_report['elapsed_s']}s")
    print(f"📋 报告: {CYCLE_REPORT}")

    return cycle_report


# === 8 个 query 实战验证 ===

ADAPTIVE_TEST_QUERIES = [
    "CLAUDE.md 五层记忆 怎么 auto-inject",
    "mavis 子智能体 5 模式 怎么用",
    "mavis Skills AWEL 三层架构 是什么",
    "mavis Hooks block-dangerous 怎么拦截",
    "mavis MCP 6 server 怎么注册",
    "mavis Headless --max-turns CI/CD 怎么跑",
    "mavis Agent SDK @tool 装饰器 怎么定义",
    "mavis Plugins plugin.json install CLI",
]


def run_8mech_adaptive_test():
    """跑 8 个机制 query 验证 adaptive runtime"""
    print("=" * 60)
    print("P2.x 实战验证 - 8 机制 query 跑 adaptive runtime")
    print("=" * 60)

    results = []
    for i, q in enumerate(ADAPTIVE_TEST_QUERIES, 1):
        print(f"\n[Test {i}/8] {q}")
        try:
            report = run_adaptive(q)
            expected = EIGHT_MECHANISMS[i-1]["name"]
            correct = (report["routed_mechanism"] == expected)
            report["expected_mechanism"] = expected
            report["routing_correct"] = correct
            results.append(report)
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append({"query": q, "error": str(e)})

    # 写报告
    report_path = P2_DIR / "adaptive-test-results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "routing_accuracy": sum(1 for r in results if r.get("routing_correct")) / len(results) if results else 0,
        "avg_elapsed_s": round(sum(r.get("elapsed_s", 0) for r in results) / len(results), 2) if results else 0,
        "avg_node_savings_pct": round(sum(r.get("node_savings_pct", 0) for r in results) / len(results), 1) if results else 0,
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"📊 路由准确率: {sum(1 for r in results if r.get('routing_correct'))}/{len(results)}")
    print(f"⏱️  平均耗时: {report_path.read_text().split('avg_elapsed_s\":')[1].split(',')[0]} 秒/次")
    print(f"📋 报告: {report_path}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 默认跑 8 个机制测试
        run_8mech_adaptive_test()
    else:
        # python adaptive_runtime.py "<query>"
        run_adaptive(sys.argv[1])
