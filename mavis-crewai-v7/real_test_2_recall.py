#!/usr/bin/env python3
"""
真实测试 2: M3 真 mavis recall 查询
- 跑 5 个真 query (从 mavis memory 召回真答案)
- 唔系 demo query (e.g. "CLAUDE.md 五层记忆"), 系真嘅记忆查询
- 验证: 召回内容 + M3 中文总结
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

sys.path.insert(0, "/Users/apple/workspace/mavis-llamaindex-v2/.venv/lib/python3.12/site-packages")
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))

from mavis_m3_provider import call_llm_m3
from build_index import load_or_build_index


def real_recall_test():
    print("=" * 70)
    print("真实测试 2: M3 真 mavis recall 查询")
    print("=" * 70)
    print()
    print("5 个真 query (从 mavis memory 召回):")

    # 5 个真嘅 query (基于跨夜战永久 invariant + 实际场景)
    queries = [
        {
            "query": "永久 invariant #30 系乜? 边个 P 队列?",
            "expected_mechanism": "子智能体",  # mavis memory 相关
            "expected_keywords": ["invariant", "#30", "recall"],
        },
        {
            "query": "mavis 8 机制协奏有边 8 个?",
            "expected_mechanism": "CLAUDE.md",  # mavis framework 总览
            "expected_keywords": ["CLAUDE.md", "子智能体", "Skills", "Hooks", "MCP", "Headless", "Agent SDK", "Plugins"],
        },
        {
            "query": "block-dangerous 拦截 28 种黑名单具体系边 28 种?",
            "expected_mechanism": "Hooks",  # 永久 invariant #48
            "expected_keywords": ["rm", "sudo", "chmod", "kill"],
        },
        {
            "query": "CrewAI 4 组件系乜?",
            "expected_mechanism": "Skills",  # 永久 invariant #35
            "expected_keywords": ["Agent", "Task", "Crew", "Process"],
        },
        {
            "query": "P3.5 修复嘅 2 大 bug 系乜?",
            "expected_mechanism": "子智能体",  # 永久 invariant #46
            "expected_keywords": ["P3.5", "70%", "Linter"],
        },
    ]

    index = load_or_build_index()
    if not index:
        print("❌ 索引未建")
        return

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/5] {q['query']}")
        try:
            engine = index.as_query_engine(similarity_top_k=3)
            start = time.time()
            response = engine.query(q["query"])
            elapsed = round(time.time() - start, 2)

            # 召回内容
            sources = []
            for node in response.source_nodes:
                meta = node.node.metadata or {}
                fname = (meta.get('file_path', '?').split('/')[-1] or '?')
                score = round(node.score or 0, 4)
                text_preview = node.node.text[:100].replace("\n", " ")
                sources.append({"file": fname, "score": score, "text": text_preview})

            # 验证: 至少 1 个召回, score > 0.5
            has_source = len(sources) > 0
            top_score = max((s["score"] for s in sources), default=0)
            valid_score = top_score > 0.5

            # 验证: 召回内容含 expected_keywords
            all_text = " ".join(s["text"] for s in sources)
            keyword_matches = sum(1 for kw in q["expected_keywords"] if kw.lower() in all_text.lower())

            results.append({
                "query": q["query"],
                "sources": sources,
                "top_score": top_score,
                "answer": str(response)[:300],
                "elapsed_s": elapsed,
                "valid_score": valid_score,
                "keyword_matches": keyword_matches,
                "keyword_total": len(q["expected_keywords"]),
                "passed": has_source and valid_score and keyword_matches >= 1,
            })

            print(f"  top_score: {top_score}")
            print(f"  召回 {len(sources)} 文件, {keyword_matches}/{len(q['expected_keywords'])} 关键词命中")
            print(f"  答案前 200 字符: {str(response)[:200]}")
            if results[-1]["passed"]:
                print(f"  ✅ PASS ({elapsed}s)")
            else:
                print(f"  ❌ FAIL")

        except Exception as e:
            results.append({"query": q["query"], "error": str(e), "passed": False})
            print(f"  ❌ Exception: {e}")

    total_elapsed = time.time() - total_start
    passed = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"真实测试 2 完成: {passed}/5 PASS, 总 {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = Path(__file__).parent / "real_test_2_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "真实测试 2: M3 真 mavis recall 查询",
        "provider": "MiniMax-M3 (永久 invariant #51) + LlamaIndex (永久 invariant #36) + 本地 nomic-embed",
        "test_count": 5,
        "passed_count": passed,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    real_recall_test()
