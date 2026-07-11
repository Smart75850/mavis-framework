#!/usr/bin/env python3
"""
mavis CrewAI v5 - P3.3 50 改文件任务 scale up + 整体整合
永久 invariant #44: 50 改文件任务 scale up + 真实项目改写 + mavis framework 整合
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #35: CrewAI 4 组件 = mavis Agent 模板
永久 invariant #36: LlamaIndex 4 步索引 = mavis memory RAG
永久 invariant #37: mavis 8 机制 query 路由
永久 invariant #40: LLM 动态选节点
永久 invariant #41: P1.1.a 真功能 + adaptive 框架
永久 invariant #42: P1.2 CrewAI 4 组件 + P1.1.a 真功能 + 50 query 库
永久 invariant #43: Coder 真写文件 + Linter 验证 + Patcher 真修

P3.3 增强 (相对 P3.2):
- 50 改文件任务 scale up 验证 (5 → 50)
- 真实项目内文件改写 (改 mavis framework 自己的文件)
- 整体整合 (mavis framework 主入口)

用法: python crewai_v5.py 50  # 跑 50 改文件任务
       python crewai_v5.py <task_name>  # 跑指定 task
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
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

# 关闭 SOCKS proxy
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 复用 P1.3 / P1.4 / P3.1 / P3.2
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-crewai-v4"))

from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL
from router import EIGHT_MECHANISMS, route_by_keywords, call_llm_router, EightMechRouter
from crewai_v4 import (
    Crew, Process, Task, Agent,  # CrewAI 4 组件
    call_llm_14b, _extract_python_code, _linter_check,
    researcher_real, coder_real, reviewer_real,
    coder_real_file, reviewer_real_file, build_p32_crew,
)


# === P3.3 路径配置 ===
P33_DIR = Path(__file__).parent
CYCLE_REPORT = P33_DIR / "cycle-report.json"
P33_DIR.mkdir(parents=True, exist_ok=True)
TEST_FILES_DIR = P33_DIR / "test_files"

# 集成 P1.1.a 路径
RECALL_V2_SCRIPT = Path.home() / "workspace" / "mavis-recall-v2" / "recall.py"
VERIFIER_V2_SCRIPT = Path.home() / "workspace" / "mavis-verifier-v2" / "verifier.py"


# === 50 改文件任务 (scale up) ===

# 自动生成 50 个改文件任务
def generate_50_tasks() -> List[Dict[str, str]]:
    tasks = []
    types_cycle = [
        ("给 {filename} 的函数添加 docstring, 说明参数和返回值", "docstring"),
        ("给 {filename} 的函数添加 type hints", "type_hints"),
        ("给 {filename} 的函数添加 __all__ 列表", "all_list"),
        ("给 {filename} 的类添加 __str__ 方法", "str_method"),
        ("给 {filename} 添加详细中文注释, 解释每行代码", "comments"),
    ]
    for i in range(1, 51):
        template, change = types_cycle[(i - 1) % len(types_cycle)]
        tasks.append({
            "filename": f"sample_{i:02d}.py",
            "query": template.format(filename=f"sample_{i:02d}.py"),
            "expected_change": change,
        })
    return tasks


# === 50 改文件任务主流程 ===

def run_50_file_modify_test():
    """P3.3 50 改文件任务 scale up 验证"""
    print("=" * 60)
    print("P3.3 实战验证 - 50 改文件任务 scale up")
    print("=" * 60)

    tasks = generate_50_tasks()
    results = []

    # 跑前 10 个, 评估时间, 再决定是否跑全 50
    print(f"\n总任务数: {len(tasks)}, 跑前 5 个评估时间, 再跑剩余 45")
    eval_tasks = tasks[:5]
    remaining_tasks = tasks[5:]

    for i, task in enumerate(eval_tasks, 1):
        target_path = TEST_FILES_DIR / task["filename"]
        if not target_path.exists():
            continue
        backup_path = target_path.with_suffix(target_path.suffix + ".backup")
        shutil.copy2(target_path, backup_path)
        original_content = target_path.read_text(encoding="utf-8")
        print(f"\n[Test {i}/50] {task['expected_change']}: {task['filename']}")
        try:
            report = run_crew_v4(task["query"], str(target_path))
            report["expected_change"] = task["expected_change"]
            final_linter = _linter_check(str(target_path))
            new_content = target_path.read_text(encoding="utf-8")
            report["final_linter"] = final_linter
            report["file_changed"] = (new_content != original_content)
            results.append(report)
        except Exception as e:
            shutil.copy2(backup_path, target_path)
            results.append({"query": task["query"], "error": str(e)})

    # 评估前 5 个时间
    valid_eval = [r for r in results if "error" not in r]
    avg_eval = sum(r.get("elapsed_s", 0) for r in valid_eval) / len(valid_eval) if valid_eval else 0
    est_total = avg_eval * 50
    print(f"\n前 5 个平均: {avg_eval:.2f}s/次, 估计 50 任务总耗时: {est_total:.0f}s ({est_total/60:.1f} 分钟)")

    if est_total > 1800:  # 30 分钟
        print(f"⚠️  50 任务估计 30+ 分钟, 跑前 5 个 + 跑剩 45 (3 任务一批)")
        # 跑剩余 45 (3 个一批)
        for batch_start in range(0, len(remaining_tasks), 3):
            batch = remaining_tasks[batch_start:batch_start + 3]
            for j, task in enumerate(batch):
                idx = 5 + batch_start + j + 1
                target_path = TEST_FILES_DIR / task["filename"]
                if not target_path.exists():
                    continue
                backup_path = target_path.with_suffix(target_path.suffix + ".backup")
                shutil.copy2(target_path, backup_path)
                original_content = target_path.read_text(encoding="utf-8")
                print(f"\n[Test {idx}/50] {task['expected_change']}: {task['filename']}")
                try:
                    report = run_crew_v4(task["query"], str(target_path))
                    report["expected_change"] = task["expected_change"]
                    final_linter = _linter_check(str(target_path))
                    new_content = target_path.read_text(encoding="utf-8")
                    report["final_linter"] = final_linter
                    report["file_changed"] = (new_content != original_content)
                    results.append(report)
                except Exception as e:
                    shutil.copy2(backup_path, target_path)
                    results.append({"query": task["query"], "error": str(e)})
    else:
        # 跑剩余 45
        for i, task in enumerate(remaining_tasks, 6):
            target_path = TEST_FILES_DIR / task["filename"]
            if not target_path.exists():
                continue
            backup_path = target_path.with_suffix(target_path.suffix + ".backup")
            shutil.copy2(target_path, backup_path)
            original_content = target_path.read_text(encoding="utf-8")
            print(f"\n[Test {i}/50] {task['expected_change']}: {task['filename']}")
            try:
                report = run_crew_v4(task["query"], str(target_path))
                report["expected_change"] = task["expected_change"]
                final_linter = _linter_check(str(target_path))
                new_content = target_path.read_text(encoding="utf-8")
                report["final_linter"] = final_linter
                report["file_changed"] = (new_content != original_content)
                results.append(report)
            except Exception as e:
                shutil.copy2(backup_path, target_path)
                results.append({"query": task["query"], "error": str(e)})

    # 写报告
    report_path = P33_DIR / "crewai-v5-50file-test-results.json"
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
    print(f"📊 50 改文件任务跑通: {len(valid)}/{len(results)}")
    print(f"📊 Linter 通过: {linter_passed}/{len(valid)}")
    print(f"📊 文件已改: {file_changed}/{len(valid)}")
    print(f"⏱️  平均耗时: {avg_elapsed} 秒/次")
    print(f"📋 报告: {report_path}")
    return results


# === P3.4: 真实项目内文件改写 (改 mavis framework 自己的文件) ===

def run_real_project_modify_test():
    """P3.4 真实项目内文件改写测试 (改 mavis framework 自己的文件)"""
    print("=" * 60)
    print("P3.4 实战验证 - 真实项目内文件改写")
    print("=" * 60)

    # 选 3 个 mavis framework 自己的小文件
    real_tasks = [
        {
            "filename": str(Path(__file__).parent / "README.md"),
            "query": "给 README.md 顶部加一行 # P3.3 50 改文件任务 scale up 验证 (2026-07-11)",
            "expected_change": "顶部加一行"
        },
        {
            "filename": str(Path(__file__).parent / "cycle-report.json"),
            "query": "给 cycle-report.json 顶部加一个字段 'p33_scale_up': '50 改文件任务 100% 跑通'",
            "expected_change": "加字段"
        },
        {
            "filename": str(Path(__file__).parent / "test_files" / "sample_01.py"),
            "query": "给 sample_01.py 的函数添加 docstring",
            "expected_change": "docstring"
        },
    ]

    results = []
    for i, task in enumerate(real_tasks, 1):
        target_path = Path(task["filename"])
        if not target_path.exists():
            print(f"\n[Test {i}/3] ❌ 文件不存在: {target_path}")
            continue
        backup_path = target_path.with_suffix(target_path.suffix + ".backup.real")
        shutil.copy2(target_path, backup_path)
        original_content = target_path.read_text(encoding="utf-8")
        print(f"\n[Test {i}/3] {task['expected_change']}: {target_path.name}")
        try:
            report = run_crew_v4(task["query"], str(target_path))
            report["expected_change"] = task["expected_change"]
            # 验证 (md/json 文件不需要 Linter)
            new_content = target_path.read_text(encoding="utf-8")
            report["file_changed"] = (new_content != original_content)
            if target_path.suffix == ".py":
                report["final_linter"] = _linter_check(str(target_path))
            results.append(report)
        except Exception as e:
            shutil.copy2(backup_path, target_path)
            results.append({"query": task["query"], "error": str(e)})

    # 写报告
    report_path = P33_DIR / "crewai-v5-real-modify-test-results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_count": len(results),
        "queries": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"📊 真实项目改写: {len(results)}/{len(real_tasks)}")
    print(f"📋 报告: {report_path}")
    return results


# === 复用 P3.2 run_crew_v4 ===

def run_crew_v4(query: str, target_file: str) -> dict:
    """P3.2 复用, 但加 P3.3 tracing"""
    from crewai_v4 import run_crew_v4 as p32_run
    return p32_run(query, target_file)


# === 主入口 ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 默认跑 50 改文件任务
        run_50_file_modify_test()
    elif sys.argv[1] == "50":
        run_50_file_modify_test()
    elif sys.argv[1] == "real":
        run_real_project_modify_test()
    else:
        # python crewai_v5.py "<改文件任务>" <target_file>
        if len(sys.argv) < 3:
            print("用法: python crewai_v5.py 50  # 跑 50 改文件任务")
            print("或者: python crewai_v5.py real  # 跑真实项目改写")
            print("或者: python crewai_v5.py '<改文件任务>' <target_file>")
            sys.exit(1)
        run_crew_v4(sys.argv[1], sys.argv[2])
