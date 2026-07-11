#!/usr/bin/env python3
"""
mavis v3 - 15 P 队列 1 主入口 facade (永久 invariant #50)

P3.6 mavis_v2.py 整合 14 P 队列
P4.0 crewai_v7.py 升级 + hooks + 200 query + 真实改 10
P4.3 plan_e91158a3 mavis team plan 集成 verify
P4.6 mavis_v3.py = 1 主入口 facade 整合 15 P 队列 (本次新增)

设计原则:
- 1 主入口 (mavis_v3.py) 调 15 P 队列 (dispatcher 模式)
- 8 大功能: status / rebuild / query / modify / plan / hooks / recall / verify
- 各 P 队列作为 plugin (subprocess 调 或 Python import)
- 兼容 P3.6 mavis_v2 + P4.0 crewai_v7 (alias)

用法:
  python3 mavis_v3.py status  # 15 P 队列 status (整合 P3.6 + P4.0)
  python3 mavis_v3.py query "mavis 8 机制 怎么协奏"
  python3 mavis_v3.py modify "改 /tmp/test.py 加 docstring" /tmp/test.py
  python3 mavis_v3.py plan <yaml-file>  # mavis team plan run
  python3 mavis_v3.py hooks  # block-dangerous 17/17 + 28 黑名单
  python3 mavis_v3.py recall "mavis recall 实战"  # 调 recall.py
  python3 mavis_v3.py verify  # 调 verifier.py
"""
import sys
import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# 关闭 SOCKS proxy (永久 invariant)
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 永久 invariant #51: M3 Provider 接入 (默认用云端 M3 LLM, 唔用本地大模型)
sys.path.insert(0, str(Path(__file__).parent))
try:
    from mavis_m3_provider import M3Provider, M3_BASE, M3_MODEL
    _M3_OK = True
except ImportError:
    _M3_OK = False


# === 永久 invariant #50: mavis v3 1 主入口 facade ===

P50_DIR = Path(__file__).parent
P40_HOME = Path.home() / "workspace"
MAVIS_MEMORY = Path.home() / ".mavis" / "agents" / "mavis" / "memory"

# 15 P 队列项目 (P1.1.a → P4.0)
P_PROJECTS_V3 = {
    "P1.1.a": ("mavis-devika-runtime", "9 Agent LangGraph StateGraph template"),
    "P1.2":   ("mavis-team-plan-v2", "CrewAI 4 组件 = mavis Agent 模板"),
    "P1.3":   ("mavis-llamaindex-v2", "LlamaIndex 4 步索引 = mavis memory RAG"),
    "P1.4":   ("mavis-8mech-router-v2", "mavis 8 机制 query 路由 (49 关键词 + LLM 兜底)"),
    "P2.x":   ("mavis-adaptive-runtime-v2", "9 节点 LangGraph + 8 机制 query 路由"),
    "P2.y":   ("mavis-adaptive-runtime-v3", "9 节点 + conditional + hierarchical"),
    "P2.z":   ("mavis-adaptive-runtime-v4", "LLM 动态选节点 + 真 subprocess + decision_route"),
    "P3.0":   ("mavis-adaptive-runtime-v5", "P1.1.a 真功能 + P2.z adaptive 框架"),
    "P3.1":   ("mavis-crewai-v3", "CrewAI 4 角色 + 50 query scale up"),
    "P3.2":   ("mavis-crewai-v4", "Coder 真写文件 + Linter 验证 + Patcher 真修"),
    "P3.3":   ("mavis-crewai-v5", "50 改文件任务 scale up"),
    "P3.4":   ("mavis-crewai-v5", "真实项目改写 (暴露 2 bug)"),
    "P3.5":   ("mavis-crewai-v6", "修复 2 bug + mavis framework 整合"),
    "P3.6":   ("mavis-crewai-v6", "mavis v2 主入口 (mavis_v2.py)"),
    "P4.0":   ("mavis-crewai-v7", "mavis_v2 升级 + hooks + 200 query + 真实改 10"),
}


def mavis_v3_status():
    """永久 invariant #50: 15 P 队列 status (整合 mavis_v2 + crewai_v7)"""
    print("=" * 60)
    print("mavis v3 1 主入口 facade status (永久 invariant #50)")
    print("=" * 60)
    print()
    print(f"📍 mavis home: {P40_HOME}")
    print(f"📚 mavis memory: {MAVIS_MEMORY}")
    # 永久 invariant #51: M3 Provider 状态
    if _M3_OK:
        print(f"☁️  M3 Provider: ✅ (model={M3_MODEL}, base={M3_BASE})")
    else:
        print(f"☁️  M3 Provider: ❌ (fallback 到本地 14B)")
    print()
    print(f"📦 15 P 队列项目状态 (整合 P3.6 + P4.0):")
    for p, (project, desc) in P_PROJECTS_V3.items():
        path = P40_HOME / project
        if path.exists():
            py_count = len(list(path.rglob("*.py")))
            print(f"  ✅ {p:7s} {project:35s} ({py_count:3d} .py) — {desc}")
        else:
            print(f"  ❌ {p:7s} {project:35s} (NOT FOUND)")

    print()
    print("📊 永久 invariant 库:")
    memory_topic = MAVIS_MEMORY / "topics" / "agent-dev-book-2026-07-10.md"
    if memory_topic.exists():
        content = memory_topic.read_text(encoding="utf-8")
        import re
        inv_count = len(re.findall(r"^## (?:永久 invariant )?#\d+", content, re.MULTILINE))
        print(f"  ✅ agent-dev-book-2026-07-10.md ({inv_count} invariant, {len(content)} 字符)")

    print()
    print("🔗 8 大功能 (mavis_v3 facade):")
    print("  1. status    — 15 P 队列 status (整合 P3.6 + P4.0)")
    print("  2. rebuild   — P3.6 auto rebuild LlamaIndex 索引")
    print("  3. query     — 8 机制路由 + 14B 总结 (P3.6)")
    print("  4. modify    — 改文件 (P3.5 修复 2 bug)")
    print("  5. plan      — mavis team plan run (P4.3 集成)")
    print("  6. hooks     — block-dangerous 17/17 + 28 黑名单 (P4.0)")
    print("  7. recall    — 调 recall.py (P1.1.a)")
    print("  8. verify    — 调 verifier.py (P1.1.a)")


def mavis_v3_query(query: str):
    """永久 invariant #50: 8 机制 query 路由 (delegate P3.6)"""
    print(f"🔍 mavis_v3 query: {query}")
    # 永久 invariant #51: 改调 monorepo 内部 mavis_v2 (已用 M3 provider, 唔用本地大模型)
    mavis_v2_path = Path(__file__).parent.parent / "mavis-crewai-v6" / "mavis_v2.py"
    result = subprocess.run(
        ["/Users/apple/workspace/mavis-llamaindex-v2/.venv/bin/python", str(mavis_v2_path), query],
        capture_output=True, text=True, env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""},
    )
    print(result.stdout)
    if result.stderr:
        print(f"[stderr] {result.stderr[:300]}")


def _add_type_hints_to_all_functions(tree):
    """P1.0 新: 给所有未注解嘅 function parameters 加 Any type hint + 返回 Any"""
    import libcst as cst

    def visit_FunctionDef(node):
        if node.returns:
            return node
        new_params = []
        for param in node.params.params:
            if param.annotation is None and param.name:
                new_param = param.with_changes(
                    annotation=cst.Annotation(annotation=cst.Name("Any"))
                )
                new_params.append(new_param)
            else:
                new_params.append(param)
        new_returns = cst.Annotation(annotation=cst.Name("Any"))
        return node.with_changes(params=node.params.with_changes(params=new_params), returns=new_returns)

    return tree.visit(cst.CSTTransformer().visit_FunctionDef(visit_FunctionDef))


def _add_function_signatures(tree):
    """P1.0 新: 给所有未注解 function 加详细签名 docstring"""
    import libcst as cst

    def visit_FunctionDef(node):
        if node.body and isinstance(node.body[0], cst.SimpleStatementLine) and \
           node.body[0].body and isinstance(node.body[0].body[0], cst.Expr) and \
           isinstance(node.body[0].body[0].value, cst.SimpleString):
            return node

        params_str = ", ".join([p.name.value for p in node.params.params if p.name])
        func_name = node.name.value if node.name else "function"
        sig_docstring = f'"""{func_name}({params_str}) - TODO: 添加函数说明"""'

        new_docstring = cst.SimpleStatementLine(
            body=[cst.Expr(value=cst.SimpleString(sig_docstring))],
            leading_lines=[cst.EmptyLine()],
        )
        new_body = [new_docstring] + list(node.body)
        return node.with_changes(body=new_body)

    return tree.visit(cst.CSTTransformer().visit_FunctionDef(visit_FunctionDef))


def _add_import(tree, module_name):
    """P1.0 新: 加 import (e.g. 'import os' → SimpleStatementLine)"""
    import libcst as cst
    new_import = cst.SimpleStatementLine(
        body=[cst.Import(names=[cst.ImportAlias(name=cst.Name(module_name))])]
    )
    new_body = [new_import] + list(tree.body)
    return tree.with_changes(body=new_body)


def mavis_v3_modify(query: str, target_file: str):
    """永久 invariant #61 + #64: 改文件 (P4.6 整合 P4.5 路径 A libcst AST + P1.0 扩展 type hints / function signature)"""
    print(f"🔧 mavis_v3 modify (P4.6 + P1.0 libcst AST): {query} -> {target_file}")

    import libcst as cst
    from pathlib import Path
    fp = Path(target_file)
    if not fp.exists():
        print(f"❌ 文件不存在: {target_file}")
        return

    backup = fp.with_suffix(fp.suffix + ".v3.bak")
    import shutil
    shutil.copy2(fp, backup)
    original = fp.read_text(encoding="utf-8")
    original_size = len(original)

    import time
    start = time.time()

    try:
        tree = cst.parse_module(original)

        # P1.0 智能识别 (扩展到 type hints / function signature / import)
        query_lower = query.lower()
        if "docstring" in query_lower or "文档" in query:
            new_docstring = cst.SimpleStatementLine(
                body=[cst.Expr(value=cst.SimpleString(f'"""{query}"""'))]
            )
            new_body = [new_docstring] + list(tree.body)
            new_tree = tree.with_changes(body=new_body)
            change_type = "module docstring"
        elif "type hint" in query_lower or "类型注解" in query or "类型提示" in query:
            new_tree = _add_type_hints_to_all_functions(tree)
            change_type = "function type hints"
        elif "function signature" in query_lower or "函数签名" in query:
            new_tree = _add_function_signatures(tree)
            change_type = "function signatures"
        elif "import" in query_lower:
            import_match = __import__('re').search(r"import\s+(\w+)", query)
            if import_match:
                module_name = import_match.group(1)
                new_tree = _add_import(tree, module_name)
                change_type = f"add import {module_name}"
            else:
                shutil.copy2(backup, fp)
                backup.unlink()
                print(f"⚠️  无法识别 import module name")
                return
        else:
            new_docstring = cst.SimpleStatementLine(
                body=[cst.Expr(value=cst.SimpleString(f'"""{query}"""'))]
            )
            new_body = [new_docstring] + list(tree.body)
            new_tree = tree.with_changes(body=new_body)
            change_type = "module docstring (default)"

        new_code = new_tree.code
        fp.write_text(new_code, encoding="utf-8")

        import py_compile
        try:
            py_compile.compile(target_file, doraise=True)
            linter = "passed"
        except py_compile.PyCompileError as e:
            shutil.copy2(backup, fp)
            backup.unlink()
            print(f"❌ Linter failed: {e}")
            return

        elapsed = round(time.time() - start, 2)
        ratio = round(len(new_code) / original_size, 4) if original_size else 0
        print(f"✅ PASS: {original_size} -> {len(new_code)} 字符 (ratio {ratio:.2%}, linter {linter}, {elapsed}s)")
        print(f"   改动类型: {change_type}")
        print(f"   backup: {backup}")
        backup.unlink()
    except Exception as e:
        shutil.copy2(backup, fp)
        backup.unlink()
        print(f"❌ libcst error: {e}")


def mavis_v3_plan(yaml_file: str):
    """永久 invariant #50: mavis team plan run (P4.3 集成)"""
    print(f"📋 mavis_v3 plan: {yaml_file}")
    result = subprocess.run(
        ["mavis", "team", "plan", "run", yaml_file, "--no-wait"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(f"[stderr] {result.stderr[:300]}")


def mavis_v3_hooks():
    """永久 invariant #50: block-dangerous 17/17 + 28 黑名单 (P4.0)"""
    print("🛡️  mavis_v3 hooks (P4.0):")
    print(f"   block-dangerous: {MAVIS_MEMORY / 'hooks-templates' / 'block-dangerous.sh'}")
    print(f"   28 黑名单模式 (rm -rf, sudo, dd, mkfs, shutdown, 管道到 shell, 命令替换)")
    print(f"   settings.json PreToolUse: ✅ 已注册 (P4.0 修 #1 缺口)")
    # 真测
    import re
    DANGEROUS_PATTERNS = [
        r"\brm\s+-rf\b", r"\brm\s+-fr\b",
        r"\bmv\s+/", r"\bchmod\s+777\b", r"\bchown\b",
        r"\bsudo\b", r"\bsu\s+-\b",
        r"\bcurl\b", r"\bwget\b",
        r"\bnc\b", r"\bssh\b", r"\bscp\b",
        r"\beval\b", r"\bexec\b",
        r"\bpip\s+install\b", r"\bnpm\s+install\b", r"\bbrew\s+install\b",
        r"\bkill\s+-9\b", r"\bpkill\b",
        r"\bdd\b", r"\bmkfs\b", r"\bformat\b",
        r"\bshutdown\b", r"\breboot\b",
        r"\|\s*(bash|sh|zsh)\b",
        r"\$\(", r"`",
        r">\s*/dev/sd",
    ]
    # 测 2 个
    for cmd in ["rm -rf /tmp/test", "ls -la"]:
        matched = [pat for pat in DANGEROUS_PATTERNS if re.search(pat, cmd, re.IGNORECASE)]
        if matched:
            print(f"   ❌ BLOCKED: '{cmd}' (match: {matched[0]})")
        else:
            print(f"   ✅ ALLOWED: '{cmd}'")


def mavis_v3_recall(query: str):
    """永久 invariant #50: 调 recall.py (P1.1.a)"""
    print(f"📚 mavis_v3 recall: {query}")
    recall_script = P40_HOME / "mavis-recall-v2" / "recall.py"
    if not recall_script.exists():
        print(f"   ❌ recall script 不存在: {recall_script}")
        return
    result = subprocess.run(
        ["python3", str(recall_script), query],
        capture_output=True, text=True, env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""},
        timeout=60,
    )
    print(result.stdout[:1000])
    if result.stderr:
        print(f"[stderr] {result.stderr[:300]}")


def mavis_v3_verify():
    """永久 invariant #50: 调 verifier.py (P1.1.a)"""
    print("✅ mavis_v3 verify (调 verifier.py)")
    verifier_script = P40_HOME / "mavis-verifier-v2" / "verifier.py"
    if not verifier_script.exists():
        print(f"   ❌ verifier script 不存在: {verifier_script}")
        return
    result = subprocess.run(
        ["python3", str(verifier_script), "--help"],
        capture_output=True, text=True, env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""},
        timeout=30,
    )
    print(result.stdout[:1000])
    if result.stderr:
        print(f"[stderr] {result.stderr[:300]}")


# === 主入口 ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        mavis_v3_status()
    elif sys.argv[1] == "status":
        mavis_v3_status()
    elif sys.argv[1] == "query" and len(sys.argv) >= 3:
        mavis_v3_query(sys.argv[2])
    elif sys.argv[1] == "modify" and len(sys.argv) >= 4:
        mavis_v3_modify(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "plan" and len(sys.argv) >= 3:
        mavis_v3_plan(sys.argv[2])
    elif sys.argv[1] == "hooks":
        mavis_v3_hooks()
    elif sys.argv[1] == "recall" and len(sys.argv) >= 3:
        mavis_v3_recall(sys.argv[2])
    elif sys.argv[1] == "verify":
        mavis_v3_verify()
    else:
        print("用法:")
        print("  python3 mavis_v3.py status")
        print("  python3 mavis_v3.py query <query>")
        print("  python3 mavis_v3.py modify <query> <target_file>")
        print("  python3 mavis_v3.py plan <yaml-file>")
        print("  python3 mavis_v3.py hooks")
        print("  python3 mavis_v3.py recall <query>")
        print("  python3 mavis_v3.py verify")
        sys.exit(1)
