#!/usr/bin/env python3
"""
真实测试 3: 8 机制路由真实 query (非预设)
- 跑 10 个真 query (唔系 8 机制测试 query, 系自然中文问句)
- 验证: 路由到正确机制 (期望 vs 实际)
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

sys.path.insert(0, "/Users/apple/workspace/mavis-llamaindex-v2/.venv/lib/python3.12/site-packages")
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))
from router import EightMechRouter, EIGHT_MECHANISMS


def real_router_test():
    print("=" * 70)
    print("真实测试 3: 8 机制路由真实 query (非预设, 10 个)")
    print("=" * 70)
    print()

    # 10 个真嘅自然中文 query (唔同预设 8 query, 模拟大佬实战)
    queries = [
        {
            "query": "我想喺 settings.json 装一个 PreToolUse 拦截器, 应该点写?",
            "expected": "Hooks",
        },
        {
            "query": "公司入面有 6 个 MCP server 注册咗, 我想加多一个点做?",
            "expected": "MCP",
        },
        {
            "query": "claude --max-turns 5 部署 CI 流水线, 点配置 GitHub Actions?",
            "expected": "Headless",
        },
        {
            "query": "我想做一个 @tool 函数, 用 Python 写一个 mavis 嘅 agent SDK",
            "expected": "Agent SDK",
        },
        {
            "query": "我项目入面个 AGENTS.md 冇生效, 点触发 auto-inject?",
            "expected": "CLAUDE.md",
        },
        {
            "query": "我想用 subagent 派几个 worker 去做 task, 点配置?",
            "expected": "子智能体",
        },
        {
            "query": "我开发咗一个 mavis 嘅 skill, 叫 weather-query, 怎么发布?",
            "expected": "Skills",
        },
        {
            "query": "我有个 mavis plugin, 喺 plugin.json 加咗 manifest, 点 install?",
            "expected": "Plugins",
        },
        {
            "query": "block-dangerous.sh 拦截 17/17 PASS, 点写?",
            "expected": "Hooks",
        },
        {
            "query": "headless mode 部署到 GitHub Actions, max-budget-usd 设定几多?",
            "expected": "Headless",
        },
    ]

    router = EightMechRouter(top_k=2)

    results = []
    for i, q in enumerate(queries):
        try:
            r = router.route_and_response(q["query"])
            actual = r["routed_mechanism"]
            method = r["routing_method"]
            expected = q["expected"]
            passed = actual == expected

            results.append({
                "query": q["query"],
                "expected": expected,
                "actual": actual,
                "method": method,
                "passed": passed,
            })

            marker = "✅" if passed else "❌"
            print(f"{marker} T{i+1} ({method}): {q['query'][:50]}...")
            print(f"   期望: {expected} | 实际: {actual}")

        except Exception as e:
            results.append({"query": q["query"], "expected": q["expected"], "error": str(e), "passed": False})
            print(f"❌ T{i+1} Exception: {e}")

    passed = sum(1 for r in results if r.get("passed"))
    print()
    print("=" * 70)
    print(f"真实测试 3 完成: {passed}/{len(queries)} PASS ({passed/len(queries)*100:.0f}%)")
    print("=" * 70)

    # 8 机制分布
    by_mech = {}
    for r in results:
        if r.get("actual"):
            by_mech[r["actual"]] = by_mech.get(r["actual"], 0) + 1
    print("\n机制分布:")
    for m, c in sorted(by_mech.items(), key=lambda x: -x[1]):
        print(f"  {m}: {c}")

    # 写报告
    report_path = Path(__file__).parent / "real_test_3_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "真实测试 3: 8 机制路由真实 query (非预设)",
        "test_count": len(queries),
        "passed_count": passed,
        "accuracy": round(passed/len(queries)*100, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {report_path}")


if __name__ == "__main__":
    real_router_test()
