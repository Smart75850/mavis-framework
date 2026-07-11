#!/usr/bin/env python3
"""
mavis memory LlamaIndex 查询入口 - P1.3
Step 4: Query 语义检索 + LLM 总结
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

from build_index import load_or_build_index, step4_query, CYCLE_REPORT


# === P1.3 实战测试 query (4 个, 验证 recall 优势) ===

P13_TEST_QUERIES = [
    # 1. keyword grep 召回 0 (mavis-orchestration.md 实际有, 但关键词不同)
    "mavis 协奏 8 机制 具体怎么算",
    # 2. keyword grep 召回 0 (近义不同词)
    "mavis 多智能体协同 8 个机制 怎么编排",
    # 3. 关键词不在 memory (LlamaIndex 应该在 #23-26 提到过)
    "LlamaIndex 4 步索引 是什么",
    # 4. 模糊查询 - 永久 invariant 关键词
    "14B 32B 模型怎么选 长期记忆",
]


def run_test_queries():
    print("=" * 60)
    print("P1.3 实战验证 - 4 个 query 测语义检索")
    print("=" * 60)

    index = load_or_build_index()
    results = []
    for i, q in enumerate(P13_TEST_QUERIES, 1):
        print(f"\n[Test {i}/{len(P13_TEST_QUERIES)}]")
        result = step4_query(index, q, top_k=3)
        results.append(result)
        print(f"   答案: {result['answer'][:300]}{'...' if len(result['answer']) > 300 else ''}")
        print(f"   耗时: {result['elapsed_s']}s")
        print(f"   召回 top-3:")
        for j, s in enumerate(result['sources'], 1):
            print(f"     [{j}] score={s['score']:.4f} file={s['file']}")
            print(f"         {s['text_preview']}...")

    # 写报告
    report_path = CYCLE_REPORT.parent / "query-test-results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n测试报告: {report_path}")

    return results


def run_custom_query(query: str, top_k: int = 3):
    """自定义 query"""
    index = load_or_build_index()
    return step4_query(index, query, top_k=top_k)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 默认跑 4 个测试 query
        run_test_queries()
    else:
        # python query.py "<custom query>" [top_k]
        query = sys.argv[1]
        top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        result = run_custom_query(query, top_k)
        print(f"\n答案: {result['answer']}")
        print(f"\n召回 top-{top_k}:")
        for i, s in enumerate(result['sources'], 1):
            print(f"  [{i}] {s['file']} (score={s['score']:.4f})")
            print(f"      {s['text_preview']}...")
