#!/usr/bin/env python3
"""
P4.1 MemGPT 5 层记忆实战 (永久 invariant #71)

借鉴: 高强文书第 4 章 MemGPT 虚拟上下文 = mavis 5 层记忆
- MemGPT 3 层: system + core_memory + recall_storage
- mavis 5 层: 短期 + 长期 + 任务 + 反思 + 项目

P4.1 实战设计:
- 5 层记忆的真实数据结构
- 5 层联动 (add / query / summarize)
- 3 真 query 验证 5 层协同工作

3 真 query:
- Q1: "我哋之前讨论过 mavis 嘅边啲永久 invariant?" (触发短期 + 长期)
- Q2: "当前任务进度?" (触发任务 + 短期)
- Q3: "上次 verifier 嘅反思结论?" (触发反思 + 短期)
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
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v7"))
from mavis_m3_provider import call_llm_m3


# ============== MemGPT 3 层 → mavis 5 层 映射 (永久 invariant #13 + #71) ==============

MEMORY_LAYERS = {
    "L1_short_term": {
        "name": "短期记忆 (session context)",
        "memgpt_layer": "system (in-context)",
        "structure": "list[dict] - 滑动窗口,最近 N 条对话",
        "max_items": 20,
        "examples": [],
    },
    "L2_long_term": {
        "name": "长期记忆 (向量 DB)",
        "memgpt_layer": "recall_storage (vector store)",
        "structure": "dict[id, content] - 向量索引,语义检索",
        "max_items": 10000,
        "examples": [],
    },
    "L3_task": {
        "name": "任务记忆 (current task)",
        "memgpt_layer": "core_memory (working memory)",
        "structure": "dict - 当前 task list + status",
        "max_items": 50,
        "examples": [],
    },
    "L4_reflection": {
        "name": "反思记忆 (verifier output)",
        "memgpt_layer": "core_memory (reflection)",
        "structure": "list[dict] - verifier 嘅反思 + 改进建议",
        "max_items": 100,
        "examples": [],
    },
    "L5_project": {
        "name": "项目记忆 (AGENTS.md + topic files)",
        "memgpt_layer": "core_memory (archival)",
        "structure": "str - 项目级永久 invariant + SOP",
        "max_items": 1000,
        "examples": [],
    },
}


# ============== 5 层记忆管理器 (永久 invariant #71) ==============

class Memory5Layer:
    """mavis 5 层记忆管理器, 借鉴 MemGPT 虚拟上下文技巧"""

    def __init__(self):
        self.layers = {k: [] for k in MEMORY_LAYERS.keys()}
        # 预填项目记忆
        self.layers["L5_project"].append({
            "id": "proj-mavis-001",
            "content": "mavis framework = 9 大框架真接入 + 永久 invariant 库 #9-#71 + 5 层记忆体系",
            "source": "AGENTS.md",
        })
        self.layers["L5_project"].append({
            "id": "proj-mavis-002",
            "content": "永久 invariant #51: 本地 14B/32B 已被废,只保留 274MB nomic-embed,主 LLM 用 M3 云端",
            "source": "MEMORY.md",
        })

    def add(self, layer: str, content: dict):
        """添加记忆到指定层"""
        if layer not in self.layers:
            raise ValueError(f"未知记忆层: {layer}")
        self.layers[layer].append(content)
        # 滑动窗口 (L1 短期)
        if layer == "L1_short_term" and len(self.layers[layer]) > MEMORY_LAYERS[layer]["max_items"]:
            self.layers[layer] = self.layers[layer][-MEMORY_LAYERS[layer]["max_items"]:]

    def query(self, user_query: str, layers_to_search: list = None) -> dict:
        """跨层查询, M3 模拟语义检索 + 总结"""
        if layers_to_search is None:
            layers_to_search = list(self.layers.keys())

        # Step 1: 收集每层 hit
        all_items = []
        for layer in layers_to_search:
            for item in self.layers[layer]:
                all_items.append({"layer": layer, "content": item})

        # Step 2: M3 模拟语义匹配 + 总结
        if not all_items:
            return {"summary": "无相关记忆", "hits": []}

        items_text = "\n".join([
            f"[{item['layer']}] {item['content'].get('content', item['content'])}"
            for item in all_items
        ])
        system = (
            "你是一个 mavis 5 层记忆检索助手。\n"
            "用户查询 + 5 层记忆内容, 总结出最相关嘅记忆, 标注来自边一层。\n"
            "**只返 JSON**: {'summary': '<中文总结>', 'hits': [{'layer': 'L1_short_term', 'content': '<...>'}, ...]}\n"
            "hits 最少 1 条, 最多 3 条。"
        )
        raw = call_llm_m3(
            system=system,
            user=f"用户查询: {user_query}\n\n5 层记忆:\n{items_text[:2000]}",
            max_tokens=400,
            temperature=0.2,
            use_fallback=True,
        )
        # 解析 JSON
        import re
        m = re.search(r"\{[\s\S]*\"summary\"[\s\S]*\}", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"summary": raw[:200], "hits": []}

    def get_all_summary(self) -> dict:
        """5 层记忆统计 + 容量"""
        return {
            layer: {
                "name": MEMORY_LAYERS[layer]["name"],
                "count": len(self.layers[layer]),
                "max_items": MEMORY_LAYERS[layer]["max_items"],
            }
            for layer in self.layers
        }


# ============== 实战: 5 层记忆填充 + 3 真 query 跨层检索 ==============

def main():
    print("=" * 70)
    print("P4.1 MemGPT 5 层记忆实战 (永久 invariant #71)")
    print("=" * 70)
    print()
    print("借鉴: 高强文书第 4 章 MemGPT 虚拟上下文 = mavis 5 层记忆")
    print()

    # === Stage 1: 初始化 5 层 + 填充模拟数据 ===
    print("=" * 70)
    print("Stage 1: 5 层记忆初始化 + 模拟数据填充")
    print("=" * 70)
    memory = Memory5Layer()

    # L1 短期 - 最近对话
    memory.add("L1_short_term", {
        "role": "user", "content": "我哋之前讨论过 mavis 嘅边啲永久 invariant?",
        "ts": "2026-07-12T01:00:00",
    })
    memory.add("L1_short_term", {
        "role": "assistant", "content": "我哋已经实战咗 #9-#71, 包括 9 框架真接入 + LoRA 微调 + MemGPT 5 层",
        "ts": "2026-07-12T01:00:30",
    })

    # L2 长期 - 向量索引 (模拟, 实际用 nomic-embed)
    memory.add("L2_long_term", {
        "id": "vec-001", "content": "永久 invariant #65: GLM-4 Function-calling 真接入 3/3 PASS 9.3s",
        "embedding_dim": 768,
    })
    memory.add("L2_long_term", {
        "id": "vec-002", "content": "永久 invariant #66: LangChain Plan-and-Execute 真接入 3/3 PASS 14.9s",
        "embedding_dim": 768,
    })
    memory.add("L2_long_term", {
        "id": "vec-003", "content": "永久 invariant #70: LoRA 微调实战 M3 模拟 + 训练流程演示",
        "embedding_dim": 768,
    })

    # L3 任务 - 当前 task list
    memory.add("L3_task", {
        "task_id": "T-P5.0", "name": "9 框架 regression test",
        "status": "completed", "progress": "5/5 PASS",
    })
    memory.add("L3_task", {
        "task_id": "T-P4.0", "name": "LoRA 微调实战",
        "status": "completed", "progress": "1/3 PASS (M3 模拟训练流程)",
    })
    memory.add("L3_task", {
        "task_id": "T-P4.1", "name": "MemGPT 5 层记忆实战",
        "status": "in_progress", "progress": "进行中",
    })

    # L4 反思 - verifier 输出
    memory.add("L4_reflection", {
        "verifier_id": "V-P3.0", "conclusion": "GLM-4 FC 真接入实战 0 caveat, 3 工具 + 3 真 query 100% PASS",
        "ts": "2026-07-11",
    })
    memory.add("L4_reflection", {
        "verifier_id": "V-P3.3", "conclusion": "CogVLM2 召回 2/3 PASS, nomic-embed 召回偏向真实限制, 建议升级 BM25 hybrid",
        "ts": "2026-07-12",
    })

    summary = memory.get_all_summary()
    for layer, info in summary.items():
        print(f"  {layer} ({info['name']}): {info['count']}/{info['max_items']} 条")

    # === Stage 2: 3 真 query 跨层检索 ===
    print()
    print("=" * 70)
    print("Stage 2: 3 真 query 跨层检索 (永久 invariant #71)")
    print("=" * 70)

    queries = [
        {
            "query": "我哋之前讨论过 mavis 嘅边啲永久 invariant?",
            "expected_layers": ["L1_short_term", "L2_long_term", "L5_project"],
            "expected_check": lambda r: "永久 invariant" in r.get("summary", "") and len(r.get("hits", [])) >= 1,
        },
        {
            "query": "当前任务进度?",
            "expected_layers": ["L3_task", "L1_short_term"],
            "expected_check": lambda r: any(t in r.get("summary", "") for t in ["T-P5.0", "T-P4.0", "T-P4.1", "5/5 PASS", "1/3 PASS"]),
        },
        {
            "query": "上次 verifier 嘅反思结论?",
            "expected_layers": ["L4_reflection", "L1_short_term"],
            "expected_check": lambda r: any(v in r.get("summary", "") for v in ["V-P3.0", "V-P3.3", "verifier", "召回"]),
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['query']}")
        r = memory.query(q["query"], q["expected_layers"])

        value_pass = q["expected_check"](r)
        passed = value_pass and len(r.get("hits", [])) >= 1
        r["passed"] = passed
        r["expected_layers"] = q["expected_layers"]

        results.append(r)
        status = "✅" if passed else "❌"
        print(f"  {status} summary: {r.get('summary', '')[:150]}")
        print(f"  命中层: {[h.get('layer') for h in r.get('hits', [])]}")
        if not passed:
            if not value_pass:
                print(f"  ❌ 总结错: 期望含 expected 关键词")
            else:
                print(f"  ❌ 0 命中层")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P4.1 MemGPT 5 层记忆实战: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = BASE / "memgpt_p4_1_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P4.1 MemGPT 5 层记忆实战",
        "memgpt_to_mavis_mapping": "3 层 (system + core_memory + recall_storage) → 5 层 (短期 + 长期 + 任务 + 反思 + 项目)",
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
