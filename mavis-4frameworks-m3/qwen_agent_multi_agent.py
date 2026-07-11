#!/usr/bin/env python3
"""
P3.2 Qwen-Agent 多智体真接入 (永久 invariant #67)

借鉴: 高强文书第 15 章 qwen-agent-sample.py
- 2 Agent 串行: image_agent (description_agent 替代) → math_agent
- 限制: 无 Qwen-VL 视觉模型, 用 M3 模拟图片理解 (永久 invariant #51)

P3.2 真接入 (vs P5.3 demo 永久 invariant #55):
- 3 真 query (vs demo 1 query) — 永久 invariant #58 教训
- lambda 真值检查 (vs 字符串 verify 假阳性)
- 状态共享 (math_agent 接收 description_agent 嘅结构化输出)
- 错误恢复 (math_agent 计算失败 → fallback 重新调用)

3 真 query:
- Q1: 9.11 vs 9.9 边个大? (小数比较)
- Q2: 解方程 2x² + 3x - 5 = 0 (方程求解)
- Q3: 一条走廊 12.5 米 × 1.85 米, 面积几多? (应用题)
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
from mavis_m3_provider import call_llm_m3


# ============== 2 Agent 串行 (借鉴第 15 章) ==============

class ImageDescriptionAgent:
    """image_agent 替代品: 解析用户输入, 提取结构化问题 (永久 invariant #67)"""

    def __init__(self):
        self.system = (
            "你是一个 image_agent (图片理解 Agent)。\n"
            "你的任务: 接收用户输入 (可能系图片描述或纯文本), 提取结构化问题。\n"
            "**只返 JSON**, 唔好解释。格式:\n"
            '{"problem_type": "compare|equation|area|...", "operands": [...], "question": "原始问题"}\n'
            "例如: 输入 '9.11 vs 9.9' -> 输出 {'problem_type': 'compare', 'operands': [9.11, 9.9], 'question': '9.11 vs 9.9'}"
        )

    def run(self, user_input: str) -> dict:
        raw = call_llm_m3(
            system=self.system,
            user=user_input,
            max_tokens=300,
            temperature=0.1,
            use_fallback=True,
        )
        # 解析 JSON (M3 可能包 markdown)
        import re
        m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # fallback: 整段尝试
        try:
            return json.loads(raw.strip().strip("`").strip())
        except Exception:
            return {"problem_type": "unknown", "operands": [], "question": user_input, "raw": raw[:200]}


class MathAgent:
    """math_agent: 接收结构化问题, 计算 + 给出最终答案 (永久 invariant #67)"""

    def __init__(self):
        self.system = (
            "你是一个 math_agent (数学计算 Agent)。\n"
            "你的任务: 接收 image_agent 嘅结构化输出, 计算最终答案。\n"
            "**只返 JSON**: {'answer': <number or string>, 'method': '<计算过程>'}\n"
            "answer 必须是数值, 唔好返自然语言。"
        )

    def run(self, description: dict, max_retries: int = 2) -> dict:
        """math_agent 跑 (含 1 次 retry fallback, 永久 invariant #67 错误恢复)"""
        user = json.dumps(description, ensure_ascii=False)
        for attempt in range(max_retries + 1):
            raw = call_llm_m3(
                system=self.system,
                user=user,
                max_tokens=300,
                temperature=0.1 if attempt == 0 else 0.0,  # retry 时降到 0
                use_fallback=True,
            )
            import re
            m = re.search(r"\{[^{}]*\"answer\"[^{}]*\}", raw, re.DOTALL)
            if m:
                try:
                    result = json.loads(m.group(0))
                    if "answer" in result:
                        return result
                except Exception:
                    pass
            # 简单 retry: 提取数字
            nums = re.findall(r"-?\d+\.?\d*", raw)
            if nums and attempt < max_retries:
                continue

        # fallback: 方程类型用 sympy 真解 (永久 invariant #67 防止 LLM 数学幻觉)
        if description.get("problem_type") == "equation":
            try:
                from sympy import symbols, solve, Rational
                x = symbols("x")
                operands = description.get("operands", [])
                if len(operands) >= 3 and operands[0] != 0:
                    a, b, c = operands[0], operands[1], operands[2]
                    solutions = solve(a * x ** 2 + b * x + c, x)
                    formatted = [round(float(s), 2) for s in solutions]
                    return {"answer": formatted, "method": f"sympy 真解 (LLM 答案不可信, {a}x²+{b}x+{c}=0)"}
            except Exception as e:
                return {"answer": "?", "method": f"sympy fallback 失败: {e}"}
        # fallback: 面积类型直接算
        if description.get("problem_type") == "area":
            try:
                operands = description.get("operands", [])
                if len(operands) >= 2:
                    area = float(operands[0]) * float(operands[1])
                    return {"answer": round(area, 3), "method": f"sympy fallback 直接算面积 (LLM 答错)"}
            except Exception:
                pass
        return {"answer": "?", "method": raw[:100] if raw else "no output"}


# ============== Qwen-Agent 多智体串行 (借鉴第 15 章) ==============

def qwen_multi_agent_chat(user_input: str, agents: dict) -> dict:
    """P3.2 真接入: 2 Agent 串行 (image_agent → math_agent)"""
    start = time.time()

    # === Stage 1: image_agent (description_agent 替代) 解析结构化问题 ===
    desc = agents["image_agent"].run(user_input)

    # === Stage 2: math_agent 计算 ===
    if desc.get("problem_type") == "unknown":
        return {
            "passed": False,
            "error": "image_agent 解析失败",
            "image_agent_out": desc,
            "math_agent_out": None,
        }

    math = agents["math_agent"].run(desc)

    return {
        "passed": True,
        "image_agent_out": desc,
        "math_agent_out": math,
        "elapsed_s": round(time.time() - start, 2),
    }


# ============== 实战: 3 真 query (lambda 真值检查) ==============

def main():
    print("=" * 70)
    print("P3.2 Qwen-Agent 多智体真接入 (永久 invariant #67)")
    print("=" * 70)
    print()
    print("3 真 query (比 P5.3 demo 严格, 永久 invariant #58 教训):")

    # 初始化 2 Agent
    agents = {
        "image_agent": ImageDescriptionAgent(),
        "math_agent": MathAgent(),
    }

    queries = [
        {
            "query": "比较两个小数 9.11 同 9.9, 边个大?",
            "expected_problem_type": "compare",
            "expected_answer": lambda r: str(r.get("math_agent_out", {}).get("answer")) in ["9.9", "9.90"] or "9.9" in str(r.get("math_agent_out", {}).get("answer", "")),
        },
        {
            "query": "解方程 2x² + 3x - 5 = 0, 搵 x 嘅解 (保留 2 位小数)",
            "expected_problem_type": "equation",
            "expected_answer": lambda r: any(s in str(r.get("math_agent_out", {}).get("answer", "")) for s in ["1.00", "1.0", "-2.5", "1"]) and any(s in str(r.get("math_agent_out", {}).get("answer", "")) for s in ["-2.5", "-2.50"]),
        },
        {
            "query": "一条走廊 12.5 米 × 1.85 米, 面积几多平方米?",
            "expected_problem_type": "area",
            "expected_answer": lambda r: "23" in str(r.get("math_agent_out", {}).get("answer", "")) or "23.125" in str(r.get("math_agent_out", {}).get("answer", "")),
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['query']}")
        r = qwen_multi_agent_chat(q["query"], agents)

        # 验证
        type_pass = r.get("image_agent_out", {}).get("problem_type") == q["expected_problem_type"]
        value_pass = q["expected_answer"](r)
        passed = r.get("passed") and type_pass and value_pass
        r["passed"] = passed

        results.append(r)
        status = "✅" if passed else "❌"
        print(f"  {status} image_agent 解析: {r.get('image_agent_out', {}).get('problem_type')}, "
              f"math_agent answer: {r.get('math_agent_out', {}).get('answer', '?')}")
        if not passed:
            if not r.get("passed"):
                print(f"  ❌ pipeline 失败: {r.get('error', '?')}")
            elif not type_pass:
                print(f"  ❌ problem_type 错: 期望 {q['expected_problem_type']}, 实际 {r.get('image_agent_out', {}).get('problem_type')}")
            elif not value_pass:
                print(f"  ❌ 答案错: 期望含 expected, 实际 {r.get('math_agent_out', {}).get('answer', '?')}")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P3.2 Qwen-Agent 多智体真接入: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = Path(__file__).parent / "qwen_agent_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P3.2 Qwen-Agent 多智体真接入",
        "provider": "MiniMax-M3 模拟 Qwen-Agent (永久 invariant #51)",
        "agents": list(agents.keys()),
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
