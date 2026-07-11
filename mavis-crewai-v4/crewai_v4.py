#!/usr/bin/env python3
"""
mavis CrewAI v4 - P3.2 真实改文件任务
永久 invariant #43: Coder 真写文件 + Linter 验证 + Patcher 真修 = mavis CrewAI v4
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #35: CrewAI 4 组件 = mavis Agent 模板
永久 invariant #36: LlamaIndex 4 步索引 = mavis memory RAG
永久 invariant #37: mavis 8 机制 query 路由
永久 invariant #40: LLM 动态选节点
永久 invariant #41: P1.1.a 真功能 + adaptive 框架
永久 invariant #42: P1.2 CrewAI 4 组件 + P1.1.a 真功能 + 50 query 库

P3.2 增强 (相对 P3.1):
- Coder 真写文件 (B4 完整文件模式, 借鉴 P1.1.a)
- Linter 验证 (py_compile)
- Patcher 真修 (if Linter failed, 14B 重写 + Linter 再验证)
- 5 个真实改文件任务测试

用法: python crewai_v4.py "<改文件任务>" <target_file>
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

# 复用 P1.3 / P1.4 / P3.1
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-8mech-router-v2"))

from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL
from router import EIGHT_MECHANISMS, route_by_keywords, call_llm_router, EightMechRouter


# === P3.2 路径配置 ===
P32_DIR = Path(__file__).parent
CYCLE_REPORT = P32_DIR / "cycle-report.json"
P32_DIR.mkdir(parents=True, exist_ok=True)
TEST_FILES_DIR = P32_DIR / "test_files"

# 集成 P1.1.a 路径
RECALL_V2_SCRIPT = Path.home() / "workspace" / "mavis-recall-v2" / "recall.py"
VERIFIER_V2_SCRIPT = Path.home() / "workspace" / "mavis-verifier-v2" / "verifier.py"


# === CrewAI 4 组件 (P3.1 复用 + P3.2 加 target_file 支持) ===

@dataclass
class Agent:
    role: str
    goal: str
    backstory: str
    tools: List[Callable] = field(default_factory=list)
    allow_delegation: bool = False
    verbose: bool = False

    def build_system_prompt(self) -> str:
        return f"""你是{self.role}。

🎯 目标: {self.goal}

📚 背景: {self.backstory}

OUTPUT IN CHINESE. 简洁直接, 用 markdown 格式输出。"""


@dataclass
class Task:
    description: str
    expected_output: str
    agent: Agent
    context_from: Optional['Task'] = None
    output: str = ""
    # P3.2 新增: 改文件任务的目标文件
    target_file: Optional[str] = None
    # P3.2 新增: 改文件任务的状态 (Coder 输出文件路径 / Linter 结果)
    file_modified: Optional[str] = None
    linter_result: Optional[str] = None
    patcher_approved: Optional[bool] = None


class Process:
    def __init__(self, tasks: List[Task], mode: str = "sequential"):
        self.tasks = tasks
        self.mode = mode

    def run(self) -> List[Task]:
        for i, task in enumerate(self.tasks):
            print(f"\n📌 Task {i+1}/{len(self.tasks)}: {task.description[:60]}...")

            if task.context_from and task.context_from.output:
                task_with_context = f"""上游任务 ({task.context_from.description[:30]}) 的输出:
{task.context_from.output}

---

本任务 ({task.description}):"""
            else:
                task_with_context = task.description

            user_msg = f"""任务: {task_with_context}

期望输出: {task.expected_output}

请完成这个任务。"""

            if task.agent.role == "研究员":
                task.output = researcher_real(task.description, task.context_from.output if task.context_from else "")
            elif task.agent.role == "程序员" and task.target_file:
                # P3.2 真改文件
                task.output = coder_real_file(task.description, task.target_file, task.context_from.output if task.context_from else "")
            elif task.agent.role == "程序员":
                # P3.1 兼容: 知识查询
                task.output = coder_real(task.description, task.context_from.output if task.context_from else "")
            elif task.agent.role == "审核员" and task.target_file:
                # P3.2 真审核 + Patcher 真修
                task.output, task.patcher_approved = reviewer_real_file(task.description, task.target_file, task.context_from.output if task.context_from else "")
            elif task.agent.role == "审核员":
                task.output = reviewer_real(task.description, task.context_from.output if task.context_from else "")
            else:
                task.output = call_llm_14b(task.agent.build_system_prompt(), user_msg)

            print(f"   Agent ({task.agent.role}) 输出 ({len(task.output)} 字符): {task.output[:150]}...")

        return self.tasks


class Crew:
    def __init__(self, agents: List[Agent], tasks: List[Task], process_mode: str = "sequential"):
        self.agents = agents
        self.tasks = tasks
        self.process = Process(tasks, mode=process_mode)

    def kickoff(self) -> List[Task]:
        print(f"\n🚀 Crew kickoff: {len(self.agents)} agents, {len(self.tasks)} tasks, mode={self.process.mode}")
        return self.process.run()


# === LLM 工具 ===
# 永久 invariant #51: M3 Provider 接入 (用云端 LLM, 唔用本地大模型)
import sys as _sys
_sys.path.insert(0, str(Path.home() / "workspace" / "mavis-framework" / "mavis-crewai-v7"))
try:
    from mavis_m3_provider import call_llm_m3
    USE_M3 = True
except ImportError:
    USE_M3 = False


def call_llm_14b(system: str, user: str, timeout: int = 60) -> str:
    """调 LLM: 优先 M3, fallback 到本地 14B (永久 invariant #51)"""
    if USE_M3:
        for attempt in range(2):
            try:
                return call_llm_m3(
                    system=system,
                    user=user,
                    max_tokens=2048,
                    temperature=0.7,
                    use_fallback=True,  # M3 失败自动 fallback 到本地 14B
                ).strip()
            except Exception as e:
                if attempt == 1:
                    return f"[LLM_ERROR] {e}"
                time.sleep(2)
    # 无 M3 时, 用本地 ollama
    for attempt in range(2):
        try:
            r = httpx.post(
                f"{OLLAMA_BASE}/chat/completions",
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ]
                },
                timeout=timeout
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt == 1:
                return f"[LLM_ERROR] {e}"
            time.sleep(2)


# === P1.1.a 真功能 (P3.2 复用) ===

def researcher_real(query: str, context: str = "") -> str:
    try:
        result = subprocess.run(
            ["python3", str(RECALL_V2_SCRIPT), query, "hybrid", "3"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        if result.returncode == 0:
            return f"[recall.py 真调成功]\n\n{result.stdout[:1500]}"
        return f"[recall.py 失败] exit {result.returncode}: {result.stderr[:200]}"
    except Exception as e:
        return f"[recall.py 异常] {e}"


def coder_real(query: str, context: str = "") -> str:
    code = call_llm_14b(
        system="你是编码 Agent (Coder)。OUTPUT IN CHINESE。",
        user=f"用户 query: {query}\ncontext: {context[:500]}\n请生成代码或方案 (200 字内)。"
    )
    return code


def reviewer_real(query: str, context: str = "") -> str:
    try:
        result = subprocess.run(
            ["python3", str(VERIFIER_V2_SCRIPT),
             f"审核以下方案, exit_code=0, query={query[:100]}", "1"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        approved = (result.returncode == 0)
        summary = call_llm_14b(
            system="你是审核员, 综合上游 context + verifier 结果给出最终审核报告。",
            user=f"用户 query: {query}\ncontext: {context[:500]}\n\nverifier 审核: {'通过' if approved else '未通过'}\n请给出最终审核 (中文, 200 字内)。"
        )
        return f"[verifier.py {'通过' if approved else '未通过'}]\n\n{summary}"
    except Exception as e:
        return f"[verifier.py 异常] {e}"


# === P3.2 核心: Coder 真写文件 + Linter 验证 + Patcher 真修 ===

def _extract_python_code(text: str) -> Optional[str]:
    """提取 LLM 输出中的 python 块"""
    # 匹配 ```python ... ``` 或 ``` ... ```
    patterns = [
        r"```python\s*\n(.*?)\n```",
        r"```\s*\n(.*?)\n```",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return None


def _linter_check(file_path: str) -> str:
    """P3.2 Linter 验证 (py_compile)"""
    try:
        py_compile.compile(file_path, doraise=True)
        return "passed"
    except py_compile.PyCompileError as e:
        return f"failed: {str(e)[:200]}"
    except Exception as e:
        return f"failed: {type(e).__name__}: {str(e)[:200]}"


def coder_real_file(query: str, target_file: str, context: str = "") -> str:
    """P3.2 核心: Coder 真写文件 (B4 完整文件模式 + 长度检查 + Linter)"""
    target_path = Path(target_file)
    if not target_path.exists():
        return f"❌ target_file 不存在: {target_file}"

    print(f"   [Coder] 改文件: {target_file}")
    original_content = target_path.read_text(encoding="utf-8")
    original_length = len(original_content)
    original_excerpt = original_content[:8000]
    if original_length > 8000:
        original_excerpt += f"\n\n... (省略 {original_length - 8000} 字符) ..."

    # B4 完整文件模式 (借鉴 P1.1.a)
    max_retries = 3
    full_code = None
    linter_result = "not-attempted"
    retry_error = ""

    for attempt in range(1, max_retries + 1):
        print(f"   [尝试 {attempt}/{max_retries}]")
        error_prefix = ""
        if retry_error:
            error_prefix = f"""
**重要: 上一次失败, 错误信息:**
```
{retry_error[:500]}
```

**修正建议**:
- 如果是"输出无 python 块": 必须用 ```python ... ``` 包裹
- 如果是"长度过短 (< 70%)": 必须输出完整文件 (从头到尾)
- 如果是"linter 失败": 你输出的代码有语法错误, 仔细检查
"""

        system = """你是编码 Agent (Coder)。OUTPUT IN CHINESE。
**关键约束: 你必须输出完整的修改后文件, 不是 search/replace, 也不是 diff!**

格式 (借鉴 AgentScope 第 9 章):
```
请用 ```python ... ``` 包裹完整的修改后文件内容
```

要求 (极其重要, 违反会被 Linter 拒绝):
1. 必须输出**完整的修改后文件**, 整个文件从头到尾
2. **绝对不能**简化或删除现有代码 (除非是任务要求改的部分)
3. **绝对不能**只输出要改的那几行, 必须输出整个文件
4. 保留所有 import, 函数定义, 注释, 缩进风格
5. 你的修改必须满足任务描述
6. 长度必须 >= 原文件 70% (防止 LLM 简化)"""

        user = f"""任务: {query}
{error_prefix}
原文件当前内容 ({original_length} 字符, 前 8000 字符):
```python
{original_excerpt}
```

请输出**完整的修改后文件** (整个文件,从头到尾, 用 ```python ... ``` 包裹)。"""

        response = call_llm_14b(system, user, timeout=300)
        full_code = _extract_python_code(response)

        if not full_code:
            retry_error = f"LLM 输出无 python 代码块 (响应前 300: {response[:300]})"
            print(f"      ❌ 无 python 块, 准备重试")
            continue

        # 长度检查 (>= 70% 原文件长度)
        if len(full_code) < original_length * 0.7:
            retry_error = f"长度过短 ({len(full_code)} < {original_length} * 0.7 = {int(original_length * 0.7)})"
            print(f"      ❌ 长度过短, 准备重试")
            continue

        # 写临时文件, 跑 Linter
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        tmp_path.write_text(full_code, encoding="utf-8")
        linter_result = _linter_check(str(tmp_path))
        tmp_path.unlink()  # 删临时

        if linter_result == "passed":
            break  # 成功
        else:
            retry_error = f"Linter 失败: {linter_result}"
            print(f"      ❌ Linter 失败, 准备重试")

    # 写文件
    if linter_result == "passed" and full_code:
        target_path.write_text(full_code, encoding="utf-8")
        return f"""✅ [Coder 改文件成功]
target_file: {target_file}
原文件长度: {original_length} 字符
新文件长度: {len(full_code)} 字符
Linter: {linter_result}
文件已写入: {target_file}
新文件前 200 字符:
{full_code[:200]}

Context: {context[:300]}"""
    else:
        return f"""❌ [Coder 改文件失败]
target_file: {target_file}
Linter: {linter_result}
重试 {max_retries} 次均失败
最后一次错误: {retry_error[:200]}
文件未修改

Context: {context[:300]}"""


def reviewer_real_file(query: str, target_file: str, context: str = "") -> tuple:
    """P3.2 核心: Reviewer 真审核 + Patcher 真修 (if Linter failed)"""
    target_path = Path(target_file)
    if not target_path.exists():
        return f"❌ target_file 不存在: {target_file}", False

    print(f"   [Reviewer] 审核 + 修文件: {target_file}")
    current_content = target_path.read_text(encoding="utf-8")
    linter_result = _linter_check(target_file)
    approved = (linter_result == "passed")

    # Patcher 真修: if Linter failed, 调 14B 修
    patch_attempts = 2
    patch_status = "no-patch-needed"
    for attempt in range(1, patch_attempts + 1):
        if linter_result == "passed":
            patch_status = "no-patch-needed"
            break

        print(f"   [Patcher 尝试 {attempt}/{patch_attempts}] Linter 失败, 调 14B 修")
        # 调 14B 修
        patch_response = call_llm_14b(
            system="""你是 Patcher (修复 Agent)。OUTPUT IN CHINESE。
            修复 Python 文件的语法错误。""",
            user=f"文件: {target_file}\nLinter 错误: {linter_result}\n\n文件当前内容:\n```python\n{current_content}\n```\n\n请输出修复后的完整文件 (用 ```python ... ``` 包裹)。"
        )
        patched_code = _extract_python_code(patch_response)
        if patched_code:
            # 写 + 验证
            tmp_path = target_path.with_suffix(target_path.suffix + ".patch.tmp")
            tmp_path.write_text(patched_code, encoding="utf-8")
            linter_result = _linter_check(str(tmp_path))
            if linter_result == "passed":
                # 修成功, 写文件
                target_path.write_text(patched_code, encoding="utf-8")
                current_content = patched_code
                approved = True
                patch_status = f"patched-on-attempt-{attempt}"
                tmp_path.unlink()
                break
            tmp_path.unlink()

    # 调 verifier.py (per 永久 invariant #32)
    try:
        result = subprocess.run(
            ["python3", str(VERIFIER_V2_SCRIPT),
             f"审核改文件任务: {query[:100]}, linter={linter_result}", "1"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        verifier_approved = (result.returncode == 0)
    except Exception as e:
        verifier_approved = False

    summary = call_llm_14b(
        system="你是审核员, 综合 Linter + Patcher + verifier 结果给出最终审核报告。",
        user=f"任务: {query}\ntarget: {target_file}\nLinter: {linter_result}\nPatcher: {patch_status}\nverifier: {'通过' if verifier_approved else '未通过'}\n请给出最终审核 (中文, 200 字内)。"
    )
    return f"""[Reviewer 审核]
target_file: {target_file}
Linter: {linter_result}
Patcher: {patch_status}
verifier: {'通过' if verifier_approved else '未通过'}
最终审核: {'通过' if approved and verifier_approved else '未通过'}

{summary}""", (approved and verifier_approved)


# === P3.2 4 角色 Crew (跟 P3.1 一样, 但 Task 加 target_file) ===

def build_p32_crew(query: str, target_file: str) -> Crew:
    """P3.2 4 角色 Crew: Planner (Manager) + Researcher + Coder (真改文件) + Reviewer (真审核+修)"""
    planner = Agent(
        role="计划员",
        goal="按用户 query 制定改文件计划",
        backstory="""你擅长需求分析, 制定改文件子计划""",
        allow_delegation=True,
    )
    researcher = Agent(
        role="研究员",
        goal="检索 mavis memory 召回相关知识",
        backstory="""你擅长信息检索, 调用 mavis-recall-v2""",
    )
    coder = Agent(
        role="程序员",
        goal="按研究员的检索结果 + 计划, 改 target_file",
        backstory="""你是 Python 专家, B4 完整文件模式""",
    )
    reviewer = Agent(
        role="审核员",
        goal="审核 Coder 改文件的结果, 必要时用 Patcher 修",
        backstory="""你是审核专家, 调 verifier.py""",
    )

    planner_task = Task(
        description=f"分析改文件任务: {query} (target: {target_file})",
        expected_output="改文件计划 (3 步子计划 + 关键点)",
        agent=planner,
    )
    researcher_task = Task(
        description="检索 mavis memory 召回相关知识",
        expected_output="检索摘要",
        agent=researcher,
        context_from=planner_task,
    )
    coder_task = Task(
        description=f"按计划 + 检索结果, 改 target_file: {target_file}",
        expected_output="改文件结果 (Linter 通过 + 文件已写)",
        agent=coder,
        context_from=researcher_task,
        target_file=target_file,
    )
    reviewer_task = Task(
        description=f"审核 Coder 改文件结果 (target: {target_file}), 必要时 Patcher 修",
        expected_output="最终审核 (Linter + Patcher + verifier 全部通过)",
        agent=reviewer,
        context_from=coder_task,
        target_file=target_file,
    )

    return Crew(
        agents=[planner, researcher, coder, reviewer],
        tasks=[planner_task, researcher_task, coder_task, reviewer_task],
        process_mode="sequential"
    )


# === 主流程 ===

def run_crew_v4(query: str, target_file: str) -> dict:
    """P3.2 主入口: 真实改文件任务"""
    print("=" * 60)
    print("mavis CrewAI v4 - P3.2 真实改文件任务")
    print("永久 invariant #43: Coder 真写文件 + Linter 验证 + Patcher 真修")
    print("=" * 60)
    print(f"Query: {query}")
    print(f"Target: {target_file}")

    # 1. 8 机制 query 路由
    kw_matches = route_by_keywords(query)
    if kw_matches:
        mechanism = kw_matches[0][0]
    else:
        mechanism = call_llm_router(query, EIGHT_MECHANISMS) or "子智能体"
    print(f"\n🎯 路由结果: {mechanism}")

    # 2. 构建 P3.2 4 角色 Crew
    crew = build_p32_crew(query, target_file)

    # 3. 跑 Crew
    t0 = time.time()
    completed_tasks = crew.kickoff()
    elapsed = time.time() - t0

    # 4. 输出报告
    coder_task = completed_tasks[2]
    reviewer_task = completed_tasks[3]
    cycle_report = {
        "query": query,
        "target_file": target_file,
        "routed_mechanism": mechanism,
        "agents": [a.role for a in crew.agents],
        "tasks_count": len(completed_tasks),
        "node_history": [t.agent.role for t in completed_tasks],
        "coder_output": coder_task.output[:500],
        "reviewer_output": reviewer_task.output[:500],
        "patcher_approved": reviewer_task.patcher_approved,
        "elapsed_s": round(elapsed, 2),
        "version": "P3.2 (真改文件 + Linter + Patcher)",
        "completed_at": datetime.now().isoformat(),
    }
    CYCLE_REPORT.write_text(json.dumps(cycle_report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. 验证 Linter
    final_linter = _linter_check(target_file)
    final_size = os.path.getsize(target_file)
    cycle_report["final_linter"] = final_linter
    cycle_report["final_file_size"] = final_size
    CYCLE_REPORT.write_text(json.dumps(cycle_report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 最终结果 ===")
    print(f"任务: {query}")
    print(f"Target: {target_file}")
    print(f"最终 Linter: {final_linter}")
    print(f"最终文件大小: {final_size} 字符")
    print(f"Patcher 批准: {reviewer_task.patcher_approved}")
    print(f"⏱️  总耗时: {elapsed:.2f}s")
    print(f"📋 报告: {CYCLE_REPORT}")
    return cycle_report


# === 5 个真实改文件任务 ===

TEST_TASKS = [
    {
        "query": "给 sample1.py 的 hello() 和 add() 函数添加 docstring, 说明参数和返回值",
        "target": "sample1.py",
        "expected_change": "docstring"
    },
    {
        "query": "给 sample2.py 的 load_config() 和 save_config() 函数添加 type hints",
        "target": "sample2.py",
        "expected_change": "type hints"
    },
    {
        "query": "给 sample3.py 的 calculate() 函数添加除零检查, 当 op='div' 且 y=0 时返回 None",
        "target": "sample3.py",
        "expected_change": "除零检查"
    },
    {
        "query": "给 sample4.py 的 process_data() 函数添加对负数和零的过滤, 只处理正数",
        "target": "sample4.py",
        "expected_change": "过滤负数和零"
    },
    {
        "query": "给 sample5.py 的 User 类添加 __repr__ 方法",
        "target": "sample5.py",
        "expected_change": "__repr__ 方法"
    },
]


def run_5_file_test():
    """跑 5 个真实改文件任务测试"""
    print("=" * 60)
    print("P3.2 实战验证 - 5 个真实改文件任务")
    print("=" * 60)

    results = []
    for i, task in enumerate(TEST_TASKS, 1):
        target_path = TEST_FILES_DIR / task["target"]
        if not target_path.exists():
            print(f"\n[Test {i}/5] ❌ 文件不存在: {target_path}")
            results.append({"query": task["query"], "error": "file not found"})
            continue

        # 备份原文件
        backup_path = target_path.with_suffix(target_path.suffix + ".backup")
        shutil.copy2(target_path, backup_path)
        original_content = target_path.read_text(encoding="utf-8")

        print(f"\n[Test {i}/5] {task['expected_change']}: {task['target']}")
        try:
            report = run_crew_v4(task["query"], str(target_path))
            report["expected_change"] = task["expected_change"]
            # 验证 Linter
            final_linter = _linter_check(str(target_path))
            new_content = target_path.read_text(encoding="utf-8")
            file_changed = (new_content != original_content)
            report["final_linter"] = final_linter
            report["file_changed"] = file_changed
            report["backup_restored"] = False
            results.append(report)
        except Exception as e:
            print(f"[ERROR] {e}")
            # 还原
            shutil.copy2(backup_path, target_path)
            results.append({"query": task["query"], "error": str(e), "backup_restored": True})

    # 写报告
    report_path = P32_DIR / "crewai-v4-5file-test-results.json"
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
    print(f"📊 5 改文件任务跑通: {len(valid)}/{len(results)}")
    print(f"📊 Linter 通过: {linter_passed}/{len(valid)}")
    print(f"📊 文件已改: {file_changed}/{len(valid)}")
    print(f"⏱️  平均耗时: {avg_elapsed} 秒/次")
    print(f"📋 报告: {report_path}")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # 默认跑 5 个改文件任务
        run_5_file_test()
    elif sys.argv[1] == "5":
        run_5_file_test()
    else:
        # python crewai_v4.py "<改文件任务>" <target_file>
        if len(sys.argv) < 3:
            print("用法: python crewai_v4.py '<改文件任务>' <target_file>")
            print("或者: python crewai_v4.py 5  # 跑 5 个改文件任务")
            sys.exit(1)
        run_crew_v4(sys.argv[1], sys.argv[2])
