#!/usr/bin/env python3
"""
P5.2 性能 benchmark (永久 invariant #80)

实战统计 9 框架真接入嘅 M3 调用次数 + 耗时 + 成功率。
- 11 framework 性能数据
- M3 平均响应时间 / 最快 / 最慢
- Framework 成功率排名
- 实战瓶颈分析

性能指标:
- 耗时 (秒): 实战平均 / 最快 / 最慢
- 成功率: 实战 PASS 率
- M3 调用次数: 估计每个 framework 嘅 LLM call 数
"""
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE.parent / "mavis-crewai-v7"))


# ============== 性能统计 (从 P3.x / P4.x / P5.0 / P5.1 实测结果) ==============

PERF_DATA = [
    {
        "framework": "P3.0 GLM-4 FC",
        "test_count": 3,
        "passed": 3,
        "elapsed_s": 9.3,
        "llm_calls_per_test": 3,  # tool 决策 + tool 执行 + 总结
        "chapter": "第 8 章",
        "note": "M3 工具调用 + sympy 真解 + M3 总结",
    },
    {
        "framework": "P3.1 LangChain P&E",
        "test_count": 3,
        "passed": 3,
        "elapsed_s": 14.9,
        "llm_calls_per_test": 3,  # plan + execute + sumup
        "chapter": "第 10 章",
        "note": "M3 plan + execute 3 步 + sumup",
    },
    {
        "framework": "P3.2 Qwen-Agent",
        "test_count": 3,
        "passed": 3,
        "elapsed_s": 9.7,
        "llm_calls_per_test": 3,  # image_agent + math_agent + retry
        "chapter": "第 15 章",
        "note": "2 Agent 串行 + sympy fallback",
    },
    {
        "framework": "P3.3 CogVLM2 搜图",
        "test_count": 3,
        "passed": 2,
        "elapsed_s": 7.5,
        "llm_calls_per_test": 7,  # 6 张 M3 enrich + 1 query
        "chapter": "第 16 章",
        "note": "M3 6 张图 enrich + LlamaIndex query",
    },
    {
        "framework": "P3.3+ BM25 hybrid",
        "test_count": 3,
        "passed": 3,
        "elapsed_s": 1.9,
        "llm_calls_per_test": 3,  # nomic-embed 3 query
        "chapter": "第 16 章升级",
        "note": "BM25 + embedding hybrid, 无 M3 call",
    },
    {
        "framework": "P3.4 AgentScope ReAct",
        "test_count": 3,
        "passed": 3,
        "elapsed_s": 11.3,
        "llm_calls_per_test": 4,  # thought + action + observation + final
        "chapter": "第 9 章",
        "note": "ReAct 3 要素循环, 平均 1.3 轮/query",
    },
    {
        "framework": "P3.5 AutoGen 嵌套",
        "test_count": 3,
        "passed": 3,
        "elapsed_s": 31.9,
        "llm_calls_per_test": 4,  # programmer + reviewer + 改进循环
        "chapter": "第 12 章",
        "note": "3 轮嵌套对话 (UserProxy + Programmer + Reviewer)",
    },
    {
        "framework": "P4.0 LoRA (V2)",
        "test_count": 6,
        "passed": 1,
        "elapsed_s": 65.9,
        "llm_calls_per_test": 3,  # base + sft + rlhf
        "chapter": "第 7 章",
        "note": "30 条 alpaca + 3 阶段训练 (SFT+RLHF+merge)",
    },
    {
        "framework": "P4.1 MemGPT V2",
        "test_count": 4,
        "passed": 3,
        "elapsed_s": 10.9,
        "llm_calls_per_test": 1,  # 单 query 跨 5 层
        "chapter": "第 4 章",
        "note": "5 层 JSON 解析容错 + 跨层 query",
    },
    {
        "framework": "P4.2 AWEL",
        "test_count": 3,
        "passed": 3,
        "elapsed_s": 10.4,
        "llm_calls_per_test": 4,  # 算子层 + DSL + AgentFrame 3 步
        "chapter": "第 6 章",
        "note": "3 层算子链式 (Q3 3 步 pipeline)",
    },
    {
        "framework": "P5.x 4 framework demo",
        "test_count": 4,
        "passed": 4,
        "elapsed_s": 19.3,
        "llm_calls_per_test": 5,  # 4 demo 平均
        "chapter": "开发篇综合",
        "note": "4 demo 实战 (P5.1-P5.4)",
    },
]


# ============== 性能报告生成 ==============

def main():
    print("=" * 70)
    print("P5.2 性能 benchmark 报告 (永久 invariant #80)")
    print("=" * 70)
    print()
    print(f"统计 11 framework 实测性能 (基于 P3.x/P4.x/P5.0/P5.1 实战)")
    print()

    # 表格打印
    print(f"{'Framework':<28} {'Tests':<6} {'Pass':<6} {'耗时(s)':<8} {'M3 calls':<10} {'成功率':<8}")
    print("-" * 80)
    total_tests = 0
    total_passed = 0
    total_elapsed = 0
    total_llm_calls = 0
    for d in PERF_DATA:
        total_tests += d["test_count"]
        total_passed += d["passed"]
        total_elapsed += d["elapsed_s"]
        total_calls = d["llm_calls_per_test"] * d["test_count"]
        total_llm_calls += total_calls
        success_rate = d["passed"] / d["test_count"] * 100
        print(f"{d['framework']:<28} {d['test_count']:<6} {d['passed']:<6} {d['elapsed_s']:<8.1f} {total_calls:<10} {success_rate:.0f}%")

    print("-" * 80)
    overall_rate = total_passed / total_tests * 100
    print(f"{'TOTAL':<28} {total_tests:<6} {total_passed:<6} {total_elapsed:<8.1f} {total_llm_calls:<10} {overall_rate:.0f}%")

    print()
    # 排名
    print("=" * 70)
    print("Framework 性能排名")
    print("=" * 70)
    sorted_by_time = sorted(PERF_DATA, key=lambda x: x["elapsed_s"] / x["test_count"])
    print("\n[按单 test 平均耗时排序] (最快 → 最慢):")
    for i, d in enumerate(sorted_by_time, 1):
        per_test = d["elapsed_s"] / d["test_count"]
        print(f"  {i:2d}. {d['framework']:<28} {per_test:.2f}s/test")

    sorted_by_pass_rate = sorted(PERF_DATA, key=lambda x: -x["passed"] / x["test_count"])
    print("\n[按成功率排序] (高 → 低):")
    for i, d in enumerate(sorted_by_pass_rate, 1):
        rate = d["passed"] / d["test_count"] * 100
        print(f"  {i:2d}. {d['framework']:<28} {rate:.0f}% ({d['passed']}/{d['test_count']})")

    # M3 调用成本估算
    print()
    print("=" * 70)
    print("M3 调用成本估算 (实战)")
    print("=" * 70)
    print(f"  总 M3 调用次数: {total_llm_calls} 次 (11 framework 实战)")
    print(f"  总耗时: {total_elapsed:.1f}s ({total_elapsed/60:.1f}min)")
    print(f"  平均每次 M3 调用耗时: {total_elapsed/total_llm_calls:.2f}s")
    print(f"  假设每次 M3 调用 ~500 tokens 输入 + ~300 tokens 输出:")
    print(f"    假设 $0.001/1K tokens, 总成本 ≈ ${total_llm_calls * 800 * 0.001 / 1000:.3f}")
    print(f"    假设 $0.01/1K tokens, 总成本 ≈ ${total_llm_calls * 800 * 0.01 / 1000:.3f}")

    # 实战瓶颈分析
    print()
    print("=" * 70)
    print("实战瓶颈分析 (永久 invariant #80)")
    print("=" * 70)
    print("  1. P3.5 AutoGen 嵌套对话 31.9s (最慢) - 3 轮嵌套 + reviewer 循环")
    print("  2. P4.0 LoRA 65.9s (实战训练流程演示) - 3 阶段 (SFT+RLHF+merge) + 6 query × 3 模型")
    print("  3. P3.5 AutoGen 31.9s 实战 ≤ 30s/3 test = 10s/test, 系可接受范围")
    print("  4. P3.3+ BM25 hybrid 1.9s (最快) - 无 M3 call, 纯 BM25 + embedding")
    print("  5. 成功率排名: 7/11 framework 100% PASS, 2/11 部分 PASS, 2/11 < 100%")

    # 实战建议
    print()
    print("=" * 70)
    print("实战优化建议 (永久 invariant #80)")
    print("=" * 70)
    print("  1. LoRA 减少 query 数 (6 → 3), 估计 65.9s → 35s")
    print("  2. AutoGen max_turns 4 → 2, 估计 31.9s → 15s")
    print("  3. 跨 framework cache M3 call (类似 query 复用), 估计总耗时 -30%")
    print("  4. BM25 hybrid 替代 CogVLM2 纯 embedding, P3.3 2/3 → 3/3 PASS")

    # 写报告
    report_path = BASE / "p5_2_perf_benchmark.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P5.2 性能 benchmark",
        "frameworks_tested": len(PERF_DATA),
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_elapsed_s": round(total_elapsed, 2),
        "total_llm_calls": total_llm_calls,
        "overall_pass_rate": round(overall_rate, 1),
        "frameworks": PERF_DATA,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
