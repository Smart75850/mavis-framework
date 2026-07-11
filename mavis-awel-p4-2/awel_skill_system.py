#!/usr/bin/env python3
"""
P4.2 DB-GPT AWEL Skill 体系实战 (永久 invariant #72)

借鉴: 高强文书第 6 章 DB-GPT AWEL 3 层架构
- 算子层 (LLM 原子操作)
- DSL 层 (标准化结构化语言)
- AgentFrame (算子链式封装)

mavis 对应: sub-skill (算子) + skill 调用语法 (DSL) + skill 组合 (AgentFrame)

P4.2 实战设计:
- 3 层 AWEL 真实实现
- 3 真 query 验证 3 层协同工作

3 真 query:
- Q1: 算子层 - 翻译算子 (英文 → 中文)
- Q2: DSL 层 - 2 个算子组合 (翻译 + 总结)
- Q3: AgentFrame 层 - 完整 pipeline (翻译 → 总结 → 分类)
"""
import sys
import os
import json
import time
import re
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v7"))
from mavis_m3_provider import call_llm_m3


# ============== AWEL 3 层架构 (永久 invariant #15 + #72) ==============

# 算子层: LLM 原子操作 (单功能)
def operator_translate(text: str, target_lang: str = "中文") -> str:
    """算子: 翻译"""
    system = f"你是一个翻译助手, 将文本翻译成{target_lang}, 保持原意。"
    return call_llm_m3(system=system, user=text, max_tokens=200, temperature=0.2, use_fallback=True)


def operator_summarize(text: str, max_length: int = 50) -> str:
    """算子: 总结"""
    system = f"你是一个总结助手, 将文本总结为不超过 {max_length} 字嘅精炼版本。"
    return call_llm_m3(system=system, user=text, max_tokens=200, temperature=0.2, use_fallback=True)


def operator_classify(text: str, categories: list) -> str:
    """算子: 分类"""
    system = (
        f"你是一个文本分类助手, 将文本分类到以下类别之一: {', '.join(categories)}。\n"
        "**只返类别名**, 唔好返其他内容。"
    )
    return call_llm_m3(system=system, user=text, max_tokens=50, temperature=0.1, use_fallback=True)


# DSL 层: 算子链式组合语法 (借鉴 AWEL DSL)
DSL_GRAMMAR = """
# AWEL DSL 语法 (简化版, 永久 invariant #72)
# 格式: operator_name(input=expr, **kwargs) -> output

translate(text="Hello World", target="中文") -> translated
summarize(text=translated, max_length=30) -> summary
classify(text=summary, categories=["技术", "生活", "其他"]) -> category

# 链式组合: result = translate > summarize > classify
"""


def dsl_chain(operators: list, input_data: str) -> dict:
    """DSL 层: 算子链式调用"""
    result = {"input": input_data, "stages": []}
    current = input_data

    for op_def in operators:
        op_name = op_def["operator"]
        kwargs = op_def.get("kwargs", {})
        if op_name == "translate":
            output = operator_translate(current, **kwargs)
        elif op_name == "summarize":
            output = operator_summarize(current, **kwargs)
        elif op_name == "classify":
            output = operator_classify(current, **kwargs)
        else:
            output = f"[未知算子: {op_name}]"
        result["stages"].append({"operator": op_name, "input": current[:80], "output": output})
        current = output

    result["final"] = current
    return result


# AgentFrame 层: 复杂 workflow 封装
class AWELFrame:
    """AgentFrame: 算子链式计算封装, 借鉴 AWEL 嘅 operator chain"""

    def __init__(self, name: str, pipeline: list):
        self.name = name
        self.pipeline = pipeline  # list of operator configs

    def execute(self, input_data: str) -> dict:
        """执行 AgentFrame pipeline"""
        print(f"\n[AgentFrame: {self.name}] 执行 pipeline ({len(self.pipeline)} 步)")
        result = dsl_chain(self.pipeline, input_data)
        return result


# ============== 实战: 3 真 query 验证 3 层协同 ==============

def main():
    print("=" * 70)
    print("P4.2 DB-GPT AWEL Skill 体系实战 (永久 invariant #72)")
    print("=" * 70)
    print()
    print("借鉴: 高强文书第 6 章 AWEL 3 层架构")
    print("  算子层 (LLM 原子) + DSL 层 (标准化结构化语言) + AgentFrame (算子链式封装)")
    print()

    # === Stage 1: AWEL 3 层架构展示 ===
    print("=" * 70)
    print("Stage 1: AWEL 3 层架构展示 (永久 invariant #72)")
    print("=" * 70)
    print()
    print("【算子层】 3 个 LLM 原子算子:")
    print("  - operator_translate(text, target_lang)")
    print("  - operator_summarize(text, max_length)")
    print("  - operator_classify(text, categories)")
    print()
    print("【DSL 层】 算子链式语法 (简化 AWEL DSL):")
    print(DSL_GRAMMAR)
    print()
    print("【AgentFrame 层】 算子链式计算封装, 实战 pipeline")

    # === Stage 2: 3 真 query 验证 3 层协同 ===
    print("=" * 70)
    print("Stage 2: 3 真 query 验证 3 层协同")
    print("=" * 70)

    queries = [
        {
            "name": "Q1 算子层 - 翻译",
            "query": "LoRA is a parameter-efficient fine-tuning technique that uses low-rank matrices.",
            "operator_only": True,
            "expected_check": lambda r: "LoRA" in r.get("final", "") and any(kw in r.get("final", "") for kw in ["参数", "微调", "低秩", "高效"]),
        },
        {
            "name": "Q2 DSL 层 - 翻译 + 总结",
            "query": "MemGPT introduces a hierarchical memory system with core memory and archival storage, enabling unlimited context through paging.",
            "pipeline": [
                {"operator": "translate", "kwargs": {"target_lang": "中文"}},
                {"operator": "summarize", "kwargs": {"max_length": 50}},
            ],
            "expected_check": lambda r: "MemGPT" in r.get("final", "") and ("记忆" in r.get("final", "") or "存储" in r.get("final", "") or "上下文" in r.get("final", "")),
        },
        {
            "name": "Q3 AgentFrame 层 - 完整 pipeline",
            "query": "DB-GPT's AWEL (Agentic Workflow Expression Language) enables 3-layer architecture for AI agent orchestration.",
            "pipeline": [
                {"operator": "translate", "kwargs": {"target_lang": "中文"}},
                {"operator": "summarize", "kwargs": {"max_length": 30}},
                {"operator": "classify", "kwargs": {"categories": ["技术", "生活", "其他"]}},
            ],
            "expected_check": lambda r: r.get("final", "") in ["技术", "生活", "其他"],
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['name']}")
        print(f"  input: {q['query'][:100]}")

        if q.get("operator_only"):
            # 算子层单步
            r = {"input": q["query"], "stages": [{"operator": "translate", "input": q["query"], "output": operator_translate(q["query"])}], "final": operator_translate(q["query"])}
        else:
            # AgentFrame pipeline
            frame = AWELFrame(q["name"], q["pipeline"])
            r = frame.execute(q["query"])

        value_pass = q["expected_check"](r)
        passed = value_pass
        r["passed"] = passed
        r["name"] = q["name"]

        results.append(r)
        status = "✅" if passed else "❌"
        print(f"  {status} final: {r.get('final', '')[:200]}")
        if not passed:
            print(f"  ❌ 验证失败: 期望含 expected 关键词")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P4.2 AWEL Skill 体系实战: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = BASE / "awel_p4_2_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P4.2 DB-GPT AWEL Skill 体系实战",
        "layers": {
            "L1_operator": ["translate", "summarize", "classify"],
            "L2_dsl": "AWEL DSL 简化版 (operator > operator)",
            "L3_agent_frame": "AWELFrame class (pipeline execute)",
        },
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
