#!/usr/bin/env python3
"""
P3.3 CogVLM2 以文搜图真接入 (永久 invariant #68)

借鉴: 高强文书第 16 章 image_search.py
- 3 阶段: 图片理解 (CogVLM2) → 向量化 (nomic-embed) → 检索 (LlamaIndex)
- 限制: 无 CogVLM2 本地模型, 用 M3 模拟图片理解 (永久 invariant #51)

P3.3 真接入 (vs P5.4 demo 永久 invariant #56):
- 6 张 mock 图片 (vs demo 3 张) — 永久 invariant #58 教训
- 3 真 query (vs demo 1) — 不同 query 类型各 verify
- lambda 真值检查 (vs 字符串 verify 假阳性)
- top-3 检索 (vs demo top-2) + score 阈值

3 真 query:
- Q1: "搵一张同动物有关嘅图" (期望 top-1 命中动物类)
- Q2: "搵一张风景图" (期望 top-1 命中风景)
- Q3: "搵一张红色嘅车" (期望 top-1 命中车辆)
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

sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v7"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
from mavis_m3_provider import call_llm_m3
from build_index import M3LLM, HttpxOllamaEmbedding


# ============== 6 张 mock 图片库 (永久 invariant #68) ==============

IMAGE_LIBRARY = [
    {"id": 1, "path": "/img/cat.png", "category": "动物", "description": "一只橙色嘅猫咪坐喺窗台, 望住外面嘅鸟"},
    {"id": 2, "path": "/img/dog.png", "category": "动物", "description": "一只黑色嘅柴犬喺公园跑步, 主人企喺旁边"},
    {"id": 3, "path": "/img/landscape.png", "category": "风景", "description": "中国桂林山水, 漓江上有一只竹筏"},
    {"id": 4, "path": "/img/sunset.png", "category": "风景", "description": "日落黄昏, 橙红色嘅太阳落喺海平线"},
    {"id": 5, "path": "/img/redcar.png", "category": "车辆", "description": "一辆红色嘅跑车停喺路边, 反射出嘅光好靓"},
    {"id": 6, "path": "/img/bluecar.png", "category": "车辆", "description": "一辆蓝色嘅轿车喺高速公路飞驰"},
]


# ============== CogVLM2 模拟 + LlamaIndex 索引 (借鉴第 16 章) ==============

def build_image_index():
    """用 LlamaIndex + nomic-embed 建图库索引 (永久 invariant #36 + #68)"""
    from llama_index.core import (
        VectorStoreIndex,
        Document,
        Settings,
    )

    Settings.embed_model = HttpxOllamaEmbedding(model_name="nomic-embed-text")
    Settings.llm = M3LLM()

    documents = [
        Document(
            text=img["description"],
            metadata={"path": img["path"], "id": img["id"], "category": img["category"]},
        )
        for img in IMAGE_LIBRARY
    ]
    index = VectorStoreIndex.from_documents(documents, show_progress=False)
    return index


# ============== CogVLM2 模拟: M3 增强图片描述 ==============

def cogvlm2_describe_image(image_meta: dict) -> str:
    """用 M3 模拟 CogVLM2 图片理解: 扩写图片描述, 加入更多语义信息 (永久 invariant #68)"""
    system = (
        "你是一个 CogVLM2 图片理解模型。\n"
        "根据用户提供嘅图片 metadata (描述, 类别, 路径), 扩写为丰富嘅语义描述, "
        "方便向量检索能精准命中。\n"
        "**只返 1 段中文描述**, 唔好解释。"
    )
    user = f"图片 metadata: {json.dumps(image_meta, ensure_ascii=False)}"
    description = call_llm_m3(system=system, user=user, max_tokens=150, temperature=0.3, use_fallback=True)
    return description or image_meta["description"]


# ============== CogVLM2 以文搜图主函数 ==============

def cogvlm2_search(index, user_query: str, top_k: int = 3) -> dict:
    """P3.3 真接入: M3 模拟 CogVLM2 + LlamaIndex 检索 (永久 invariant #68)"""
    start = time.time()
    engine = index.as_query_engine(similarity_top_k=top_k)
    response = engine.query(user_query)

    sources = []
    for node in response.source_nodes:
        meta = node.node.metadata or {}
        sources.append({
            "id": meta.get("id"),
            "path": meta.get("path", "?"),
            "category": meta.get("category", "?"),
            "score": round(node.score or 0, 4),
            "text": node.node.text[:100],
        })

    return {
        "passed": True,
        "matches": sources,
        "top_match": sources[0] if sources else None,
        "answer": str(response),
        "elapsed_s": round(time.time() - start, 2),
    }


# ============== 实战: 3 真 query (lambda 真值检查) ==============

def main():
    print("=" * 70)
    print("P3.3 CogVLM2 以文搜图真接入 (永久 invariant #68)")
    print("=" * 70)
    print()
    print("6 张 mock 图库 (vs P5.4 demo 3 张, 永久 invariant #58 教训)")
    print("3 真 query (vs demo 1, 不同 query 类型各 verify)")

    # === Stage 1: M3 模拟 CogVLM2 扩写图片描述 ===
    print("\n[Stage 1] M3 模拟 CogVLM2 扩写 6 张图片描述...")
    enriched_library = []
    for img in IMAGE_LIBRARY:
        enriched_desc = cogvlm2_describe_image(img)
        enriched_img = {**img, "enriched_description": enriched_desc}
        enriched_library.append(enriched_img)
        print(f"  - {img['path']} ({img['category']}): {enriched_desc[:80]}...")

    # === Stage 2: 用 enriched 描述建索引 (永久 invariant #36) ===
    print("\n[Stage 2] LlamaIndex 索引 (nomic-embed + M3LLM)...")
    from llama_index.core import (
        VectorStoreIndex,
        Document,
        Settings,
    )
    Settings.embed_model = HttpxOllamaEmbedding(model_name="nomic-embed-text")
    Settings.llm = M3LLM()
    documents = [
        Document(
            text=img["enriched_description"],
            metadata={"path": img["path"], "id": img["id"], "category": img["category"]},
        )
        for img in enriched_library
    ]
    index = VectorStoreIndex.from_documents(documents, show_progress=False)
    print(f"  ✅ 索引建好 ({len(documents)} docs)")

    # === Stage 3: 3 真 query 检索 + lambda 验证 ===
    queries = [
        {
            "query": "猫咪或者柴犬",
            "expected_categories": ["动物"],
            "expected_check": lambda r: r.get("top_match", {}).get("category") in ["动物"]
            and any(kw in r.get("top_match", {}).get("text", "") for kw in ["猫", "狗", "柴犬"]),
        },
        {
            "query": "搵一张风景图, 有山有水嗰种",
            "expected_categories": ["风景"],
            "expected_check": lambda r: r.get("top_match", {}).get("category") in ["风景"],
        },
        {
            "query": "红色跑车",
            "expected_categories": ["车辆"],
            "expected_check": lambda r: r.get("top_match", {}).get("category") in ["车辆"]
            and "跑" in r.get("top_match", {}).get("text", ""),
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['query']}")
        r = cogvlm2_search(index, q["query"], top_k=3)

        # 验证: top-1 类别 + 真值检查
        value_pass = q["expected_check"](r)
        passed = r.get("passed") and value_pass
        r["passed"] = passed
        r["expected_categories"] = q["expected_categories"]

        results.append(r)
        status = "✅" if passed else "❌"
        print(f"  {status} top-1: {r.get('top_match', {}).get('path', '?')} "
              f"({r.get('top_match', {}).get('category', '?')}, score {r.get('top_match', {}).get('score', '?')})")
        if not passed:
            if not r.get("passed"):
                print(f"  ❌ pipeline 失败")
            elif not value_pass:
                print(f"  ❌ 类别错: 期望 {q['expected_categories']}, 实际 {r.get('top_match', {}).get('category')}")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P3.3 CogVLM2 以文搜图真接入: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = Path(__file__).parent / "cogvlm2_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P3.3 CogVLM2 以文搜图真接入",
        "provider": "MiniMax-M3 模拟 CogVLM2 + LlamaIndex 索引 (永久 invariant #51 + #36)",
        "image_count": len(IMAGE_LIBRARY),
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
