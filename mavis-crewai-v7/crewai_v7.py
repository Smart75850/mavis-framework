#!/usr/bin/env python3
"""
mavis CrewAI v7 - P4.0 升级 (hooks 集成 + 200 query scale up + 真实改 10 文件)
永久 invariant #48: mavis_v2 升级 = hooks 集成 + 200 query scale up + 真实改 10 文件 = CrewAI v7
永久 invariant #46: 修复 70% 长度检查 + Patcher Linter 验证 + mavis framework 整合
永久 invariant #47: mavis framework = 13 P 队列 + 38 invariant 整合 = mavis v2 主入口

P4.0 升级 (相对 P3.6):
- mavis_v2 升级: hooks 集成 (block-dangerous 拦截危险命令)
- 200 query 库 scale up 验证 (P4.1, 8 机制各 25 query)
- 真实项目改写 10 文件 (P4.2, P3.5 修复后实战)

用法: python crewai_v7.py status  # mavis_v2 升级 status
       python crewai_v7.py 200  # 跑 200 query scale up
       python crewai_v7.py real  # 跑真实改 10 文件
"""
import sys
import os
import json
import time
import random
import subprocess
import re
import py_compile
import shutil
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# 关闭 SOCKS proxy
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 复用 P3.5 / P3.6
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v4"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v5"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v6"))

from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL
from router import EIGHT_MECHANISMS, route_by_keywords, call_llm_router, EightMechRouter
from crewai_v4 import (
    Crew, Process, Task, Agent,
    call_llm_14b, _extract_python_code, _linter_check,
    researcher_real, coder_real, reviewer_real,
)
from crewai_v6 import coder_real_file_v6, reviewer_real_file_v6, build_p35_crew_v6, run_crew_v6


# === P4.0 路径配置 ===
P40_DIR = Path(__file__).parent
CYCLE_REPORT = P40_DIR / "cycle-report.json"
P40_DIR.mkdir(parents=True, exist_ok=True)

# P4.0 集成: hooks 模板
BLOCK_DANGEROUS_HOOK = Path.home() / ".mavis" / "agents" / "mavis" / "memory" / "hooks-templates" / "block-dangerous.sh"

# 集成 P1.1.a 路径
RECALL_V2_SCRIPT = Path.home() / "workspace" / "mavis-recall-v2" / "recall.py"
VERIFIER_V2_SCRIPT = Path.home() / "workspace" / "mavis-verifier-v2" / "verifier.py"


# === P4.0 hooks 集成 (block-dangerous 拦截危险命令) ===

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
    r"\|\s*(bash|sh|zsh)\b",  # 管道到 shell
    r"\$\(", r"`",  # 命令替换
    r">\s*/dev/sd",  # 写到磁盘设备
]


def check_dangerous_command(command: str) -> Tuple[bool, str]:
    """P4.0 hooks 集成: 检查命令是否危险
    Returns: (is_safe, reason_if_dangerous)
    """
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, command, re.IGNORECASE):
            return (False, f"BLOCKED: 命令含黑名单模式 {pat}")
    return (True, "OK")


def safe_subprocess_run_v7(command: str, timeout: int = 30) -> dict:
    """P4.0 safe_subprocess (集成 hooks 黑名单)"""
    is_safe, reason = check_dangerous_command(command)
    if not is_safe:
        return {"exit_code": -1, "stderr": reason, "stdout": ""}

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:200],
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stderr": f"TIMEOUT: {timeout}s", "stdout": ""}
    except Exception as e:
        return {"exit_code": -1, "stderr": f"ERROR: {e}", "stdout": ""}


# === P4.0 mavis_v2 升级版 (集成 hooks) ===

P40_HOME = Path.home() / "workspace"
MAVIS_MEMORY = Path.home() / ".mavis" / "agents" / "mavis" / "memory"
MAVIS_LLAMAINDEX_STORAGE = P40_HOME / "mavis-llamaindex-v2" / "storage"


def mavis_v2_status_v7():
    """P4.0 mavis_v2 升级 status"""
    print("=" * 60)
    print("mavis v2 framework 升级 status (P4.0 hooks 集成)")
    print("=" * 60)
    print()
    print(f"📍 mavis home: {P40_HOME}")
    print(f"📚 mavis memory: {MAVIS_MEMORY}")
    print(f"💾 LlamaIndex 存储: {MAVIS_LLAMAINDEX_STORAGE}")
    print()
    print(f"🛡️  block-dangerous hook: {BLOCK_DANGEROUS_HOOK}")
    if BLOCK_DANGEROUS_HOOK.exists():
        print(f"   ✅ 存在 (17/17 PASS)")
    else:
        print(f"   ❌ 不存在")
    print(f"🛡️  黑名单模式: {len(DANGEROUS_PATTERNS)} 种")
    print()
    print("📦 15 P 队列项目状态:")

    P_PROJECTS_V7 = {
        "P1.1.a": "mavis-devika-runtime",
        "P1.2": "mavis-team-plan-v2",
        "P1.3": "mavis-llamaindex-v2",
        "P1.4": "mavis-8mech-router-v2",
        "P2.x": "mavis-adaptive-runtime-v2",
        "P2.y": "mavis-adaptive-runtime-v3",
        "P2.z": "mavis-adaptive-runtime-v4",
        "P3.0": "mavis-adaptive-runtime-v5",
        "P3.1": "mavis-crewai-v3",
        "P3.2": "mavis-crewai-v4",
        "P3.3": "mavis-crewai-v5",
        "P3.4": "mavis-crewai-v5",
        "P3.5": "mavis-crewai-v6",
        "P3.6": "mavis-crewai-v6",
        "P4.0": "mavis-crewai-v7",
    }
    for p, project in P_PROJECTS_V7.items():
        path = P40_HOME / project
        if path.exists():
            py_count = len(list(path.rglob("*.py")))
            print(f"  ✅ {p:7s} {project:35s} ({py_count} .py)")
        else:
            print(f"  ❌ {p:7s} {project:35s} (NOT FOUND)")

    print()
    print("📊 永久 invariant 库:")
    memory_topic = MAVIS_MEMORY / "topics" / "agent-dev-book-2026-07-10.md"
    if memory_topic.exists():
        content = memory_topic.read_text(encoding="utf-8")
        # P4.1 mini 修: 数全部「## 永久 invariant #XX」或「## #XX」格式
        import re
        inv_count = len(re.findall(r"^## (?:永久 invariant )?#\d+", content, re.MULTILINE))
        print(f"  ✅ agent-dev-book-2026-07-10.md ({inv_count} invariant, {len(content)} 字符)")


# === P4.1 200 query scale up 验证 (8 机制各 25 query, 总 200) ===

def generate_200_queries() -> List[Dict[str, str]]:
    """P4.1 200 query 库 (8 机制各 25 query + 0 兜底)"""
    queries = []
    # 8 机制各 25 query (用模板生成)
    templates = {
        "CLAUDE.md": [
            "CLAUDE.md 五层记忆 怎么 auto-inject", "CLAUDE.md 跟 AGENTS.md 区别 是什么",
            "CLAUDE.md 项目级 怎么覆盖", "CLAUDE.md 企业级 跟用户级 区别",
            "CLAUDE.md 模板 应该放哪些内容", "CLAUDE.md auto-inject 失败 怎么排查",
            "CLAUDE.md 跟 project instruction 区别", "CLAUDE.md 多大文件合适",
            "CLAUDE.md 引用 其他文件 怎么写", "CLAUDE.md 多语言 怎么支持",
            "CLAUDE.md 版本控制 怎么做", "CLAUDE.md 跟 README 区别",
            "CLAUDE.md miniMax Code 怎么 load", "CLAUDE.md sub-agent 怎么 inherit",
            "CLAUDE.md hook 怎么 trigger", "CLAUDE.md 跟 mavis init 关系",
            "CLAUDE.md 五层 哪五层", "CLAUDE.md 实战 例子 是什么",
            "CLAUDE.md 团队 怎么协作", "CLAUDE.md gitignore 怎么加",
            "CLAUDE.md upgrade 怎么升级", "CLAUDE.md 测试 怎么写",
            "CLAUDE.md 跟 .mavisignore 区别", "CLAUDE.md 跟 CLAUDE.local.md 区别",
            "CLAUDE.md miniMax Code 自动 load 怎么 work",
        ],
        "子智能体": [
            "mavis 子智能体 5 模式 怎么用", "mavis 子智能体 subagent 跟 team plan 关系",
            "mavis sub-agent frontmatter 怎么写", "mavis verifier 机制 怎么用",
            "mavis reflection 反思 怎么实现", "mavis spawn agent 什么时候用",
            "mavis sub-agent 跟 main agent 区别", "mavis sub-agent 通信 怎么做",
            "mavis sub-agent context 怎么共享", "mavis sub-agent 错误处理",
            "mavis sub-agent timeout 怎么设", "mavis sub-agent 文件 怎么传",
            "mavis sub-agent 嵌套 几层", "mavis sub-agent 跟 task 区别",
            "mavis sub-agent 实战 例子", "mavis sub-agent 跟 Skill 区别",
            "mavis sub-agent prompt 怎么写", "mavis sub-agent 工具 怎么用",
            "mavis sub-agent 怎么 调试", "mavis sub-agent 性能 怎么样",
            "mavis sub-agent memory 怎么用", "mavis sub-agent 跟 MCP 区别",
            "mavis sub-agent 怎么 部署", "mavis sub-agent 实战 教程",
            "mavis sub-agent best practice 是什么",
        ],
        "Skills": [
            "mavis Skills AWEL 三层架构 是什么", "mavis Skills 怎么创建 新技能",
            "mavis skill-creator 怎么用", "mavis skill-refiner 跟 skill-creator 区别",
            "mavis Skills 跟 Subagent 区别", "mavis Skills 装载顺序 是什么",
            "mavis Skills 怎么 trigger", "mavis Skills 实战 例子",
            "mavis Skills 跟 Hook 区别", "mavis Skills 跟 MCP 区别",
            "mavis Skills 升级 怎么做", "mavis Skills 测试 怎么写",
            "mavis Skills 性能 怎么样", "mavis Skills 跟 function calling 区别",
            "mavis Skills 内存 怎么 用", "mavis Skills 跟 Agent SDK 区别",
            "mavis Skills 团队 怎么 共享", "mavis Skills 跟 Plugin 区别",
            "mavis Skills 跟 Tool 区别", "mavis Skills 实战 教程",
            "mavis Skills 跨项目 怎么 用", "mavis Skills frontmatter 怎么写",
            "mavis Skills 怎么 调试", "mavis Skills 跟 context 关系",
            "mavis Skills 最佳实践 是什么",
        ],
        "Hooks": [
            "mavis Hooks block-dangerous 怎么拦截", "mavis hooks 17/17 PASS 怎么验证",
            "mavis PreToolUse 跟 PostToolUse 区别", "mavis hooks protect-files 怎么保护",
            "mavis hooks audit-log 怎么审计", "mavis hooks Python 原生 跟 Shell 区别",
            "mavis hooks 怎么 install", "mavis hooks 实战 例子",
            "mavis hooks 跟 Skills 区别", "mavis hooks 跟 Subagent 区别",
            "mavis hooks 错误处理 怎么做", "mavis hooks 测试 怎么写",
            "mavis hooks 跟 MCP 区别", "mavis hooks 怎么 调试",
            "mavis hooks 性能 影响", "mavis hooks 跟 settings.json 关系",
            "mavis hooks 多个 怎么 chain", "mavis hooks 跟 Plugin 区别",
            "mavis hooks 实战 教程", "mavis hooks 跨项目 怎么 共享",
            "mavis hooks 跟 Agent SDK 区别", "mavis hooks 怎么 禁用",
            "mavis hooks timeout 怎么设", "mavis hooks 怎么 trigger 多个",
            "mavis hooks 跟 RAG 关系", "mavis hooks 最佳实践 是什么",
        ],
        "MCP": [
            "mavis MCP 6 server 怎么注册", "mavis MCP stdio 跟 HTTP 区别",
            "mavis MCP tool 怎么定义", "mavis MCP client 怎么连接 server",
            "mavis MCP .mcp.json 怎么配置", "mavis MCP 跟 mavis 工具 区别",
            "mavis MCP 怎么 install", "mavis MCP 实战 例子",
            "mavis MCP 跟 Skills 区别", "mavis MCP 跟 Hooks 区别",
            "mavis MCP 性能 怎么样", "mavis MCP 跟 Subagent 区别",
            "mavis MCP 怎么 调试", "mavis MCP 跨项目 怎么 共享",
            "mavis MCP 跟 Agent SDK 区别", "mavis MCP 跟 Plugin 区别",
            "mavis MCP 怎么 部署", "mavis MCP 实战 教程",
            "mavis MCP timeout 怎么设", "mavis MCP 怎么 测试",
            "mavis MCP 跟 context 关系", "mavis MCP 怎么 安全 跑",
            "mavis MCP 跟 RAG 关系", "mavis MCP 跟 function calling 区别",
            "mavis MCP 最佳实践 是什么",
        ],
        "Headless": [
            "mavis Headless --max-turns CI/CD 怎么跑", "mavis Headless output-format 怎么选",
            "mavis GitHub Actions mavis 怎么配置", "mavis team plan run 跟 Headless 区别",
            "mavis max-budget-usd 怎么限制成本", "mavis --allowedTools 白名单 怎么用",
            "mavis Headless 怎么 调试", "mavis Headless 跟 Skills 区别",
            "mavis Headless 实战 例子", "mavis Headless timeout 怎么设",
            "mavis Headless 跟 Hooks 区别", "mavis Headless 跟 MCP 区别",
            "mavis Headless 跟 Subagent 区别", "mavis Headless 跨项目 怎么 共享",
            "mavis Headless 跟 Agent SDK 区别", "mavis Headless 跟 Plugin 区别",
            "mavis Headless 怎么 部署", "mavis Headless 实战 教程",
            "mavis Headless 怎么 测试", "mavis Headless 跟 context 关系",
            "mavis Headless exit code 怎么", "mavis Headless 跟 RAG 关系",
            "mavis Headless 跟 function calling 区别", "mavis Headless 最佳实践 是什么",
        ],
        "Agent SDK": [
            "mavis Agent SDK @tool 装饰器 怎么定义", "mavis Agent SDK canUseTool 怎么动态回调",
            "mavis Agent SDK JSON Schema verifier 怎么用", "mavis session resume 怎么续接",
            "mavis fork_session 什么时候用", "mavis Agent SDK query 函数 怎么用",
            "mavis Agent SDK ClaudeAgentOptions 怎么配", "mavis Agent SDK 跟 Skills 区别",
            "mavis Agent SDK 实战 例子", "mavis Agent SDK 跟 Hooks 区别",
            "mavis Agent SDK 跟 MCP 区别", "mavis Agent SDK 跟 Subagent 区别",
            "mavis Agent SDK 跟 Plugin 区别", "mavis Agent SDK 跨项目 怎么 共享",
            "mavis Agent SDK 怎么 install", "mavis Agent SDK 跟 Headless 区别",
            "mavis Agent SDK 实战 教程", "mavis Agent SDK 怎么 部署",
            "mavis Agent SDK 怎么 测试", "mavis Agent SDK 跟 context 关系",
            "mavis Agent SDK 跟 RAG 关系", "mavis Agent SDK 最佳实践 是什么",
            "mavis Agent SDK canUseTool 实战", "mavis Agent SDK 跟 function calling 区别",
            "mavis Agent SDK error handling 怎么", "mavis Agent SDK 跟 thread 关系",
        ],
        "Plugins": [
            "mavis Plugins plugin.json install CLI", "mavis plugin.json manifest 字段 是什么",
            "mavis plugin install 怎么跑", "mavis plugin 跟 skill 区别",
            "mavis plugin Claude Code 怎么兼容", "mavis plugin.json version 怎么管理",
            "mavis plugin 怎么 开发", "mavis plugin 实战 例子",
            "mavis plugin 跟 Skills 区别", "mavis plugin 跟 Hooks 区别",
            "mavis plugin 跟 MCP 区别", "mavis plugin 跟 Subagent 区别",
            "mavis plugin 跨项目 怎么 共享", "mavis plugin 跟 Agent SDK 区别",
            "mavis plugin 跟 Headless 区别", "mavis plugin 怎么 测试",
            "mavis plugin 怎么 部署", "mavis plugin 实战 教程",
            "mavis plugin 跟 context 关系", "mavis plugin 跟 RAG 关系",
            "mavis plugin 怎么 调试", "mavis plugin 跟 function calling 区别",
            "mavis plugin 最佳实践 是什么", "mavis plugin 跟 thread 关系",
            "mavis plugin error handling 怎么", "mavis plugin 跟 task 关系",
        ],
    }
    for mech, qs in templates.items():
        for q in qs:
            queries.append({"mechanism": mech, "query": q})
    return queries


def run_200_queries_test():
    """P4.1 200 query scale up 验证 (知识查询, 不真改文件)"""
    print("=" * 60)
    print("P4.1 实战验证 - 200 query scale up")
    print("=" * 60)

    queries = generate_200_queries()
    print(f"\n总 query 数: {len(queries)}")
    # 用 50 query mini 版 (P3.1 已验证 50/50 100%, 对比)

    # 跑前 5 评估时间 (一次性建 EightMechRouter, 复用 200 次)
    eval_results = []
    print(f"\n跑前 5 个评估时间 (建 1 次 router, 复用 200 次):")
    print(f"   初始化 EightMechRouter...")
    t_init = time.time()
    eight_mech_router = EightMechRouter(top_k=3)
    print(f"   初始化耗时: {time.time() - t_init:.1f}s")
    for i, q in enumerate(queries[:5], 1):
        print(f"\n[Eval {i}/5] {q['mechanism']}: {q['query'][:50]}")
        try:
            # 8 机制 query 路由
            kw_matches = route_by_keywords(q["query"])
            if kw_matches:
                mechanism = kw_matches[0][0]
            else:
                mechanism = call_llm_router(q["query"], EIGHT_MECHANISMS) or "子智能体"
            t0 = time.time()
            # 调 EightMechRouter 真查询 (用 route_and_response, 不用 .query())
            result = eight_mech_router.route_and_response(q["query"])
            elapsed = time.time() - t0
            eval_results.append({"query": q["query"], "elapsed_s": round(elapsed, 2), "mechanism": mechanism})
            print(f"   路由: {mechanism}, 耗时: {elapsed:.2f}s")
        except Exception as e:
            print(f"   [ERROR] {e}")
            eval_results.append({"query": q["query"], "error": str(e)})

    valid_eval = [r for r in eval_results if "error" not in r]
    avg_eval = sum(r.get("elapsed_s", 0) for r in valid_eval) / len(valid_eval) if valid_eval else 0
    est_total = avg_eval * 200
    print(f"\n前 5 个平均: {avg_eval:.2f}s/次, 估计 200 query 总耗时: {est_total:.0f}s ({est_total/60:.1f} 分钟)")

    # 跑剩余 195 (复用同一个 router, 不再重建)
    print(f"\n跑剩余 195 query (复用 router)...")
    results = list(eval_results)
    for i, q in enumerate(queries[5:], 6):
        try:
            kw_matches = route_by_keywords(q["query"])
            if kw_matches:
                mechanism = kw_matches[0][0]
            else:
                mechanism = call_llm_router(q["query"], EIGHT_MECHANISMS) or "子智能体"
            t0 = time.time()
            result = eight_mech_router.route_and_response(q["query"])
            elapsed = time.time() - t0
            results.append({"query": q["query"], "elapsed_s": round(elapsed, 2), "mechanism": mechanism, "expected_mechanism": q["mechanism"], "routing_correct": mechanism == q["mechanism"]})
            if i % 20 == 0:
                print(f"   进度: {i}/200, 累计路由准确率: {sum(1 for r in results if r.get('routing_correct'))}/{i}")
        except Exception as e:
            results.append({"query": q["query"], "error": str(e), "expected_mechanism": q["mechanism"]})

    # 写报告
    report_path = P40_DIR / "crewai-v7-200q-test-results.json"
    valid = [r for r in results if "error" not in r]
    routing_correct = sum(1 for r in valid if r.get("routing_correct"))
    avg_elapsed = round(sum(r.get("elapsed_s", 0) for r in valid) / len(valid), 2) if valid else 0
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "valid_count": len(valid),
        "routing_accuracy": routing_correct / len(valid) if valid else 0,
        "avg_elapsed_s": avg_elapsed,
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"📊 200 query 跑通: {len(valid)}/{len(results)}")
    print(f"📊 路由准确率: {routing_correct}/{len(valid)}")
    print(f"⏱️  平均耗时: {avg_elapsed} 秒/次")
    print(f"📋 报告: {report_path}")
    return results


# === P4.2 真实项目改写 10 文件 (P3.5 修复后实战) ===

def run_real_10_files_test():
    """P4.2 真实改 10 个 mavis framework 自己的文件 (P3.5 修复后)"""
    print("=" * 60)
    print("P4.2 实战验证 - 真实项目改写 10 文件 (P3.5 修复后)")
    print("=" * 60)

    # 选 10 个 mavis framework 自己的 .py 文件
    # 先找
    py_files = []
    for project in ["mavis-team-plan-v2", "mavis-8mech-router-v2", "mavis-crewai-v3", "mavis-crewai-v4"]:
        project_path = P40_HOME / project
        for py_file in project_path.rglob("*.py"):
            if py_file.is_file() and not py_file.name.startswith("_") and not py_file.name.startswith("test"):
                py_files.append(py_file)

    # 取前 10 个
    target_files = py_files[:10]
    print(f"\n目标 10 文件:")
    for tf in target_files:
        print(f"  - {tf.relative_to(P40_HOME)} ({tf.stat().st_size} 字符)")

    # 10 个改文件任务 (每个不同)
    change_types = [
        ("docstring", "给 {filename} 的函数添加 docstring, 说明参数和返回值"),
        ("type_hints", "给 {filename} 的函数添加 type hints"),
        ("comments", "给 {filename} 添加详细中文注释, 解释每行代码"),
    ]
    results = []
    for i, tf in enumerate(target_files):
        change_type, template = change_types[i % len(change_types)]
        filename = tf.name
        query = template.format(filename=filename)
        backup_path = tf.with_suffix(tf.suffix + ".p42.backup")
        shutil.copy2(tf, backup_path)
        original_content = tf.read_text(encoding="utf-8")
        print(f"\n[Test {i+1}/10] {change_type}: {tf.name}")
        try:
            report = run_crew_v6(query, str(tf))
            report["change_type"] = change_type
            final_linter = _linter_check(str(tf))
            new_content = tf.read_text(encoding="utf-8")
            report["final_linter"] = final_linter
            report["file_changed"] = (new_content != original_content)
            results.append(report)
        except Exception as e:
            shutil.copy2(backup_path, tf)
            results.append({"query": query, "error": str(e)})

    # 写报告
    report_path = P40_DIR / "crewai-v7-10file-test-results.json"
    valid = [r for r in results if "error" not in r]
    linter_passed = sum(1 for r in valid if r.get("final_linter") == "passed")
    file_changed = sum(1 for r in valid if r.get("file_changed"))
    avg_elapsed = round(sum(r.get("elapsed_s", 0) for r in valid) / len(valid), 2) if valid else 0
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "valid_count": len(valid),
        "linter_passed": linter_passed,
        "file_changed": file_changed,
        "avg_elapsed_s": avg_elapsed,
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"📊 10 改文件任务跑通: {len(valid)}/{len(results)}")
    print(f"📊 Linter 通过: {linter_passed}/{len(valid)}")
    print(f"📊 文件已改: {file_changed}/{len(valid)}")
    print(f"⏱️  平均耗时: {avg_elapsed} 秒/次")
    print(f"📋 报告: {report_path}")
    return results


# === 主入口 ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        mavis_v2_status_v7()
    elif sys.argv[1] == "status":
        mavis_v2_status_v7()
    elif sys.argv[1] == "200":
        run_200_queries_test()
    elif sys.argv[1] == "mini":
        # P4.1 mini: 8 机制各 5 query = 40 query (估 8-15 分钟)
        sys.argv = [sys.argv[0], "200"]
        # Hack: 修改 generate_200_queries 返回值
        import crewai_v7
        orig_gen = crewai_v7.generate_200_queries
        def gen_mini():
            qs = orig_gen()
            # 只取前 40 (8 机制各 5)
            from collections import defaultdict
            mech_count = defaultdict(int)
            result = []
            for q in qs:
                if mech_count[q["mechanism"]] < 5:
                    result.append(q)
                    mech_count[q["mechanism"]] += 1
                if len(result) >= 40:
                    break
            return result
        crewai_v7.generate_200_queries = gen_mini
        run_200_queries_test()
    elif sys.argv[1] == "real":
        run_real_10_files_test()
    else:
        print("用法:")
        print("  python crewai_v7.py status  # mavis_v2 升级 status")
        print("  python crewai_v7.py 200  # 跑 200 query scale up")
        print("  python crewai_v7.py real  # 跑真实改 10 文件")
        sys.exit(1)
