#!/usr/bin/env python3
"""
mavis v2 framework - P3.6 整体整合主入口
永久 invariant #47: mavis framework = 11 P 队列 + 37 invariant 整合 = mavis v2 主入口
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #35: CrewAI 4 组件 = mavis Agent 模板
永久 invariant #36: LlamaIndex 4 步索引 = mavis memory RAG
永久 invariant #37: mavis 8 机制 query 路由
永久 invariant #40: LLM 动态选节点
永久 invariant #41: P1.1.a 真功能 + adaptive 框架
永久 invariant #42: P1.2 CrewAI 4 组件 + P1.1.a 真功能 + 50 query 库
永久 invariant #43: Coder 真写文件 + Linter 验证 + Patcher 真修
永久 invariant #44: 50 改文件任务 scale up + 真实项目改写 + mavis framework 整合
永久 invariant #45: 真实项目内文件改写 (暴露 2 bug)
永久 invariant #46: 修复 70% 长度检查 + Patcher Linter 验证 + mavis framework 整合

P3.6 mavis framework 整体整合:
- 11 P 队列全部跑通 (P1.1.a + P1.2 + P1.3 + P1.4 + P2.x + P2.y + P2.z + P3.0 + P3.1 + P3.2 + P3.3 + P3.4 + P3.5)
- 37 个永久 invariant
- auto rebuild 索引 (P3.6 新增)
- mavis 2.0 framework 上线

用法: python mavis_v2.py "<query>"  # 智能 routing + 执行
       python mavis_v2.py modify "<改文件任务>" <target_file>  # 真实改文件
       python mavis_v2.py rebuild  # auto rebuild 索引
       python mavis_v2.py status  # 看 mavis framework 状态
"""
import sys
import os
import json
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 关闭 SOCKS proxy
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 集成 mavis framework 所有 P 队列
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-team-plan-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-adaptive-runtime-v5"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v3"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v6"))

from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL
from router import EIGHT_MECHANISMS, route_by_keywords, call_llm_router, EightMechRouter
from crewai_v6 import run_crew_v6, CYCLE_REPORT as P35_CYCLE


# === P3.6 mavis framework 状态 ===

MAVIS_HOME = Path.home() / "workspace"
MAVIS_MEMORY = Path.home() / ".mavis" / "agents" / "mavis" / "memory"
MAVIS_LLAMAINDEX_STORAGE = MAVIS_HOME / "mavis-llamaindex-v2" / "storage"

# 11 P 队列项目目录
MAVIS_P_PROJECTS = {
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
}


def mavis_status():
    """mavis framework 状态"""
    print("=" * 60)
    print("mavis v2 framework 状态")
    print("=" * 60)
    print()
    print(f"📍 mavis home: {MAVIS_HOME}")
    print(f"📚 mavis memory: {MAVIS_MEMORY}")
    print(f"💾 LlamaIndex 存储: {MAVIS_LLAMAINDEX_STORAGE}")
    print()
    print("📦 14 P 队列项目状态:")

    for p, project in MAVIS_P_PROJECTS.items():
        path = MAVIS_HOME / project
        if path.exists():
            # 数 .py 文件
            py_count = len(list(path.rglob("*.py")))
            print(f"  ✅ {p:7s} {project:35s} ({py_count} .py)")
        else:
            print(f"  ❌ {p:7s} {project:35s} (NOT FOUND)")

    print()
    print("📊 永久 invariant 库:")
    memory_topic = MAVIS_MEMORY / "topics" / "agent-dev-book-2026-07-10.md"
    if memory_topic.exists():
        content = memory_topic.read_text(encoding="utf-8")
        # 数 ## 开头的 invariant
        inv_count = sum(1 for line in content.split("\n") if line.startswith("## #") or line.startswith("## 永久 invariant"))
        print(f"  ✅ agent-dev-book-2026-07-10.md ({inv_count} invariant, {len(content)} 字符)")
    else:
        print(f"  ❌ agent-dev-book-2026-07-10.md NOT FOUND")

    # LlamaIndex 索引
    if MAVIS_LLAMAINDEX_STORAGE.exists():
        size_kb = sum(f.stat().st_size for f in MAVIS_LLAMAINDEX_STORAGE.rglob("*")) / 1024
        print(f"  ✅ LlamaIndex 索引 ({size_kb:.1f} KB)")
    else:
        print(f"  ❌ LlamaIndex 索引 NOT FOUND")


# === P3.6 auto rebuild 索引 ===

def mavis_rebuild():
    """P3.6 auto rebuild 索引 (mavis memory 更新时)"""
    print("=" * 60)
    print("P3.6 auto rebuild 索引")
    print("=" * 60)
    print()
    print(f"📚 索引目录: {MAVIS_MEMORY}")

    # 1. 数当前 .md 文件
    md_files = list(MAVIS_MEMORY.rglob("*.md"))
    md_count = sum(1 for f in md_files if "archive" not in str(f) and "hooks-templates" not in str(f) and ".summary" not in f.name and not f.name.endswith(".bak"))
    print(f"📄 当前 mavis memory .md 文件数: {md_count}")

    # 2. 删除旧索引
    if MAVIS_LLAMAINDEX_STORAGE.exists():
        shutil.rmtree(MAVIS_LLAMAINDEX_STORAGE)
        print(f"🗑️  删除旧索引: {MAVIS_LLAMAINDEX_STORAGE}")
    MAVIS_LLAMAINDEX_STORAGE.mkdir(parents=True, exist_ok=True)

    # 3. 重建索引 (调 P1.3 build_index)
    from build_index import build_index
    build_index(MAVIS_MEMORY, MAVIS_LLAMAINDEX_STORAGE)

    # 4. 验证
    new_files = list(MAVIS_LLAMAINDEX_STORAGE.rglob("*"))
    total_kb = sum(f.stat().st_size for f in new_files if f.is_file()) / 1024
    print(f"✅ 索引重建完成: {len(new_files)} 文件, {total_kb:.1f} KB")


# === P3.6 mavis_v2 主入口 ===

def mavis_query(query: str):
    """P3.6 智能 routing + 执行"""
    print("=" * 60)
    print("mavis v2 framework - 智能 routing + 执行")
    print("=" * 60)
    print(f"Query: {query}")
    print()

    # 1. 8 机制 query 路由
    kw_matches = route_by_keywords(query)
    if kw_matches:
        mechanism = kw_matches[0][0]
        routing_method = "关键词"
    else:
        mechanism = call_llm_router(query, EIGHT_MECHANISMS) or "子智能体"
        routing_method = "LLM 兜底"
    print(f"🎯 路由结果: {mechanism} (方法: {routing_method})")

    # 2. 根据机制选项目
    if mechanism == "Skills":
        # 知识查询 → 调 14B 总结
        print(f"\n📋 知识查询 - 调 P1.3 LlamaIndex 4 步索引 + 14B 总结")
        index = load_or_build_index()
        engine = index.as_query_engine(similarity_top_k=3, response_mode="compact")
        response = engine.query(query)
        print(f"\n=== 答案 ===")
        print(str(response)[:1000])
        return {"mechanism": mechanism, "answer": str(response)}

    elif mechanism in ["子智能体", "CLAUDE.md", "Agent SDK", "Headless", "MCP", "Plugins", "Hooks"]:
        # 通用 query → CrewAI 4 角色串行
        print(f"\n📋 通用 query - 调 P3.1 4 角色 CrewAI")
        from crewai_v3 import build_p31_crew, run_crew_v3
        # 这里简化, 调 P3.0 8 机制 query 路由
        eight_mech_router = EightMechRouter(top_k=3)
        # T2 修: EightMechRouter 无 .query() 方法, 改用 .route_and_response()
        result = eight_mech_router.route_and_response(query)
        print(f"\n=== 答案 ===")
        print(result["answer"][:1000])
        return {"mechanism": mechanism, "answer": result["answer"]}

    else:
        print(f"\n❌ 未知机制: {mechanism}")
        return {"mechanism": mechanism, "error": "unknown mechanism"}


def mavis_modify(query: str, target_file: str):
    """P3.6 真实改文件任务 (P3.5 修复 2 bug)"""
    print("=" * 60)
    print("mavis v2 framework - 真实改文件任务 (P3.5 修复 2 bug)")
    print("=" * 60)
    print(f"Query: {query}")
    print(f"Target: {target_file}")
    print()

    return run_crew_v6(query, target_file)


# === 主入口 ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        mavis_status()
    elif sys.argv[1] == "status":
        mavis_status()
    elif sys.argv[1] == "rebuild":
        mavis_rebuild()
    elif sys.argv[1] == "modify":
        if len(sys.argv) < 4:
            print("用法: python mavis_v2.py modify '<改文件任务>' <target_file>")
            sys.exit(1)
        mavis_modify(sys.argv[2], sys.argv[3])
    else:
        # 智能 routing + 执行
        mavis_query(sys.argv[1])
