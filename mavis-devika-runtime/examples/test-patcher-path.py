#!/usr/bin/env python3
"""
mavis devika runtime - 条件边测试 (触发 Patcher 路径)

用法: conda run -n part03 python examples/test-patcher-path.py
"""
import sys
import json
from pathlib import Path

# 允许从上级目录 import runtime
sys.path.insert(0, str(Path(__file__).parent.parent))
import runtime
from runtime import (
    init_context, build_workflow, DevikaContext,
    node_05_runner, node_07_patcher, node_08_reporter,
    should_continue_after_runner, should_continue_after_patcher
)

# 强制 Runner 失败的版本
def node_05_runner_fail(state: DevikaContext) -> dict:
    """故意失败的 Runner (测试 Patcher 路径)"""
    print("\n⚡ [05 Runner (FAIL)] 模拟失败...")
    return {
        "run_result": {
            "exit_code": 1,
            "stdout": "",
            "stderr": "Simulated failure for testing Patcher path",
            "duration_ms": 50
        },
        "last_approved": False,
        "node_history": ["05_runner"],
        "messages": [{"role": "assistant", "content": "[Runner] FAILED"}]
    }


def main():
    print("=" * 60)
    print("条件边测试: 强制 Runner 失败 -> 触发 Patcher 路径")
    print("=" * 60)

    # 构造一个简化的 workflow
    from langgraph.graph import StateGraph, END, START

    workflow = StateGraph(DevikaContext)
    workflow.add_node("05_runner", node_05_runner_fail)
    workflow.add_node("07_patcher", node_07_patcher)
    workflow.add_node("08_reporter", node_08_reporter)

    workflow.add_edge(START, "05_runner")
    workflow.add_conditional_edges(
        "05_runner",
        should_continue_after_runner,
        {
            "07_patcher": "07_patcher",
            "08_reporter": "08_reporter"
        }
    )
    workflow.add_conditional_edges(
        "07_patcher",
        should_continue_after_patcher,
        {
            "05_runner": "05_runner",
            "08_reporter": "08_reporter"
        }
    )
    workflow.add_edge("08_reporter", END)

    app = workflow.compile()
    initial_state = init_context("测试 Patcher 路径", max_turns=2)
    config = {"configurable": {"thread_id": "patcher-test"}}

    final_state = app.invoke(initial_state, config=config)

    print("\n" + "=" * 60)
    print("=== 测试结果 ===")
    print(f"节点历史: {' -> '.join(final_state.get('node_history', []))}")
    print(f"最终 approved: {final_state.get('last_approved', False)}")
    print(f"轮次: {final_state.get('current_turn', 0)}/{final_state.get('max_turns', 0)}")
    print(f"Patcher root_cause: {final_state.get('patch', {}).get('root_cause', '')[:200]}")
    print("=" * 60)

    # 验证条件边是否触发
    history = final_state.get("node_history", [])
    assert "07_patcher" in history, "❌ Patcher 没被触发"
    assert "08_reporter" in history, "❌ Reporter 没被触发"
    print("\n✅ 条件边验证通过: Runner FAIL -> Patcher -> Reporter")

if __name__ == "__main__":
    main()