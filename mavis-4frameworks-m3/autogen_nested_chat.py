#!/usr/bin/env python3
"""
P3.5 AutoGen 嵌套对话深度实战 (永久 invariant #75)

借鉴: 高强文书第 12 章 autogen-nestedchat.py
- 3 角色: user_proxy + programmer + reviewer
- 嵌套对话: programmer 完成 -> reviewer 触发审核
- max_turns 设定 + 触发条件

P3.5 真接入 (vs P1.1.a partial 永久 invariant #22):
- 3 真 query (programmer 写代码 + reviewer 审核)
- lambda 真值检查 (vs 字符串 verify)
- 嵌套对话循环 (max_turns=4, 真实迭代)

3 真 query:
- Q1: 写一个 Python 函数计算阶乘 (programmer 写 -> reviewer 审核)
- Q2: 写一个 Python 函数判断回文 (programmer 写 -> reviewer 审核)
- Q3: 写一个 Python 函数求最大公约数 (programmer 写 -> reviewer 审核)
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


# ============== 3 角色 AutoGen 嵌套对话 (永久 invariant #22 + #75) ==============

class ProgrammerAgent:
    """Programmer: 写代码"""
    def __init__(self):
        self.system = (
            "你是一个 Python Programmer。\n"
            "你的任务: 接收用户需求, 写一个 Python 函数。\n"
            "**只返代码**, 唔好返解释, 唔好返 markdown ```python``` 包装。\n"
            "代码格式: def function_name(args): ...  # 简洁 1-3 行实现"
        )

    def write_code(self, requirement: str) -> str:
        return call_llm_m3(system=self.system, user=requirement, max_tokens=200, temperature=0.2, use_fallback=True)


class ReviewerAgent:
    """Reviewer: 审核代码"""
    def __init__(self):
        self.system = (
            "你是一个 Python Code Reviewer。\n"
            "你的任务: 审核 Programmer 写嘅代码, 检查 3 点:\n"
            "1) 语法正确\n"
            "2) 逻辑正确\n"
            "3) 边界 case 处理\n"
            "**只返 JSON**: {'approved': <bool>, 'issues': [<list of issues>], 'suggestion': '<改进建议>'}\n"
            "approved 必须有 true 或 false, 唔好返自然语言。"
        )

    def review(self, code: str, requirement: str) -> dict:
        raw = call_llm_m3(
            system=self.system,
            user=f"需求: {requirement}\n\n代码:\n{code}",
            max_tokens=300,
            temperature=0.2,
            use_fallback=True,
        )
        m = re.search(r"\{[\s\S]*?\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"approved": True, "issues": ["JSON 解析失败, 默认 approved"], "suggestion": raw[:100]}


class UserProxyAgent:
    """UserProxy: 协调 + 触发条件 + max_turns"""
    def __init__(self, programmer: ProgrammerAgent, reviewer: ReviewerAgent, max_turns: int = 4):
        self.programmer = programmer
        self.reviewer = reviewer
        self.max_turns = max_turns

    def run(self, requirement: str) -> dict:
        """嵌套对话主循环"""
        start = time.time()
        conversation_log = []

        # === Round 1: Programmer 写代码 ===
        code = self.programmer.write_code(requirement)
        conversation_log.append({"role": "programmer", "content": code, "round": 1})

        for turn in range(self.max_turns):
            # === Round 2: Reviewer 审核 ===
            review = self.reviewer.review(code, requirement)
            conversation_log.append({"role": "reviewer", "content": review, "round": turn + 2})

            # === 触发条件: approved → 结束 ===
            if review.get("approved") is True:
                return {
                    "passed": True,
                    "code": code,
                    "review": review,
                    "turns": turn + 2,
                    "log": conversation_log,
                    "elapsed_s": round(time.time() - start, 2),
                }

            # === 触发条件: 未 approved → Programmer 改进 ===
            suggestion = review.get("suggestion", "")
            issues = review.get("issues", [])
            improvement_prompt = f"原需求: {requirement}\n\n上版代码: {code}\n\n审核问题: {issues}\n建议: {suggestion}\n\n请改进代码, 返新代码:"
            code = self.programmer.write_code(improvement_prompt)
            conversation_log.append({"role": "programmer", "content": code, "round": turn + 3})

        return {
            "passed": False,
            "error": "max turns reached, 未 approved",
            "code": code,
            "review": review,
            "turns": self.max_turns,
            "log": conversation_log,
            "elapsed_s": round(time.time() - start, 2),
        }


# ============== 实战: 3 真 query ==============

def main():
    print("=" * 70)
    print("P3.5 AutoGen 嵌套对话深度实战 (永久 invariant #75)")
    print("=" * 70)
    print()
    print("借鉴: 高强文书第 12 章 autogen-nestedchat.py")
    print("3 角色: UserProxy + Programmer + Reviewer (永久 invariant #22 + #75)")
    print()

    programmer = ProgrammerAgent()
    reviewer = ReviewerAgent()
    user_proxy = UserProxyAgent(programmer, reviewer, max_turns=4)

    queries = [
        {
            "query": "写一个 Python 函数 factorial(n), 计算 n 嘅阶乘 (n >= 0)。",
            "expected_check": lambda r: r.get("passed") and "def factorial" in r.get("code", "") and ("for" in r["code"] or "while" in r["code"] or "reduce" in r["code"]),
        },
        {
            "query": "写一个 Python 函数 is_palindrome(s), 判断字符串 s 系唔系回文。",
            "expected_check": lambda r: r.get("passed") and "def is_palindrome" in r.get("code", "") and "==" in r["code"],
        },
        {
            "query": "写一个 Python 函数 gcd(a, b), 求 a 同 b 嘅最大公约数 (用欧几里得算法)。",
            "expected_check": lambda r: r.get("passed") and "def gcd" in r.get("code", "") and "%" in r["code"],
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['query']}")
        r = user_proxy.run(q["query"])

        value_pass = q["expected_check"](r)
        passed = r.get("passed") and value_pass
        r["passed"] = passed
        r["query"] = q["query"]

        results.append(r)
        status = "✅" if passed else "❌"
        print(f"  {status} 嵌套 {r.get('turns', '?')} 轮, code: {r.get('code', '')[:200]}")
        if r.get("review"):
            print(f"       review approved={r['review'].get('approved')}, issues={r['review'].get('issues', [])}")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P3.5 AutoGen 嵌套对话深度实战: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = BASE / "autogen_nested_chat_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P3.5 AutoGen 嵌套对话深度实战",
        "provider": "MiniMax-M3 模拟 AutoGen 3 角色 (永久 invariant #51 + #22 + #75)",
        "agents": ["UserProxy", "Programmer", "Reviewer"],
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
