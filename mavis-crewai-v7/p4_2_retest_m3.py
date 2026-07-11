#!/usr/bin/env python3
"""
P4.2 retest with M3 (永久 invariant #52)
- 之前 P4.2 9/9 报告 PASS 实际 7/9 真 PASS, 失败 Test 3+4 系大文件 (16K+ 21K)
- 永久 invariant #34 说 14B 写不动 10000+ 字符
- 现在接 M3 (永久 invariant #51), 大文件应该 100% PASS
- 真 verify: P3.5 修复 + M3 接入后, 9 个大文件改写 9/9 跑通
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

# 用 mavis venv (有 llama-index)
sys.path.insert(0, "/Users/apple/workspace/mavis-llamaindex-v2/.venv/lib/python3.12/site-packages")

# 用 monorepo 内部 crewai_v6 + crewai_v4
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v6"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v4"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v7"))

# M3 provider
sys.path.insert(0, str(Path(__file__).parent))
from mavis_m3_provider import call_llm_m3, M3Provider

# CrewAI
from crewai_v6 import coder_real_file_v6, reviewer_real_file_v6, build_p35_crew_v6, run_crew_v6
from crewai_v4 import call_llm_14b  # 已经改成 M3

# 工具
def _linter_check(file_path: str) -> str:
    """py_compile check"""
    import py_compile
    try:
        py_compile.compile(file_path, doraise=True)
        return "passed"
    except py_compile.PyCompileError as e:
        return f"failed: {e}"


def _extract_python_code(text: str) -> str:
    """提取 ```python``` 块"""
    import re
    m = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def p4_2_retest_m3():
    """P4.2 retest with M3 - 9 大文件改写"""
    print("=" * 70)
    print("P4.2 retest with M3 (永久 invariant #52)")
    print("=" * 70)
    print()

    P40_HOME = Path.home() / "workspace" / "mavis-framework"
    P40_DIR = Path(__file__).parent

    # 选 9 个 mavis framework 自己的 .py 文件 (包含大文件)
    py_files = []
    for project in ["mavis-team-plan-v2", "mavis-8mech-router-v2", "mavis-crewai-v3", "mavis-crewai-v4"]:
        project_path = P40_HOME / project
        for py_file in project_path.rglob("*.py"):
            if py_file.is_file() and not py_file.name.startswith("_") and not py_file.name.startswith("test"):
                py_files.append(py_file)

    # 按大小排序, 包含大文件 (16K+ 21K)
    py_files.sort(key=lambda f: f.stat().st_size, reverse=True)

    # 9 个文件: 包括最大的 2 个 (mavis-crewai-v3.py + crewai_v4.py)
    target_files = py_files[:9]
    print(f"\n目标 9 文件 (按大小):")
    for tf in target_files:
        print(f"  - {tf.relative_to(P40_HOME)} ({tf.stat().st_size} 字符)")

    # 9 个改文件任务
    change_types = [
        ("docstring", "给 {filename} 的函数添加 docstring, 说明参数和返回值"),
        ("type_hints", "给 {filename} 的函数添加 type hints"),
        ("comments", "给 {filename} 添加详细中文注释, 解释每行代码"),
    ]
    results = []
    total_start = time.time()

    for i, tf in enumerate(target_files):
        change_type, template = change_types[i % len(change_types)]
        filename = tf.name
        query = template.format(filename=filename)
        backup_path = tf.with_suffix(tf.suffix + ".p42retest.backup")
        shutil.copy2(tf, backup_path)
        original_content = tf.read_text(encoding="utf-8")
        original_size = len(original_content)
        print(f"\n[Test {i+1}/9] {change_type}: {tf.name} ({original_size} 字符)")
        print(f"  query: {query[:80]}")

        test_start = time.time()
        try:
            # 直接用 M3 调 Coder (永久 invariant #51 已接通)
            # 1. 调 Coder 拿完整文件
            coder_system = (
                "你是一个 Python 编程专家。请根据用户要求修改给定的 Python 文件, 输出完整文件内容。\n"
                "要求:\n"
                "1. 必须输出完整文件, 唔好简化任何原代码\n"
                "2. 用 ```python 块包裹完整文件\n"
                "3. 中文注释\n"
                "4. 保留所有原 import / function / class"
            )
            coder_user = (
                f"原文件: {filename}\n"
                f"原文件长度: {original_size} 字符\n"
                f"任务: {query}\n\n"
                f"原文件内容:\n```python\n{original_content}\n```\n\n"
                f"请输出修改后嘅完整 Python 文件, 用 ```python 块包裹。"
            )

            print(f"  调 Coder (M3)...")
            new_code = call_llm_m3(
                system=coder_system,
                user=coder_user,
                max_tokens=16000,  # 永久 invariant #51: M3 支持 16K output
                temperature=0.3,
                use_fallback=True,
            )
            print(f"  Coder 返: {len(new_code)} 字符 (原 {original_size})")

            # 2. 提取 python 块
            new_file_content = _extract_python_code(new_code)

            # 3. 长度检查 (P3.5 永久 invariant: 30% / 70%)
            ratio = len(new_file_content) / original_size if original_size else 0
            is_small_change = any(kw in query for kw in [
                "加一行", "改函数名", "改字串", "改一个", "小改",
            ])
            threshold = 0.30 if is_small_change else 0.70
            passed_length = ratio >= threshold

            print(f"  长度 ratio: {ratio:.2%} (threshold {threshold:.0%}, {'✓' if passed_length else '✗'})")

            if not passed_length:
                # 失败回滚
                shutil.copy2(backup_path, tf)
                results.append({
                    "test": i + 1,
                    "file": str(tf.relative_to(P40_HOME)),
                    "change_type": change_type,
                    "original_size": original_size,
                    "new_size": len(new_file_content),
                    "ratio": round(ratio, 4),
                    "threshold": threshold,
                    "length_check": "FAILED",
                    "linter": "rolled_back",
                    "file_changed": False,
                    "error": f"length ratio {ratio:.2%} < {threshold:.0%}",
                })
                print(f"  ❌ 长度检查失败, 回滚")
                continue

            # 4. 写文件
            tf.write_text(new_file_content, encoding="utf-8")

            # 5. Linter 验证 (P3.5 永久 invariant)
            linter_result = _linter_check(str(tf))
            print(f"  Linter: {linter_result}")

            if "failed" in linter_result:
                # P3.5 失败回滚
                shutil.copy2(backup_path, tf)
                results.append({
                    "test": i + 1,
                    "file": str(tf.relative_to(P40_HOME)),
                    "change_type": change_type,
                    "original_size": original_size,
                    "new_size": len(new_file_content),
                    "ratio": round(ratio, 4),
                    "length_check": "passed",
                    "linter": linter_result,
                    "file_changed": False,
                    "error": f"linter failed: {linter_result}",
                })
                print(f"  ❌ Linter 失败, 回滚")
                continue

            # 6. 成功
            test_elapsed = time.time() - test_start
            results.append({
                "test": i + 1,
                "file": str(tf.relative_to(P40_HOME)),
                "change_type": change_type,
                "original_size": original_size,
                "new_size": len(new_file_content),
                "ratio": round(ratio, 4),
                "threshold": threshold,
                "length_check": "passed",
                "linter": "passed",
                "file_changed": True,
                "elapsed_s": round(test_elapsed, 2),
            })
            print(f"  ✅ PASS ({test_elapsed:.1f}s)")

        except Exception as e:
            shutil.copy2(backup_path, tf)
            results.append({
                "test": i + 1,
                "file": str(tf.relative_to(P40_HOME)),
                "error": str(e),
                "file_changed": False,
            })
            print(f"  ❌ Exception: {e}")

    # 恢复所有 backup
    for tf in target_files:
        backup_path = tf.with_suffix(tf.suffix + ".p42retest.backup")
        if backup_path.exists():
            shutil.copy2(backup_path, tf)
            backup_path.unlink()
    print(f"\n✅ 9 文件全部恢复原状 (rollback)")

    # 写报告
    total_elapsed = time.time() - total_start
    valid = [r for r in results if r.get("file_changed")]
    linter_passed = sum(1 for r in results if r.get("linter") == "passed")
    file_changed = sum(1 for r in results if r.get("file_changed"))
    length_passed = sum(1 for r in results if r.get("length_check") == "passed")
    avg_elapsed = round(sum(r.get("elapsed_s", 0) for r in valid) / len(valid), 2) if valid else 0

    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P4.2 retest with M3 (永久 invariant #52)",
        "provider": "MiniMax-M3 via mavis_m3_provider",
        "test_count": len(results),
        "file_changed": file_changed,
        "linter_passed": linter_passed,
        "length_check_passed": length_passed,
        "avg_elapsed_s": avg_elapsed,
        "total_elapsed_s": round(total_elapsed, 2),
        "previous_p4.2_local_14b": {
            "file_changed": 7,
            "test_count": 9,
            "failed_tests": [3, 4],
            "failed_reason": "本地 14B 写不动 16924 + 21736 字符",
        },
        "queries": results,
    }
    report_path = P40_DIR / "p4.2-retest-m3-results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 70)
    print(f"P4.2 retest with M3 完成")
    print("=" * 70)
    print(f"  总耗时: {total_elapsed:.1f}s")
    print(f"  测试数: {len(results)}")
    print(f"  改文件: {file_changed}/{len(results)} ({file_changed/len(results)*100:.0f}%)")
    print(f"  Linter PASS: {linter_passed}/{len(results)}")
    print(f"  长度检查 PASS: {length_passed}/{len(results)}")
    print(f"  之前 P4.2 (本地 14B): 7/9 改文件")
    print(f"  报告: {report_path}")
    print()
    return report


if __name__ == "__main__":
    report = p4_2_retest_m3()
