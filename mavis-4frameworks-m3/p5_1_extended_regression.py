#!/usr/bin/env python3
"""
P5.1 扩展 regression test (永久 invariant #79)

vs P5.0 (#69, 5 framework 9 真接入 test):
- 范围: P3.x 真接入 4 framework + P3.x 升级 3 framework + P4.x 3 framework = 10 真接入 framework
- 加 P5.x demo (1 framework)
- 总: 11 framework, 28 真接入 test

11 framework:
1. P3.0 GLM-4 FC (3 真 query)
2. P3.1 LangChain P&E (3 真 query)
3. P3.2 Qwen-Agent (3 真 query)
4. P3.3 CogVLM2 搜图 (3 真 query, 2/3 PASS)
5. P3.3+ BM25 hybrid (3 真 query)
6. P3.4 AgentScope ReAct (3 真 query)
7. P3.5 AutoGen 嵌套对话 (3 真 query)
8. P4.0 LoRA (1 query + 3 阶段训练)
9. P4.1 MemGPT 5 层记忆 V2 (4 真 query)
10. P4.2 AWEL (3 真 query)
11. P5.x 4 framework demo
"""
import sys
import os
import json
import time
import traceback
import io
import re
from pathlib import Path
from contextlib import redirect_stdout
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE.parent / "mavis-crewai-v7"))


# ============== 11 framework runner ==============

def run_with_capture(name: str, main_fn) -> dict:
    """跑 framework main(), 捕获 stdout, 解析 PASS/FAIL"""
    buf = io.StringIO()
    start = time.time()
    try:
        with redirect_stdout(buf):
            main_fn()
    except SystemExit:
        pass
    except Exception as e:
        return {"name": name, "passed": False, "error": str(e), "elapsed_s": round(time.time() - start, 2)}
    out = buf.getvalue()
    elapsed = round(time.time() - start, 2)

    # 解析 PASS 数 (3/3 PASS, 2/3 PASS, 4/4 PASS 等)
    import re
    m = re.search(r"(\d+)/(\d+) PASS", out)
    if m:
        passed_n, total_n = int(m.group(1)), int(m.group(2))
        return {
            "name": name,
            "passed": passed_n == total_n,
            "passed_n": passed_n,
            "total_n": total_n,
            "elapsed_s": elapsed,
        }
    return {"name": name, "passed": False, "elapsed_s": elapsed, "error": "no PASS found"}


def main():
    print("=" * 70)
    print("P5.1 扩展 regression test (永久 invariant #79)")
    print("=" * 70)
    print()
    print("vs P5.0 (5 framework 9 真接入 test):")
    print("  + P3.x 升级 3 framework (BM25 hybrid + AgentScope + AutoGen)")
    print("  + P4.x 3 framework (LoRA + MemGPT V2 + AWEL)")
    print("  = 11 framework, 28 真接入 test")
    print()

    # import 所有 framework 嘅 main
    from glm4_function_calling import main as p3_0_main
    from langchain_plan_execute import main as p3_1_main
    from qwen_agent_multi_agent import main as p3_2_main
    from cogvlm2_text_to_image import main as p3_3_main
    from cogvlm2_bm25_hybrid import main as p3_3h_main
    from agentscope_react import main as p3_4_main
    from autogen_nested_chat import main as p3_5_main
    from four_frameworks_m3 import main as p5_x_main

    tests = [
        ("P3.0 GLM-4 FC", p3_0_main),
        ("P3.1 LangChain P&E", p3_1_main),
        ("P3.2 Qwen-Agent", p3_2_main),
        ("P3.3 CogVLM2 搜图", p3_3_main),
        ("P3.3+ BM25 hybrid", p3_3h_main),
        ("P3.4 AgentScope ReAct", p3_4_main),
        ("P3.5 AutoGen 嵌套", p3_5_main),
        ("P5.x 4 framework demo", p5_x_main),
    ]

    # P3.x 嘅 import 用 venv python 跑
    print("\n[注意] P3.3 CogVLM2 + P3.3+ BM25 hybrid 需要 venv (含 llama-index)")
    print()

    results = []
    total_start = time.time()
    for name, fn in tests:
        print(f"\n[Test] {name}")
        r = run_with_capture(name, fn)
        status = "✅" if r.get("passed") else "❌"
        detail = f"{r.get('passed_n', '?')}/{r.get('total_n', '?')}" if "passed_n" in r else r.get("error", "?")
        print(f"  {status} {r.get('elapsed_s', '?')}s — {detail}")
        results.append(r)

    # P4.x framework - 用 subprocess venv 跑
    print("\n\n[Stage 2] P4.x framework (LoRA + MemGPT V2 + AWEL) — 用 venv 跑")
    p4_tests = [
        ("P4.0 LoRA (v1 + v2)", BASE.parent / "mavis-lora-p4-0" / "lora_finetune_v2.py"),
        ("P4.1 MemGPT V2", BASE.parent / "mavis-memgpt-p4-1" / "memgpt_v2_json_robust.py"),
        ("P4.2 AWEL", BASE.parent / "mavis-awel-p4-2" / "awel_skill_system.py"),
    ]
    import subprocess
    venv_python = "/Users/apple/workspace/mavis-framework/mavis-llamaindex-v2/.venv/bin/python"
    for name, path in p4_tests:
        print(f"\n[Test] {name}")
        start = time.time()
        try:
            result = subprocess.run(
                [venv_python, str(path)],
                capture_output=True, text=True,
                env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""},
                timeout=300,
            )
            elapsed = round(time.time() - start, 2)
            m = re.search(r"(\d+)/(\d+) PASS", result.stdout)
            if m:
                passed_n, total_n = int(m.group(1)), int(m.group(2))
                passed = passed_n == total_n
                detail = f"{passed_n}/{total_n}"
            else:
                passed = False
                detail = "no PASS"
            status = "✅" if passed else "❌"
            print(f"  {status} {elapsed}s — {detail}")
            results.append({"name": name, "passed": passed, "passed_n": m.group(1) if m else "?", "total_n": m.group(2) if m else "?", "elapsed_s": elapsed})
        except Exception as e:
            print(f"  ❌ {e}")
            results.append({"name": name, "passed": False, "error": str(e), "elapsed_s": 0})

    total_elapsed = time.time() - total_start
    passed_count = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P5.1 扩展 regression: {passed_count}/{len(results)} framework PASS, {total_elapsed:.1f}s")
    print("=" * 70)
    if passed_count == len(results):
        print("🎉 全部 11 framework 实战 stable!")
        print("💡 永久 invariant #79: mavis 11 framework 真接入 100% regression stable")

    # 写报告
    report_path = BASE / "p5_1_extended_regression_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P5.1 扩展 regression test",
        "framework_count": len(results),
        "passed_count": passed_count,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
