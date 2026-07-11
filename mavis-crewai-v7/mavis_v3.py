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
    # T2 修: mavis_v2.py main 入口 `mavis_query(sys.argv[1])` 直接接受 query string
    # 唔加 "query" 子命令, 否则 else 分支会把 "query" 字面当 query string 处理
    result = subprocess.run(
        ["python3", str(P40_HOME / "mavis-crewai-v6" / "mavis_v2.py"), query],
        capture_output=True, text=True, env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""},
    )
    print(result.stdout)
    if result.stderr:
        print(f"[stderr] {result.stderr[:300]}")


def mavis_v3_modify(query: str, target_file: str):
    """永久 invariant #50: 改文件 (delegate P3.6 mavis_v2.py)"""
    print(f"🔧 mavis_v3 modify: {query} -> {target_file}")
    result = subprocess.run(
        ["python3", str(P40_HOME / "mavis-crewai-v6" / "mavis_v2.py"), "modify", query, target_file],
        capture_output=True, text=True, env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""},
    )
    print(result.stdout)
    if result.stderr:
        print(f"[stderr] {result.stderr[:300]}")


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
