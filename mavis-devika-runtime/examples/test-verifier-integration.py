#!/usr/bin/env python3
"""
mavis devika runtime - 真实集成 verifier v2 测试

用法: conda run -n part03 python examples/test-verifier-integration.py
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import runtime
from runtime import (
    init_context, build_workflow, DevikaContext,
    node_05_runner, node_07_patcher, node_08_reporter,
    should_continue_after_runner, should_continue_after_patcher,
    node_01_planner
)
from langgraph.graph import StateGraph, END, START

def node_05_runner_fail(state):
    return {
        "run_result": {
            "exit_code": 1,
            "stdout": "",
            "stderr": "Simulated execution failure for verifier integration test",
            "duration_ms": 50
        },
        "last_approved": False,
        "node_history": ["05_runner"],
        "messages": [{"role": "assistant", "content": "[Runner] FAILED"}]
    }


def main():
    print("=" * 60)
    print("真实集成测试: Patcher → mavis-verifier-v2")
    print("=" * 60)

    workflow = StateGraph(DevikaContext)
    workflow.add_node("05_runner", node_05_runner_fail)
    workflow.add_node("07_patcher", node_07_patcher)  # 真实调用 verifier
    workflow.add_node("08_reporter", node_08_reporter)

    workflow.add_edge(START, "05_runner")
    workflow.add_conditional_edges(
        "05_runner", should_continue_after_runner,
        {"07_patcher": "07_patcher", "08_reporter": "08_reporter"}
    )
    workflow.add_conditional_edges(
        "07_patcher", should_continue_after_patcher,
        {"05_runner": "05_runner", "08_reporter": "08_reporter"}
    )
    workflow.add_edge("08_reporter", END)

    app = workflow.compile()
    initial_state = init_context("测试 verifier 集成", max_turns=2)
    config = {"configurable": {"thread_id": "verifier-test"}, "recursion_limit": 10}

    final_state = app.invoke(initial_state, config=config)

    print("\n" + "=" * 60)
    print("=== 集成测试结果 ===")
    print(f"节点历史: {' -> '.join(final_state.get('node_history', []))}")
    patch = final_state.get("patch", {})
    print(f"Patcher root_cause: {patch.get('root_cause', '')[:200]}")
    print(f"Tests: {patch.get('tests', [])}")
    print("=" * 60)


if __name__ == "__main__":
    main()