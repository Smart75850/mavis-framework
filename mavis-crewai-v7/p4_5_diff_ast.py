#!/usr/bin/env python3
"""
P4.5 3 路径大文件改写 (永久 invariant #60)

解决 P4.4 永久 invariant #59: chunk 拆块 ratio 90% 但 syntax 仍错。

3 路径实战:
- 路径 A: libcst AST 改写 (唔依赖 LLM, 自动结构化, 100% syntax 正确)
- 路径 B: Aider search/replace 块 (LLM 写 + retry 验证, 80%+ 预期)
- 路径 C: 极简 patch (LLM 只能返"加边一行", 服务端 sed 插入, 100% syntax 正确)

目标: 3/3 真实 mavis-framework 文件 (recall.py / router.py / mavis_m3_provider.py) 全部 PASS
vs P4.4 0/3 PASS
"""
import sys
import os
import json
import time
import shutil
import re
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


# ============== 路径 A: libcst AST 改写 ==============

def ast_path_a_add_module_docstring(file_path: Path, docstring: str) -> dict:
    """libcst AST 路径: 加 module docstring (结构化, 100% syntax 正确)"""
    import libcst as cst

    backup = file_path.with_suffix(file_path.suffix + ".p45a.bak")
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    start = time.time()
    try:
        tree = cst.parse_module(original)
        # 检查是否已有 docstring
        if tree.body and isinstance(tree.body[0], cst.SimpleWhitespace):
            first_node = tree.body[1] if len(tree.body) > 1 else None
        else:
            first_node = tree.body[0] if tree.body else None

        # 加 docstring 在文件顶部 (喺所有 import 之前)
        new_docstring_node = cst.SimpleStatementLine(
            body=[cst.Expr(value=cst.SimpleString(f'"""{docstring}"""'))]
        )
        # 喺最前插入
        new_body = [new_docstring_node] + list(tree.body)
        new_tree = tree.with_changes(body=new_body)

        new_code = new_tree.code
        file_path.write_text(new_code, encoding="utf-8")
    except Exception as e:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "path": "A",
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
            "path": "A",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "original_size": original_size,
            "new_size": len(new_code),
            "ratio": round(len(new_code) / original_size, 4),
            "linter": linter,
            "passed": False,
            "elapsed_s": elapsed,
            "error": f"linter failed: {linter}",
        }

    return {
        "path": "A",
        "file": str(file_path.relative_to(FRAMEWORK)),
        "original_size": original_size,
        "new_size": len(new_code),
        "ratio": round(len(new_code) / original_size, 4),
        "linter": "passed",
        "passed": True,
        "elapsed_s": elapsed,
    }


def ast_path_a_add_class_docstring(file_path: Path, class_name: str, docstring: str) -> dict:
    """libcst: 喺指定 class 加 docstring"""
    import libcst as cst

    backup = file_path.with_suffix(file_path.suffix + ".p45a.bak")
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    start = time.time()
    try:
        tree = cst.parse_module(original)

        # 搵 class
        class Found(Exception): pass

        def visit(node):
            if isinstance(node, cst.ClassDef) and node.name.value == class_name:
                # 已有 docstring?
                if not (node.body and isinstance(node.body[0], cst.SimpleStatementLine) and
                        node.body[0].body and isinstance(node.body[0].body[0], cst.Expr) and
                        isinstance(node.body[0].body[0].value, cst.SimpleString)):
                    # 加 docstring
                    new_docstring = cst.SimpleStatementLine(
                        body=[cst.Expr(value=cst.SimpleString(f'"""{docstring}"""'))]
                    )
                    indented_docstring = new_docstring.with_changes(
                        leading_lines=[cst.EmptyLine()]
                    )
                    new_body = [indented_docstring] + list(node.body)
                    raise Found(node.with_changes(body=new_body))
            return True

        try:
            new_tree = tree.visit(cst.CSTVisitor())
            found_node = None
            for node in cst.findall(tree, cst.ClassDef):
                if node.name.value == class_name:
                    found_node = node
                    break

            if found_node is None:
                shutil.copy2(backup, file_path)
                backup.unlink()
                return {
                    "path": "A",
                    "file": str(file_path.relative_to(FRAMEWORK)),
                    "passed": False,
                    "error": f"class {class_name} not found",
                    "elapsed_s": round(time.time() - start, 2),
                }

            # 加 docstring
            new_docstring = cst.SimpleStatementLine(
                body=[cst.Expr(value=cst.SimpleString(f'"""{docstring}"""'))]
            )
            new_body = [new_docstring] + list(found_node.body)
            new_class = found_node.with_changes(body=new_body)

            # 替换
            new_tree = tree.deep_replace(found_node, new_class)
            new_code = new_tree.code
        except Exception as e:
            shutil.copy2(backup, file_path)
            backup.unlink()
            return {
                "path": "A",
                "file": str(file_path.relative_to(FRAMEWORK)),
                "passed": False,
                "error": f"libcst replace error: {e}",
                "elapsed_s": round(time.time() - start, 2),
            }

        file_path.write_text(new_code, encoding="utf-8")
    except Exception as e:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "path": "A",
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
            "path": "A",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "original_size": original_size,
            "new_size": len(new_code),
            "ratio": round(len(new_code) / original_size, 4),
            "linter": linter,
            "passed": False,
            "elapsed_s": elapsed,
        }

    return {
        "path": "A",
        "file": str(file_path.relative_to(FRAMEWORK)),
        "original_size": original_size,
        "new_size": len(new_code),
        "ratio": round(len(new_code) / original_size, 4),
        "linter": "passed",
        "passed": True,
        "elapsed_s": elapsed,
    }


# ============== 路径 B: Aider search/replace 块 ==============

def aider_extract_blocks(text: str) -> list:
    """Aider 风格: 提取 ```search/replace...``` 块"""
    # 格式:
    # ```search/replace
    # <<<<<<< SEARCH
    # 原代码片段
    # =======
    # 新代码片段
    # >>>>>>> REPLACE
    # ```
    blocks = []
    pattern = r"```search/replace\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    for m in matches:
        # 拆 SEARCH / REPLACE
        m_split = re.split(r"={3,}\n", m)
        if len(m_split) == 2:
            search_text = m_split[0].replace("<<<<<<< SEARCH\n", "").strip("\n")
            replace_text = m_split[1].replace(">>>>>>> REPLACE\n", "").strip("\n")
            blocks.append({"search": search_text, "replace": replace_text})
    return blocks


def aider_apply_blocks(content: str, blocks: list) -> tuple:
    """应用 Aider search/replace 块"""
    new_content = content
    applied = 0
    for block in blocks:
        if block["search"] in new_content:
            new_content = new_content.replace(block["search"], block["replace"], 1)
            applied += 1
        else:
            return new_content, applied, f"search not found: {block['search'][:80]}"
    return new_content, applied, None


def aider_path_b(file_path: Path, query: str, max_retry: int = 4) -> dict:
    """Aider 路径: LLM 输出 search/replace 块 + retry 验证"""
    backup = file_path.with_suffix(file_path.suffix + ".p45b.bak")
    if backup.exists():
        shutil.copy2(backup, file_path)  # restore 之前 backup
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    start = time.time()
    system = (
        "你是一个 Python 编程专家。请用 **Aider search/replace 块** 格式修改给定嘅 Python 文件。\n"
        "\n"
        "**格式** (严格遵守):\n"
        "```search/replace\n"
        "<<<<<<< SEARCH\n"
        "原代码片段 (必须 100% 复制, 唔好简化)\n"
        "=======\n"
        "新代码片段\n"
        ">>>>>>> REPLACE\n"
        "```\n"
        "\n"
        "**5 大绝对规则**:\n"
        "1. **SEARCH 必须 100% 复制原文件**, 唔好加 / 唔好删 / 唔好改任何字符\n"
        "2. REPLACE 只改用户要求嘅部分, 其他原代码保留\n"
        "3. 唔好加 ```python``` 块包裹, 用 ```search/replace``` 包裹\n"
        "4. 可以多对 SEARCH/REPLACE (多个块)\n"
        "5. 保持括号/缩进/空行"
    )
    user = (
        f"文件: {file_path.name}\n"
        f"原文件长度: {original_size} 字符\n"
        f"任务: {query}\n\n"
        f"原文件:\n```python\n{original}\n```\n\n"
        f"请输出 Aider search/replace 块。"
    )

    for attempt in range(max_retry):
        new_text = call_llm_m3(
            system=system,
            user=user,
            max_tokens=20000,
            temperature=0.1,
            use_fallback=True,
        )

        blocks = aider_extract_blocks(new_text)
        if not blocks:
            user += "\n\n**Retry**: 你上次返嘅唔系 Aider search/replace 格式, 必须用 ```search/replace\n<<<<<<< SEARCH\n...\n=======\n...\n>>>>>>> REPLACE\n``` 包裹"
            continue

        new_content, applied, error = aider_apply_blocks(original, blocks)
        if error:
            user += f"\n\n**Retry**: {error}, 请 100% 复制原代码, 唔好改任何字符"
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

        # 成功
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

    # 失败
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


# ============== 路径 C: 极简 patch (只允许加) ==============

def simple_path_c_insert_line(file_path: Path, after_pattern: str, new_line: str) -> dict:
    """极简: 喺 after_pattern 后插入 new_line (不依赖 LLM)"""
    backup = file_path.with_suffix(file_path.suffix + ".p45c.bak")
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    start = time.time()
    if after_pattern not in original:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "path": "C",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "passed": False,
            "error": f"pattern not found: {after_pattern[:80]}",
            "elapsed_s": round(time.time() - start, 2),
        }

    # 自动 wrap 成 docstring (处理多行)
    if not new_line.startswith('"""') and not new_line.startswith("'''") and not new_line.startswith("#"):
        # 检查是否 multi-line
        if "\n" in new_line:
            new_line = f'"""\n{new_line}\n"""'
        else:
            new_line = f'"""{new_line}"""'

    # 找 after_pattern 嘅行尾
    idx = original.find(after_pattern)
    line_end = original.find("\n", idx) + 1  # 喺行尾后插入
    new_content = original[:line_end] + new_line + "\n" + original[line_end:]

    file_path.write_text(new_content, encoding="utf-8")

    elapsed = round(time.time() - start, 2)
    linter = _linter_check(str(file_path))
    if "failed" in linter:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "path": "C",
            "file": str(file_path.relative_to(FRAMEWORK)),
            "passed": False,
            "linter": linter,
            "error": f"linter failed: {linter}",
            "elapsed_s": elapsed,
        }

    return {
        "path": "C",
        "file": str(file_path.relative_to(FRAMEWORK)),
        "original_size": original_size,
        "new_size": len(new_content),
        "ratio": round(len(new_content) / original_size, 4),
        "linter": "passed",
        "passed": True,
        "elapsed_s": elapsed,
    }


# ============== 实战 3 路径 ==============

def main():
    print("=" * 70)
    print("P4.5 3 路径大文件改写 (永久 invariant #60)")
    print("=" * 70)
    print()
    print("目标 3 真 mavis-framework 文件:")
    print("  - mavis-recall-v2/recall.py (9976 字符) — 加 module docstring")
    print("  - mavis-8mech-router-v2/router.py (8376 字符) — 加 注释")
    print("  - mavis-crewai-v7/mavis_m3_provider.py (7841 字符) — 加 M3Provider docstring")
    print()

    targets = [
        {
            "file": FRAMEWORK / "mavis-recall-v2" / "recall.py",
            "docstring": "mavis memory recall v2 - 永久 invariant #30 落地\n\n支持中文 jieba 分词 + Hybrid 检索。",
        },
        {
            "file": FRAMEWORK / "mavis-8mech-router-v2" / "router.py",
            "docstring": "mavis 8 机制 query 路由 - 永久 invariant #37",
        },
        {
            "file": FRAMEWORK / "mavis-crewai-v7" / "mavis_m3_provider.py",
            "docstring": "mavis M3 Provider - 永久 invariant #51 落地\n\n云端 LLM, 唔用本地大模型。",
        },
    ]

    results = []
    total_start = time.time()

    for target in targets:
        fp = target["file"]
        ds = target["docstring"]
        print(f"\n[File] {fp.relative_to(FRAMEWORK)}")

        # 路径 A: libcst AST 加 module docstring
        print(f"  [路径 A] libcst AST 加 module docstring...")
        r_a = ast_path_a_add_module_docstring(fp, ds)
        print(f"  路径 A: {'✅' if r_a.get('passed') else '❌'} {r_a.get('elapsed_s', 0)}s, linter={r_a.get('linter', '?')}")
        results.append(r_a)

        # 路径 C: 极简 patch (喺 file 顶部加 docstring) - 唔需要 LLM
        print(f"  [路径 C] 极简 patch (顶部加 docstring)...")
        # restore 原版先
        backup_a = fp.with_suffix(fp.suffix + ".p45a.bak")
        if backup_a.exists():
            shutil.copy2(backup_a, fp)
            backup_a.unlink()
        r_c = simple_path_c_insert_line(fp, after_pattern="", new_line=ds)
        print(f"  路径 C: {'✅' if r_c.get('passed') else '❌'} {r_c.get('elapsed_s', 0)}s, linter={r_c.get('linter', '?')}")
        results.append(r_c)

        # 路径 B: Aider search/replace (用 M3)
        print(f"  [路径 B] Aider search/replace 块 (M3 + retry)...")
        # restore 原版先
        backup_c = fp.with_suffix(fp.suffix + ".p45c.bak")
        if backup_c.exists():
            shutil.copy2(backup_c, fp)
            backup_c.unlink()
        r_b = aider_path_b(fp, query=f"在文件顶部加一段 docstring: {ds[:60]}")
        print(f"  路径 B: {'✅' if r_b.get('passed') else '❌'} {r_b.get('elapsed_s', 0)}s, linter={r_b.get('linter', '?')}")
        results.append(r_b)

        # 还原原版 (下次循环)
        backup_b = fp.with_suffix(fp.suffix + ".p45b.bak")
        if backup_b.exists():
            shutil.copy2(backup_b, fp)
            backup_b.unlink()

    total_elapsed = time.time() - total_start

    # 总结
    print()
    print("=" * 70)
    print("P4.5 3 路径总结果")
    print("=" * 70)
    print(f"{'路径':<8} {'文件':<40} {'状态':<6} {'耗时':<8}")
    print("-" * 70)
    for r in results:
        path = r.get("path", "?")
        file = r.get("file", "?").split("/")[-1]
        status = "✅" if r.get("passed") else "❌"
        elapsed = r.get("elapsed_s", 0)
        print(f"{path:<8} {file:<40} {status:<6} {elapsed:<8.1f}s")
    print("-" * 70)

    a_pass = sum(1 for r in results if r.get("path") == "A" and r.get("passed"))
    b_pass = sum(1 for r in results if r.get("path") == "B" and r.get("passed"))
    c_pass = sum(1 for r in results if r.get("path") == "C" and r.get("passed"))
    print(f"路径 A (libcst AST):     {a_pass}/3")
    print(f"路径 B (Aider diff):     {b_pass}/3")
    print(f"路径 C (极简 patch):     {c_pass}/3")
    print(f"总耗时: {total_elapsed:.1f}s")
    print(f"之前 P4.4 chunk 改写: 0/3 (永久 invariant #59 syntax 错)")
    print()

    # 还原 + 写报告
    for target in targets:
        fp = target["file"]
        for ext in [".p45a.bak", ".p45c.bak", ".p45b.bak"]:
            backup = fp.with_suffix(fp.suffix + ext.replace(".bak", "") + ".bak")
            if backup.exists():
                # restore 原版 (从 .p45a.bak 如果存在, 唔系就用 .p45b.bak, 最后 .p45c.bak)
                if ext == ".p45a.bak":
                    shutil.copy2(backup, fp)
                backup.unlink()
        # 兜底: restore git 版本
        try:
            import subprocess
            subprocess.run(["git", "checkout", "--", str(fp.relative_to(FRAMEWORK))],
                         cwd=FRAMEWORK, capture_output=True)
        except Exception:
            pass

    report_path = Path(__file__).parent / "p4_5_diff_ast_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P4.5 3 路径大文件改写",
        "provider": "MiniMax-M3 (路径 B) + libcst (路径 A) + simple sed (路径 C)",
        "test_count": 9,
        "results": results,
        "summary": {
            "path_a_libcst": f"{a_pass}/3",
            "path_b_aider": f"{b_pass}/3",
            "path_c_simple": f"{c_pass}/3",
            "total_elapsed_s": round(total_elapsed, 2),
        },
        "previous_p4_4": "0/3 PASS (永久 invariant #59 syntax 错)",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
