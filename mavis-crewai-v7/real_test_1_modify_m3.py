#!/usr/bin/env python3
"""
真实测试 1: M3 改 mavis-framework 真实项目文件
(不是 demo, 是真嘅 7K-10K 字符生产代码)
"""
import sys
import os
import json
import time
import shutil
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

sys.path.insert(0, str(Path(__file__).parent))
from mavis_m3_provider import call_llm_m3

FRAMEWORK = Path.home() / "workspace" / "mavis-framework"


def _linter_check(file_path: str) -> str:
    import py_compile
    try:
        py_compile.compile(file_path, doraise=True)
        return "passed"
    except py_compile.PyCompileError as e:
        return f"failed: {e}"


def _extract_python_code(text: str) -> str:
    import re
    m = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def modify_file_with_m3(file_path: Path, query: str, threshold: float = 0.70) -> dict:
    """M3 改文件 (永久 invariant #51 + P3.5 修复)"""
    backup = file_path.with_suffix(file_path.suffix + ".real.bak")
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    # 永久 invariant #52 修正: prompt 强制 "保留原代码 100%"
    coder_system = (
        "你是一个 Python 编程专家。请根据用户要求修改给定嘅 Python 文件。\n"
        "\n"
        "**绝对规则**:\n"
        "1. 必须输出**完整文件**, 保留所有原 import / function / class / variable\n"
        "2. 唔好简化任何原代码, 唔好删除任何原有逻辑\n"
        "3. 用 ```python 块包裹完整文件\n"
        "4. 用中文写注释\n"
        "5. 修改范围越小越好, 只改用户要求嘅部分, 其他完全保留"
    )
    # 关键: 用 chr(10) 或 os.linesep 避免 bash escape 问题
    NL = chr(10)
    coder_user = (
        f"原文件: {file_path.name}{NL}"
        f"原文件长度: {original_size} 字符{NL}"
        f"任务: {query}{NL}{NL}"
        f"原文件内容:{NL}```python{NL}{original}{NL}```{NL}{NL}"
        f"请输出修改后嘅完整 Python 文件, 保留所有原代码, 用 ```python 块包裹。"
    )

    start = time.time()
    try:
        new_code = call_llm_m3(
            system=coder_system,
            user=coder_user,
            max_tokens=20000,
            temperature=0.2,  # 低温度, 保持原代码稳定
            use_fallback=True,
        )
    except Exception as e:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {"file": str(file_path.relative_to(FRAMEWORK)), "error": str(e), "passed": False, "elapsed_s": round(time.time()-start, 2)}

    new_content = _extract_python_code(new_code)
    ratio = len(new_content) / original_size if original_size else 0
    elapsed = round(time.time() - start, 2)

    # 长度检查 (P3.5 修复: 30% / 70%)
    if ratio < threshold:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "file": str(file_path.relative_to(FRAMEWORK)),
            "original_size": original_size,
            "new_size": len(new_content),
            "ratio": round(ratio, 4),
            "threshold": threshold,
            "length_check": "FAILED",
            "passed": False,
            "elapsed_s": elapsed,
            "error": f"length ratio {ratio:.2%} < {threshold:.0%}",
        }

    # 写文件
    file_path.write_text(new_content, encoding="utf-8")

    # Linter 验证
    linter = _linter_check(str(file_path))
    if "failed" in linter:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "file": str(file_path.relative_to(FRAMEWORK)),
            "original_size": original_size,
            "new_size": len(new_content),
            "ratio": round(ratio, 4),
            "linter": linter,
            "passed": False,
            "elapsed_s": elapsed,
            "error": f"linter failed: {linter}",
        }

    # 成功 - 留文件 (真测试不动 backup, 大佬可自己 revert)
    return {
        "file": str(file_path.relative_to(FRAMEWORK)),
        "original_size": original_size,
        "new_size": len(new_content),
        "ratio": round(ratio, 4),
        "linter": "passed",
        "passed": True,
        "elapsed_s": elapsed,
        "backup": str(backup.relative_to(FRAMEWORK)),
    }


def main():
    print("=" * 70)
    print("真实测试 1: M3 改 mavis-framework 真实项目文件")
    print("=" * 70)
    print()
    print("目标 3 文件 (真 mavis framework 生产代码):")

    targets = [
        (FRAMEWORK / "mavis-recall-v2" / "recall.py",
         "在文件顶部加一段 module docstring, 说明呢个系 mavis memory recall v2, 永久 invariant #30 落地, 支持中文 jieba 分词 + Hybrid 检索"),
        (FRAMEWORK / "mavis-8mech-router-v2" / "router.py",
         "在 EIGHT_MECHANISMS 顶部加一行注释, 说明呢个系 mavis 8 机制 query 路由, 永久 invariant #37"),
        (FRAMEWORK / "mavis-crewai-v7" / "mavis_m3_provider.py",
         "在 M3Provider class 顶部加 docstring, 说明呢个系 mavis framework 嘅 M3 cloud LLM provider, 永久 invariant #51"),
    ]

    for tf, q in targets:
        size = tf.stat().st_size
        print(f"  - {tf.relative_to(FRAMEWORK)} ({size} 字符)")

    results = []
    total_start = time.time()
    for tf, q in targets:
        print(f"\n[Test] 改 {tf.name} ({tf.stat().st_size} 字符)")
        r = modify_file_with_m3(tf, q)
        results.append(r)
        if r.get("passed"):
            print(f"  ✅ PASS: {r['original_size']} -> {r['new_size']} (ratio {r['ratio']:.2%}, {r['elapsed_s']}s)")
        else:
            print(f"  ❌ FAIL: {r.get('error', '?')}")

    total_elapsed = time.time() - total_start
    passed = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"真实测试 1 完成: {passed}/3 PASS, 总 {total_elapsed:.1f}s")
    print("=" * 70)

    # 写报告
    report_path = Path(__file__).parent / "real_test_1_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "真实测试 1: M3 改 mavis-framework 真实项目文件",
        "provider": "MiniMax-M3 (永久 invariant #51)",
        "test_count": 3,
        "passed_count": passed,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
