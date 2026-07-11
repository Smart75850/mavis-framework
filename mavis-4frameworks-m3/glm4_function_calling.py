#!/usr/bin/env python3
"""
P3.0 GLM-4 Function-calling 真接入 (永久 invariant #65)

借鉴: 高强文书第 8 章 glm4-functioncalling.py
- 2 工具: sympy 方程求解 + 大数相乘
- OpenAI 兼容 API 调 tools 节点
- M3 模拟 GLM-4 (永久 invariant #51 用 mavis_m3_provider)

实战: 3 真 query
- Q1: 9.11 和 9.9 边个大? (永久 invariant #58 demo test)
- Q2: 解方程 2x^2 + 3x - 5 = 0
- Q3: 2024 × 2025 + 2023 × 2024 = 几多?
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
from mavis_m3_provider import call_llm_m3, M3Provider


# ============== GLM-4 风格 2 工具 (借鉴第 8 章) ==============

TOOLS_GLM4_FC = [
    {
        "type": "function",
        "function": {
            "name": "solve_equation",
            "description": "求解一元二次方程 ax^2 + bx + c = 0, 使用 sympy",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "二次项系数"},
                    "b": {"type": "number", "description": "一次项系数"},
                    "c": {"type": "number", "description": "常数项"},
                    "variable": {"type": "string", "description": "变量名 (默认 x)", "default": "x"},
                },
                "required": ["a", "b", "c"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multiply_big_numbers",
            "description": "计算两个大数相乘 (超过 10 位), 避免 LLM 数学错误",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "被乘数 (任意位数整数)"},
                    "b": {"type": "integer", "description": "乘数 (任意位数整数)"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_decimals",
            "description": "比较两个小數嘅大小 (避免 LLM 数学错误)",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "小數 a"},
                    "b": {"type": "number", "description": "小數 b"},
                },
                "required": ["a", "b"],
            },
        },
    },
]


# ============== 工具实现 ==============

def solve_equation(a, b, c, variable="x"):
    try:
        from sympy import symbols, solve, Eq
        x = symbols(variable)
        eq = Eq(a * x**2 + b * x + c, 0)
        sols = solve(eq, x)
        return {"solutions": [str(s) for s in sols]}
    except ImportError:
        # sympy 唔可用时, 用二次公式
        import math
        disc = b**2 - 4 * a * c
        if disc < 0:
            return {"solutions": "无实数解 (discriminant < 0)"}
        sqrt_disc = math.sqrt(disc)
        x1 = (-b + sqrt_disc) / (2 * a)
        x2 = (-b - sqrt_disc) / (2 * a)
        return {"solutions": [str(x1), str(x2)]}


def multiply_big_numbers(a, b):
    return {"product": a * b}


def compare_decimals(a, b):
    if a > b:
        return {"result": f"{a} > {b}", "larger": a}
    elif a < b:
        return {"result": f"{a} < {b}", "larger": b}
    else:
        return {"result": f"{a} = {b}", "larger": None}


TOOL_DISPATCH = {
    "solve_equation": solve_equation,
    "multiply_big_numbers": multiply_big_numbers,
    "compare_decimals": compare_decimals,
}


# ============== M3 模拟 GLM-4 Function-calling ==============

def glm4_fc_chat(user_query: str, system: str = None) -> dict:
    """P3.0 实战: M3 模拟 GLM-4 function-calling (永久 invariant #65)"""
    default_system = (
        "你是一个数学助手, 可以调用工具来计算。\n"
        f"可用工具: {json.dumps(TOOLS_GLM4_FC, ensure_ascii=False)}\n"
        "\n"
        "**重要**: 无论问题点, 你都**必须**调用工具, **只返 JSON 格式**, 唔好返任何自然语言。\n"
        "JSON 格式: {\"tool\": \"tool_name\", \"args\": {...}}\n"
        "工具名只能是: solve_equation / multiply_big_numbers / compare_decimals"
    )

    start = time.time()
    response_text = call_llm_m3(
        system=system or default_system,
        user=user_query,
        max_tokens=500,
        temperature=0.2,
        use_fallback=True,
    )

    # 解析 M3 返 JSON (借鉴 GLM-4 tool_calls 节点)
    import re
    try:
        # 优先提取 ```json``` 块
        m = re.search(r"```json\s*(.*?)```", response_text, re.DOTALL)
        if m:
            call = json.loads(m.group(1))
        else:
            # 找最外层 {...}
            start_idx = response_text.find("{")
            if start_idx == -1:
                return {"passed": False, "error": "no JSON in M3 response", "raw": response_text}
            depth = 0
            end = start_idx
            for i in range(start_idx, len(response_text)):
                if response_text[i] == "{":
                    depth += 1
                elif response_text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            call = json.loads(response_text[start_idx:end])

        tool_name = call.get("tool")
        args = call.get("args", {})

        if tool_name not in TOOL_DISPATCH:
            return {"passed": False, "error": f"unknown tool: {tool_name}", "raw": response_text}

        # 执行工具
        tool_result = TOOL_DISPATCH[tool_name](**args)
    except Exception as e:
        return {"passed": False, "error": str(e), "raw": response_text}

    # Stage 2: M3 总结
    summary_system = "你是一个数学助手, 用中文简洁总结工具计算结果, 唔好省略数字。"
    summary_user = f"用户问题: {user_query}\n\n工具: {tool_name}\n参数: {args}\n结果: {json.dumps(tool_result, ensure_ascii=False)}"
    summary = call_llm_m3(
        system=summary_system,
        user=summary_user,
        max_tokens=200,
        temperature=0.3,
        use_fallback=True,
    )

    elapsed = round(time.time() - start, 2)
    return {
        "passed": True,
        "tool": tool_name,
        "args": args,
        "tool_result": tool_result,
        "summary": summary,
        "elapsed_s": elapsed,
    }


# ============== 实战: 3 真 query ==============

def main():
    print("=" * 70)
    print("P3.0 GLM-4 Function-calling 真接入 (永久 invariant #65)")
    print("=" * 70)
    print()
    print("3 真 query (借鉴第 8 章 glm4-functioncalling.py):")

    queries = [
        {
            "query": "9.11 同 9.9 边个大? 用工具计算",
            "expected_tool": "compare_decimals",
            "expected_value_check": lambda r: r.get("tool_result", {}).get("larger") == 9.9,
        },
        {
            "query": "解方程 2x^2 + 3x - 5 = 0, 用 sympy 工具",
            "expected_tool": "solve_equation",
            "expected_value_check": lambda r: any(
                s.replace(".0", "") in ["1", "-2.5"] for s in r.get("tool_result", {}).get("solutions", [])
            ),
        },
        {
            "query": "计算 2024 × 2025 + 2023 × 2024 = 几多?",
            "expected_tool": "multiply_big_numbers",
            "expected_value_check": lambda r: r.get("tool_result", {}).get("product") == 2024 * 2025,
        },
    ]

    results = []
    total_start = time.time()
    for i, q in enumerate(queries):
        print(f"\n[Test {i+1}/3] {q['query']}")
        r = glm4_fc_chat(q["query"])

        # 验证: tool 正确 + 结果正确 (lambda check)
        tool_pass = r.get("tool") == q["expected_tool"]
        value_pass = q["expected_value_check"](r)
        passed = tool_pass and value_pass
        r["passed"] = passed
        r["expected_tool"] = q["expected_tool"]

        results.append(r)
        status = "✅" if passed else "❌"
        print(f"  {status} 工具: {r.get('tool', '?')}, 结果: {json.dumps(r.get('tool_result', {}), ensure_ascii=False)[:80]}")
        print(f"  summary 前 200: {r.get('summary', '')[:200]}")
        if not passed:
            if not tool_pass:
                print(f"  ❌ 工具错: 期望 {q['expected_tool']}")
            elif not value_pass:
                print(f"  ❌ 结果值错")

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P3.0 GLM-4 FC 真接入实战: {passed_count}/3 PASS, {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = Path(__file__).parent / "glm4_fc_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P3.0 GLM-4 Function-calling 真接入",
        "provider": "MiniMax-M3 模拟 GLM-4 (永久 invariant #51 #53)",
        "tools": [t["function"]["name"] for t in TOOLS_GLM4_FC],
        "test_count": 3,
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
