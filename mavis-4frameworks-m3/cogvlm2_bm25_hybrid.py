#!/usr/bin/env python3
"""
P3.3 BM25 + embedding hybrid 升级 (永久 invariant #73)

目标: 修复 P3.3 CogVLM2 Test 3 (红色跑车 误召回 动物) 召回问题
- 原方案: 仅 nomic-embed sentence embedding (nomic-embed 召回偏向暖色词)
- 升级方案: BM25 keyword + embedding cosine hybrid
  - BM25 score: keyword 命中权重 (红色 / 跑车 / 红色跑车 命中 redcar.png)
  - Embedding score: 语义相似度
  - Final score = 0.4 * BM25 + 0.6 * embedding (经验权重)

3 真 query (vs P3.3 2/3 PASS):
- Q1: 猫咪或者柴犬 (期望 cat/dog)
- Q2: 风景图 (期望 landscape)
- Q3: 红色跑车 (期望 redcar, 原 P3.3 失败)
"""
import sys
import os
import json
import time
import math
import re
from pathlib import Path
from datetime import datetime
from collections import Counter

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v7"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
from mavis_m3_provider import call_llm_m3


# ============== 6 张 mock 图库 (vs P3.3 同样) ==============

IMAGE_LIBRARY = [
    {"id": 1, "path": "/img/cat.png", "category": "动物", "description": "一只橙色嘅猫咪坐喺窗台, 望住外面嘅鸟"},
    {"id": 2, "path": "/img/dog.png", "category": "动物", "description": "一只黑色嘅柴犬喺公园跑步, 主人企喺旁边"},
    {"id": 3, "path": "/img/landscape.png", "category": "风景", "description": "中国桂林山水, 漓江上有一只竹筏"},
    {"id": 4, "path": "/img/sunset.png", "category": "风景", "description": "日落黄昏, 橙红色嘅太阳落喺海平线"},
    {"id": 5, "path": "/img/redcar.png", "category": "车辆", "description": "一辆红色嘅跑车停喺路边, 反射出嘅光好靓"},
    {"id": 6, "path": "/img/bluecar.png", "category": "车辆", "description": "一辆蓝色嘅轿车喺高速公路飞驰"},
]


# ============== BM25 keyword 评分 (永久 invariant #73) ==============

def bm25_score(query: str, doc: str, k1: float = 1.5, b: float = 0.75, avg_dl: float = 50.0) -> float:
    """BM25 评分 (简化版, 中文按 char 切分)"""
    # 简单中文按字符 + 2-gram 切分
    query_tokens = []
    for c in query:
        query_tokens.append(c)
    # 2-gram
    for i in range(len(query) - 1):
        query_tokens.append(query[i:i+2])
    query_tokens = [t for t in query_tokens if len(t) >= 1]
    query_tf = Counter(query_tokens)

    doc_tokens = []
    for c in doc:
        doc_tokens.append(c)
    for i in range(len(doc) - 1):
        doc_tokens.append(doc[i:i+2])
    doc_tokens = [t for t in doc_tokens if len(t) >= 1]
    doc_tf = Counter(doc_tokens)
    doc_len = len(doc_tokens)

    score = 0.0
    for term, qf in query_tf.items():
        if term in doc_tf:
            tf = doc_tf[term]
            # 简化 IDF = 1 (因为 corpus 只 6 docs, IDF 唔稳定)
            score += (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_dl))
    return score


# ============== Embedding 评分 (用 LlamaIndex + nomic-embed) ==============

def get_embedding(text: str) -> list:
    """用 nomic-embed 拿 embedding"""
    from build_index import HttpxOllamaEmbedding
    emb = HttpxOllamaEmbedding(model_name="nomic-embed-text")
    return emb._get_query_embedding(text)


def cosine_sim(a: list, b: list) -> float:
    """cosine 相似度"""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ============== Hybrid 检索 (永久 invariant #73) ==============

def hybrid_search(query: str, library: list, bm25_weight: float = 0.4, emb_weight: float = 0.6) -> list:
    """BM25 + embedding hybrid 检索"""
    # Step 1: BM25 keyword 评分
    bm25_scores = []
    for img in library:
        score = bm25_score(query, img["description"])
        bm25_scores.append(score)

    # 归一化 BM25
    max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
    bm25_norm = [s / max_bm25 for s in bm25_scores]

    # Step 2: Embedding 评分
    query_emb = get_embedding(query)
    emb_scores = []
    for img in library:
        img_emb = get_embedding(img["description"])
        sim = cosine_sim(query_emb, img_emb)
        emb_scores.append(sim)

    # 归一化 embedding (cosine 已经在 -1..1, 但实际系 0.5..0.8)
    max_emb = max(emb_scores) if max(emb_scores) > 0 else 1.0
    emb_norm = [s / max_emb for s in emb_scores]

    # Step 3: hybrid score
    hybrid_scores = [
        bm25_weight * b + emb_weight * e
        for b, e in zip(bm25_norm, emb_norm)
    ]

    # 排序
    results = []
    for i, img in enumerate(library):
        results.append({
            "id": img["id"],
            "path": img["path"],
            "category": img["category"],
            "bm25_score": round(bm25_norm[i], 4),
            "emb_score": round(emb_norm[i], 4),
            "hybrid_score": round(hybrid_scores[i], 4),
        })
    results.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return results


# ============== 实战: 3 真 query ==============

def main():
    print("=" * 70)
    print("P3.3 BM25 + embedding hybrid 升级 (永久 invariant #73)")
    print("=" * 70)
    print()
    print("目标: 修复 P3.3 Test 3 召回偏向 (红色跑车 → 误召回动物)")
    print("方案: BM25 keyword (0.4) + embedding cosine (0.6) hybrid")
    print()

    queries = [
        {
            "query": "猫咪或者柴犬",
            "expected_category": "动物",
            "expected_path": None,  # cat 或 dog 都 OK
            "expected_check": lambda top: top["category"] == "动物" and any(kw in top["path"] for kw in ["cat", "dog"]),
        },
        {
            "query": "风景图, 有山有水嗰种",
            "expected_category": "风景",
            "expected_check": lambda top: top["category"] == "风景",
        },
        {
            "query": "红色跑车",
            "expected_category": "车辆",
            "expected_path": "/img/redcar.png",  # 关键: 必须命中 redcar
            "expected_check": lambda top: top["path"] == "/img/redcar.png",
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['query']}")
        r = hybrid_search(q["query"], IMAGE_LIBRARY)

        top_match = r[0]
        value_pass = q["expected_check"](top_match)
        passed = value_pass
        results.append({
            "query": q["query"],
            "top_match": top_match,
            "all_results": r,
            "passed": passed,
        })
        status = "✅" if passed else "❌"
        print(f"  {status} top-1: {top_match['path']} ({top_match['category']}, hybrid {top_match['hybrid_score']})")
        print(f"       BM25: {top_match['bm25_score']}, EMB: {top_match['emb_score']}")
        for j, item in enumerate(r[1:3]):
            print(f"    top-{j+2}: {item['path']} (hybrid {item['hybrid_score']})")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P3.3 BM25 hybrid 升级: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)
    if passed_count == 3:
        print("🎉 Test 3 (红色跑车) 修复!hybrid 方案胜出纯 embedding")
        print("💡 永久 invariant #73: BM25 + embedding hybrid 召回实战 3/3 PASS")

    # 写报告
    report_path = BASE / "cogvlm2_hybrid_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P3.3 BM25 + embedding hybrid 升级",
        "weights": {"bm25": 0.4, "embedding": 0.6},
        "library_size": len(IMAGE_LIBRARY),
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
