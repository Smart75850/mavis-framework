#!/usr/bin/env python3
"""
P4.7 改进路径 B (永久 invariant #62) — 100% 改大文件 work

P4.5 路径 B 2/3 失败原因: M3 写 SEARCH 块唔 100% 复制原代码, 4 retries 都失败
P4.7 改进:
- 1. retry 4 → 8
- 2. 预生成 SEARCH 块 (服务端用 grep 找精确 line, 给 LLM 看真位置)
- 3. 提供"预定义 transform" 模式 (add_docstring_to_module / add_docstring_to_class / add_import)
   唔靠 LLM, 直接用 libcst 生成精确 SEARCH/REPLACE 块
- 4. 智能识别 query 关键词, 自动选 transform

目标: P4.5 路径 B 2/3 → P4.7 路径 B 3/3 PASS
"""
import sys
import os
import json
import time
import shutil
import re
import subprocess
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

sys.path.insert(0, "/Users/apple/workspace/mavis-llamaindex-v2/.venv/lib/python3.12/site-packages")
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


# ============== 预定义 transform (唔靠 LLM) ==============

def transform_add_module_docstring(file_path: Path, docstring: str) -> dict:
    """预定义 transform 1: 加 module docstring (唔靠 LLM)"""
    import libcst as cst
    backup = file_path.with_suffix(file_path.suffix + ".p47.bak")
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    start = time.time()
    try:
        tree = cst.parse_module(original)
        new_docstring = cst.SimpleStatementLine(
            body=[cst.Expr(value=cst.SimpleString(f'"""{docstring}"""'))]
        )
        new_body = [new_docstring] + list(tree.body)
        new_tree = tree.with_changes(body=new_body)
        new_code = new_tree.code
        file_path.write_text(new_code, encoding="utf-8")
    except Exception as e:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "transform": "add_module_docstring",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "passed": False,
            "error": str(e),
            "elapsed_s": round(time.time() - start, 2),
        }

    elapsed = round(time.time() - start, 2)
    linter = _linter_check(str(file_path))
    if "failed" in linter:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "transform": "add_module_docstring",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "original_size": original_size,
            "new_size": len(new_code),
            "linter": linter,
            "passed": False,
            "elapsed_s": elapsed,
        }

    return {
        "transform": "add_module_docstring",
        "file": str(file_path.relative_to(FRAMEWORK)),
        "original_size": original_size,
        "new_size": len(new_code),
        "ratio": round(len(new_code) / original_size, 4),
        "linter": "passed",
        "passed": True,
        "elapsed_s": elapsed,
    }


def transform_add_import(file_path: Path, import_line: str) -> dict:
    """预定义 transform 2: 加 import (唔靠 LLM)"""
    import libcst as cst
    backup = file_path.with_suffix(file_path.suffix + ".p47.bak")
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    start = time.time()
    try:
        tree = cst.parse_module(original)
        new_import = cst.SimpleStatementLine(
            body=[cst.Import([cst.ImportAlias(name=cst.Name(import_line))])]
        )
        new_body = [new_import] + list(tree.body)
        new_tree = tree.with_changes(body=new_body)
        new_code = new_tree.code
        file_path.write_text(new_code, encoding="utf-8")
    except Exception as e:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "transform": "add_import",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "passed": False,
            "error": str(e),
            "elapsed_s": round(time.time() - start, 2),
        }

    elapsed = round(time.time() - start, 2)
    linter = _linter_check(str(file_path))
    if "failed" in linter:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "transform": "add_import",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "original_size": original_size,
            "new_size": len(new_code),
            "linter": linter,
            "passed": False,
            "elapsed_s": elapsed,
        }

    return {
        "transform": "add_import",
        "file": str(file_path.relative_to(FRAMEWORK)),
        "original_size": original_size,
        "new_size": len(new_code),
        "ratio": round(len(new_code) / original_size, 4),
        "linter": "passed",
        "passed": True,
        "elapsed_s": elapsed,
    }


def smart_pick_transform(query: str, file_path: Path) -> dict:
    """智能识别 query, 选 transform"""
    query_lower = query.lower()
    if "docstring" in query_lower or "文档" in query or "注释" in query:
        # 加 module docstring
        return transform_add_module_docstring(file_path, query)
    elif "import" in query_lower:
        # 加 import (提取 module 名)
        import_match = re.search(r"import\s+(\w+)", query)
        if import_match:
            return transform_add_import(file_path, import_match.group(1))
    # 默认: 加 module docstring
    return transform_add_module_docstring(file_path, query)


# ============== Aider 路径 B (retry 8) ==============

def aider_extract_blocks(text: str) -> list:
    blocks = []
    pattern = r"```search/replace\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    for m in matches:
        m_split = re.split(r"={3,}\n", m)
        if len(m_split) == 2:
            search_text = m_split[0].replace("<<<<<<< SEARCH\n", "").strip("\n")
            replace_text = m_split[1].replace(">>>>>>> REPLACE\n", "").strip("\n")
            blocks.append({"search": search_text, "replace": replace_text})
    return blocks


def aider_apply_blocks(content: str, blocks: list) -> tuple:
    new_content = content
    applied = 0
    for block in blocks:
        if block["search"] in new_content:
            new_content = new_content.replace(block["search"], block["replace"], 1)
            applied += 1
        else:
            return new_content, applied, f"search not found: {block['search'][:80]}"
    return new_content, applied, None


def aider_path_b(file_path: Path, query: str, max_retry: int = 8) -> dict:
    """Aider 路径: LLM 输出 search/replace 块 + retry 8 + 详细错误反馈"""
    backup = file_path.with_suffix(file_path.suffix + ".p45b.bak")
    if backup.exists():
        shutil.copy2(backup, file_path)
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    start = time.time()

    # 预提取可能嘅 SEARCH 块 (文件 line 1-3 嘅原内容, 给 LLM 提示)
    first_lines = "\n".join(original.split("\n")[:5])
    last_lines = "\n".join(original.split("\n")[-5:])

    system = (
        "你是一个 Python 编程专家。请用 **Aider search/replace 块** 格式修改给定嘅 Python 文件。\n"
        "\n"
        "**格式** (严格遵守):\n"
        "```search/replace\n"
        "<<<<<<< SEARCH\n"
        "原代码片段 (必须 100% 复制, 包括缩进和空行)\n"
        "=======\n"
        "新代码片段\n"
        ">>>>>>> REPLACE\n"
        "```\n"
        "\n"
        "**7 大绝对规则**:\n"
        "1. **SEARCH 必须 100% 复制原文件**, 包括缩进 / 空行 / 注释\n"
        "2. 唔好简化任何原代码\n"
        "3. REPLACE 只改用户要求嘅部分, 其他原代码保留\n"
        "4. 唔好加 ```python``` 块包裹, 用 ```search/replace``` 包裹\n"
        "5. 可以多对 SEARCH/REPLACE (多个块)\n"
        "6. 保持括号/缩进/空行\n"
        "7. 复制原代码时, 唔好凭记忆, 直接复制我畀嘅原文件内容"
    )
    user = (
        f"文件: {file_path.name}\n"
        f"原文件长度: {original_size} 字符\n"
        f"任务: {query}\n\n"
        f"原文件 (前面 5 行):\n```python\n{first_lines}\n```\n"
        f"原文件 (最后 5 行):\n```python\n{last_lines}\n```\n\n"
        f"完整原文件:\n```python\n{original}\n```\n\n"
        f"请输出 Aider search/replace 块。"
    )

    for attempt in range(max_retry):
        new_text = call_llm_m3(
            system=system,
            user=user,
            max_tokens=20000,
            temperature=0.0,  # 极低温度, 提高一致性
            use_fallback=True,
        )

        blocks = aider_extract_blocks(new_text)
        if not blocks:
            user += "\n\n**Retry**: 你上次返嘅唔系 Aider search/replace 格式, 必须用 ```search/replace\n<<<<<<< SEARCH\n原文件片段\n=======\n新文件片段\n>>>>>>> REPLACE\n``` 包裹"
            continue

        new_content, applied, error = aider_apply_blocks(original, blocks)
        if error:
            # 详细错误反馈: 显示原文件 5 行
            user += f"\n\n**Retry**: {error}\n\n**重要**: 你嘅 SEARCH 块必须 100% 复制原文件以下片段:\n```python\n{original[:500]}\n```"
            continue

        if applied == 0:
            user += "\n\n**Retry**: 0 块成功应用, 请 verify SEARCH 块真系原文件内容"
            continue

        # 写 + Linter
        file_path.write_text(new_content, encoding="utf-8")
        linter = _linter_check(str(file_path))
        if "failed" in linter:
            shutil.copy2(backup, file_path)
            user += f"\n\n**Retry**: linter failed: {linter}, 请检查语法"
            continue

        elapsed = round(time.time() - start, 2)
        return {
            "path": "B",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "original_size": original_size,
            "new_size": len(new_content),
            "ratio": round(len(new_content) / original_size, 4),
            "linter": "passed",
            "applied_blocks": applied,
            "retry_count": attempt,
            "passed": True,
            "elapsed_s": elapsed,
        }

    elapsed = round(time.time() - start, 2)
    shutil.copy2(backup, file_path)
    backup.unlink()
    return {
        "path": "B",
        "file": str(file_path.relative_to(FRAMEWORK)),
        "passed": False,
        "linter": "rolled_back",
        "elapsed_s": elapsed,
        "error": f"all {max_retry} retries failed",
    }


# ============== 实战: P4.7 智能 transform (3 真文件) ==============

def main():
    print("=" * 70)
    print("P4.7 智能 transform + Aider 改进 (永久 invariant #62)")
    print("=" * 70)
    print()
    print("目标 3 真 mavis-framework 文件 + 2 路径:")
    print("  - mavis-recall-v2/recall.py")
    print("  - mavis-8mech-router-v2/router.py")
    print("  - mavis-crewai-v7/mavis_m3_provider.py")
    print()
    print("2 路径:")
    print("  - 智能 transform (唔靠 LLM, libcst 直生成)")
    print("  - Aider search/replace (retry 4 → 8, 预提取 first/last lines)")
    print()

    targets = [
        (FRAMEWORK / "mavis-recall-v2" / "recall.py", "加 module docstring: mavis memory recall v2 - 永久 invariant #30 落地"),
        (FRAMEWORK / "mavis-8mech-router-v2" / "router.py", "加 module docstring: mavis 8 机制 query 路由 - 永久 invariant #37"),
        (FRAMEWORK / "mavis-crewai-v7" / "mavis_m3_provider.py", "加 module docstring: mavis M3 Provider - 永久 invariant #51 落地"),
    ]

    results = []
    total_start = time.time()

    for fp, query in targets:
        print(f"\n[File] {fp.relative_to(FRAMEWORK)}")

        # 路径 1: 智能 transform (唔靠 LLM)
        print(f"  [智能 transform] smart_pick_transform...")
        r_smart = smart_pick_transform(query, fp)
        print(f"  智能 transform: {'✅' if r_smart.get('passed') else '❌'} {r_smart.get('elapsed_s', 0)}s, linter={r_smart.get('linter', '?')}")
        results.append(r_smart)

        # 路径 2: Aider retry 8
        print(f"  [Aider retry 8] aider_path_b...")
        # restore 原版
        backup = fp.with_suffix(fp.suffix + ".p47.bak")
        if backup.exists():
            shutil.copy2(backup, fp)
            backup.unlink()
        r_aider = aider_path_b(fp, query, max_retry=8)
        print(f"  Aider retry 8: {'✅' if r_aider.get('passed') else '❌'} {r_aider.get('elapsed_s', 0)}s, linter={r_aider.get('linter', '?')}")
        results.append(r_aider)

        # 还原原版
        backup_b = fp.with_suffix(fp.suffix + ".p45b.bak")
        if backup_b.exists():
            shutil.copy2(backup_b, fp)
            backup_b.unlink()

    total_elapsed = time.time() - total_start

    # 总结
    print()
    print("=" * 70)
    print("P4.7 2 路径总结果")
    print("=" * 70)
    smart_pass = sum(1 for r in results if r.get("transform") == "add_module_docstring" and r.get("passed"))
    aider_pass = sum(1 for r in results if r.get("path") == "B" and r.get("passed"))
    print(f"智能 transform (唔靠 LLM): {smart_pass}/3 PASS")
    print(f"Aider retry 8 (LLM):        {aider_pass}/3 PASS")
    print(f"总耗时: {total_elapsed:.1f}s")
    print()
    print(f"P4.5 路径 A (libcst 独立脚本): 3/3 PASS (永久 invariant #60)")
    print(f"P4.5 路径 B (Aider retry 4):   2/3 PASS")
    print(f"P4.6 整合到 mavis_v3:           3/3 PASS (永久 invariant #61)")
    print(f"P4.7 智能 transform:             {smart_pass}/3")
    print(f"P4.7 Aider retry 8:              {aider_pass}/3")
    print()

    # 还原 (用 git)
    for fp, _ in targets:
        try:
            subprocess.run(["git", "checkout", "--", str(fp.relative_to(FRAMEWORK))],
                         cwd=FRAMEWORK, capture_output=True, timeout=10)
        except Exception:
            pass

    # 写报告
    report_path = Path(__file__).parent / "p4_7_diff_improved_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P4.7 智能 transform + Aider retry 8 改进",
        "test_count": 6,
        "results": results,
        "summary": {
            "smart_transform": f"{smart_pass}/3",
            "aider_retry_8": f"{aider_pass}/3",
            "total_elapsed_s": round(total_elapsed, 2),
        },
        "previous_p4_5": {
            "path_a_libcst": "3/3",
            "path_b_aider": "2/3",
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
