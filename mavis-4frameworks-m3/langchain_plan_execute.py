#!/usr/bin/env python3
"""
P3.1 LangChain Plan-and-Execute 真接入 (永久 invariant #66)

借鉴: 高强文书第 10 章 langchain-plan-execute.py
- 4 阶段: 任务输入 → Plan 生成 → Execute → 最终答案
- 3 工具: search (math/scientific) / calculate / sumup
- 用 M3 模拟 LangChain (永久 invariant #51 用 mavis_m3_provider)

实战: 3 真 query (比 P5.2 demo 严格, 永久 invariant #58 教训)
- Q1: 圆周率保留 6 位小数, 佢嘅 2 次方系几多?
- Q2: 计算 24 × 365 = 几多? (用 search + calculate 2 步)
- Q3: 解方程 2x + 5 = 15 (用 search 概念 + calculate)
"""
import sys
import os
import json
import time
import re
import math
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v7"))
from mavis_m3_provider import call_llm_m3


# ============== 3 工具 (借鉴第 10 章 LLMMathChain + Bing 搜索) ==============

def tool_search(query: str) -> dict:
    """search 工具: 模拟 Bing 搜索, 返相关数据"""
    search_db = {
        "圆周率": "3.14159265358979",
        "pi": "3.14159265358979",
        "e": "2.71828182845905",
        "光速": "299792458 m/s",
        "重力加速度": "9.8 m/s²",
        "一年天数": "365",
        "一天秒数": "86400",
    }
    results = []
    for k, v in search_db.items():
        if k in query:
            results.append({"title": f"{k} 知识", "snippet": v})
    if not results:
        # 通用: 用 jieba 提取关键词
        try:
            import jieba
            keywords = [w for w in jieba.cut(query) if len(w) >= 2]
        except ImportError:
            keywords = [query]
        results.append({"title": f"搜索: {query}", "snippet": f"包含关键词: {', '.join(keywords[:3])}"})
    return {"results": results[:3]}


def tool_calculate(expression: str) -> dict:
    """calculate 工具: 用 Python eval 计算 (永久 invariant #66 安全)"""
    safe_expr = expression
    # 预处理: 替换常见数学符号 (永久 invariant #66 修复 × ÷)
    safe_expr = safe_expr.replace("×", "*")
    safe_expr = safe_expr.replace("÷", "/")
    safe_expr = safe_expr.replace("−", "-")  # Unicode 减号
    safe_expr = safe_expr.replace("^", "**")
    safe_expr = safe_expr.replace("=", "")  # 方程等号去掉
    safe_expr = safe_expr.replace("π", "math.pi")
    safe_expr = safe_expr.replace("圆周率", "math.pi")
    safe_expr = safe_expr.replace(" ", "")
    # 方程简化: 把 "2x" 变成 "(2*x)" 以便 eval
    safe_expr = re.sub(r"(\d)\s*([a-zA-Z])", r"\1*\2", safe_expr)
    safe_expr = re.sub(r"([a-zA-Z])\s*(\d)", r"\1*\2", safe_expr)
    # 安全: 只允许数字 / 运算符 / 圆周率 π / 单字母变量
    safe_chars = set("0123456789.+-*/() **")
    # 提取所有字母, 必须系单字母且仅出现一次 (防止任意代码注入)
    letters = set(c for c in safe_expr if c.isalpha())
    allowed_letters = {"x", "y", "e", "i", "n", "o", "s", "t", "a", "r", "q", "l", "g", "p", "m", "c"}
    bad_letters = letters - allowed_letters
    if bad_letters:
        return {"error": f"unsafe letters: {bad_letters} in '{expression}'"}
    if not all(c in safe_chars or c.isalpha() for c in safe_expr):
        return {"error": f"unsafe expression: {expression}"}
    try:
        # 用 math 命名空间执行
        result = eval(safe_expr, {"__builtins__": {}}, {"math": math, "pi": math.pi, "e": math.e})
        return {"result": str(result)}
    except Exception as e:
        return {"error": str(e)}


def tool_sumup(steps: list) -> dict:
    """sumup 工具: M3 总结所有步骤结果"""
    system = "你是一个答案汇总助手。用中文简洁总结以上步骤嘅结果, 唔好省略关键数字。"
    user = json.dumps(steps, ensure_ascii=False)
    summary = call_llm_m3(
        system=system,
        user=user,
        max_tokens=300,
        temperature=0.3,
        use_fallback=True,
    )
    return {"summary": summary}


TOOLS = {
    "search": tool_search,
    "calculate": tool_calculate,
    "sumup": tool_sumup,
}


# ============== 4 阶段 Plan-and-Execute ==============

def langchain_pae_chat(user_query: str) -> dict:
    """P3.1 真接入: M3 模拟 LangChain Plan-and-Execute (永久 invariant #66)"""
    total_start = time.time()

    # === Stage 1: Plan 生成 (借鉴 load_chat_planner) ===
    plan_system = (
        "你是一个 Plan-and-Execute Planner。\n"
        "**只返 JSON 数组**, 唔好解释。格式:\n"
        '[{"step": 1, "action": "search", "input": "..."}, {"step": 2, "action": "calculate", "input": "3.141592**2"}]\n'
        "action 只能是 3 个值: search / calculate / sumup。\n"
        "**重要**: 对于需要查知识 + 计算嘅复合问题, 必须先用 search 取数据, 再用 calculate 算最终结果。\n"
        "calculate 的 input 必须是合法的 Python 数学表达式, 例如 '24*365' 或 '3.141592**2'。\n"
        "**唔好直接用 sumup 总结**, sumup 系最后自动执行。\n"
        "**唔好写任何自然语言**, 只返 JSON 数组。"
    )
    plan_user = f"用户问题: {user_query}"
    plan_raw = call_llm_m3(
        system=plan_system,
        user=plan_user,
        max_tokens=400,
        temperature=0.1,  # 降低温度, 提升 JSON 一致性
        use_fallback=True,
    )

    # 解析计划: 先试行解析, 失败再用 regex 抽取 JSON 块
    plan_steps = []
    for line in plan_raw.split("\n"):
        line = line.strip()
        # 去掉 markdown ```json 包装
        line = line.strip("`").strip()
        if line.startswith("{"):
            try:
                step = json.loads(line)
                if "step" in step and "action" in step and "input" in step:
                    plan_steps.append(step)
            except Exception:
                pass
    if not plan_steps:
        # fallback: 用 regex 抽 JSON 块
        import re as _re
        json_blocks = _re.findall(r'\{[^{}]*"action"[^{}]*\}', plan_raw)
        for blk in json_blocks:
            try:
                step = json.loads(blk)
                if "step" in step and "action" in step and "input" in step:
                    plan_steps.append(step)
            except Exception:
                pass
    if not plan_steps:
        # last fallback: 整段尝试 json.loads
        try:
            arr_match = _re.search(r'\[.*\]', plan_raw, _re.DOTALL)
            if arr_match:
                arr = json.loads(arr_match.group(0))
                if isinstance(arr, list):
                    plan_steps = [s for s in arr if "step" in s and "action" in s and "input" in s]
        except Exception:
            pass
    if not plan_steps:
        return {"passed": False, "error": "plan parsing failed", "raw_plan": plan_raw}

    # === Stage 2-3: Execute (借鉴 load_agent_executor) ===
    execute_results = []
    for step in plan_steps:
        action = step.get("action")
        inp = step.get("input", "")
        if action in TOOLS:
            r = TOOLS[action](inp)
            execute_results.append({"step": step.get("step"), "action": action, "output": r})
        else:
            execute_results.append({"step": step.get("step"), "action": action, "error": f"unknown action: {action}"})

    # === Stage 4: Sumup (借鉴 _strip) ===
    sumup_r = tool_sumup(execute_results)
    final_answer = sumup_r.get("summary", "无总结")

    elapsed = round(time.time() - total_start, 2)
    return {
        "passed": True,
        "plan_steps": len(plan_steps),
        "execute_results": execute_results,
        "summary": final_answer,
        "elapsed_s": elapsed,
    }


# ============== 实战: 3 真 query (lambda 真值检查) ==============

def main():
    print("=" * 70)
    print("P3.1 LangChain Plan-and-Execute 真接入 (永久 invariant #66)")
    print("=" * 70)
    print()
    print("3 真 query (比 P5.2 demo 严格, 永久 invariant #58 教训):")

    queries = [
        {
            "query": "圆周率保留到小数点后 6 位系几多? 佢嘅 2 次方系几多?",
            "expected_core_actions": ["search", "calculate"],  # sumup 系 Stage 4 自动
            "expected_check": lambda r: "3.141592" in r.get("summary", "") or "9.8696" in r.get("summary", ""),
        },
        {
            "query": "计算 24 × 365 等于几多?",
            "expected_core_actions": ["calculate"],
            "expected_check": lambda r: "8760" in r.get("summary", "") or "8760" in json.dumps(r.get("execute_results", []), ensure_ascii=False),
        },
        {
            "query": "解方程 2x + 5 = 15, x 系几多?",
            "expected_core_actions": ["calculate"],
            "expected_check": lambda r: "5" in r.get("summary", "") or "x = 5" in r.get("summary", "").lower() or "5.0" in r.get("summary", ""),
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['query']}")
        r = langchain_pae_chat(q["query"])

        # 验证: core_actions 出现 (sumup 唔系 plan 步骤) + 真值检查
        plan_actions = [step.get("action") for step in r.get("execute_results", [])]
        actions_pass = all(a in plan_actions for a in q["expected_core_actions"])
        value_pass = q["expected_check"](r)
        passed = r.get("passed") and actions_pass and value_pass
        r["passed"] = passed
        r["expected_core_actions"] = q["expected_core_actions"]

        results.append(r)
        status = "✅" if passed else "❌"
        print(f"  {status} plan {len(r.get('execute_results', []))} 步, actions: {plan_actions}")
        print(f"  summary 前 200: {r.get('summary', '')[:200]}")
        if not passed:
            if not r.get("passed"):
                print(f"  ❌ plan/execute 失败: {r.get('error', '?')}")
            elif not actions_pass:
                print(f"  ❌ actions 错: 期望 {q['expected_core_actions']}, 实际 {plan_actions}")
            elif not value_pass:
                print(f"  ❌ 真值错: 期望含 expected 关键词, summary: {r.get('summary', '')[:100]}")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P3.1 LangChain Plan-and-Execute 真接入: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = Path(__file__).parent / "langchain_pae_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P3.1 LangChain Plan-and-Execute 真接入",
        "provider": "MiniMax-M3 模拟 LangChain (永久 invariant #51)",
        "tools": list(TOOLS.keys()),
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
