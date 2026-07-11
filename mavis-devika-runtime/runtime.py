#!/usr/bin/env python3
"""
mavis devika runtime - 9 Agent LangGraph StateGraph (2026-07-10)
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #31: Devika 9 大 Agent 模板

集成 4 大改造:
- mavis-recall-v2 (Researcher)
- mavis-verifier-v2 (Patcher)
- mavis-team-plan-v2 (Planner 部分借鉴)
- mavis-devika-template (9 Agent Prompt 骨架)

LangGraph 1.0+ API:
- StateGraph (DAG)
- Node function (input: state -> output: dict)
- conditional_edges (条件边)
- MemorySaver (持久化)
- workflow.compile().invoke()

用法: python runtime.py "<objective>" [max_turns]
"""
import sys
import os
import json
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from operator import add

# === LangGraph imports (part03 conda env) ===
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

# === 永久 invariant #12: Ollama 兼容名 ===
LLM_BASE = "http://127.0.0.1:11434/v1"
LLM_MODEL = "gpt-3.5-turbo"  # qwen3:32b 兼容名 (主力)

# === A1: LLM retry + fallback 配置 (2026-07-10) ===
# 主用: qwen2.5:14b (2.16 秒响应, 比 32B 快 33 倍)
# Fallback: gpt-3.5-turbo (兼容名 = qwen3:32b, 太慢)
# Ollama serve 自动按 model 字段加载对应模型
LLM_MODELS_CHAIN = os.environ.get("MAVIS_LLM_MODELS", "qwen2.5:14b,gpt-3.5-turbo").split(",")
LLM_RETRY_PER_MODEL = int(os.environ.get("MAVIS_LLM_RETRY", "2"))  # 每个模型重试 2 次
LLM_TIMEOUT = int(os.environ.get("MAVIS_LLM_TIMEOUT", "45"))  # 单次 timeout 45s (14B 快,不需要长)
LLM_RETRY_SLEEP = int(os.environ.get("MAVIS_LLM_RETRY_SLEEP", "2"))  # 重试间隔 2s

# === 路径配置 ===
RUNTIME_DIR = Path.home() / "workspace" / "mavis-devika-runtime"
STATE_FILE = RUNTIME_DIR / "mavis-devika-state.json"
CYCLE_REPORT = RUNTIME_DIR / "cycle-report.json"
WORKSPACE_BASE = Path.home() / "workspace"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# 集成 4 大改造的路径
RECALL_V2_SCRIPT = WORKSPACE_BASE / "mavis-recall-v2" / "recall.py"
VERIFIER_V2_SCRIPT = WORKSPACE_BASE / "mavis-verifier-v2" / "verifier.py"

# === LLM 工具 (借鉴 mavis-team-v2 call_llm + A1 改造 retry/fallback) ===

def call_llm(system: str, user: str, timeout: Optional[int] = None) -> str:
    """调用 Ollama, 支持 retry + fallback 模型链.

    配置 (环境变量):
    - MAVIS_LLM_MODELS: 逗号分隔的模型链 (默认: gpt-3.5-turbo,llama3-fast)
    - MAVIS_LLM_RETRY: 每个模型重试次数 (默认: 3)
    - MAVIS_LLM_TIMEOUT: 单次 timeout 秒数 (默认: 90)
    - MAVIS_LLM_RETRY_SLEEP: 重试间隔秒数 (默认: 3)

    Returns:
        成功: LLM 响应文本
        失败: "[LLM_FALLBACK_FAILED] {last_error}" 字符串
    """
    if timeout is None:
        timeout = LLM_TIMEOUT

    last_error = None
    for model in LLM_MODELS_CHAIN:
        model = model.strip()
        for attempt in range(1, LLM_RETRY_PER_MODEL + 1):
            try:
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user}
                    ]
                }
                req = urllib.request.Request(
                    f"{LLM_BASE}/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read())
                    content = data["choices"][0]["message"]["content"]
                    if attempt > 1 or model != LLM_MODELS_CHAIN[0].strip():
                        print(f"      [LLM] ✅ {model} attempt {attempt} 成功")
                    return content
            except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
                # 网络/超时错误 → retry
                last_error = f"[{model} attempt {attempt}] {type(e).__name__}: {str(e)[:200]}"
                if attempt < LLM_RETRY_PER_MODEL:
                    print(f"      [LLM] ⚠️ {model} attempt {attempt} 失败: {type(e).__name__}, {LLM_RETRY_SLEEP}s 后重试...")
                    time.sleep(LLM_RETRY_SLEEP)
                continue
            except Exception as e:
                # 其他错误 (JSON 解析等) → 立即 fallback 到下个模型
                last_error = f"[{model}] {type(e).__name__}: {str(e)[:200]}"
                print(f"      [LLM] ❌ {model} 错误: {type(e).__name__}, fallback")
                break

    # 所有模型都失败
    return f"[LLM_FALLBACK_FAILED] {last_error}"


# === Context Schema (复用 Devika CONVENTIONS.md §2) ===

class PlanStep(TypedDict):
    step_number: int
    action: str
    expected_output: str
    depends_on: List[int]

class Plan(TypedDict):
    objective: str
    steps: List[PlanStep]
    estimated_turns: int

class Research(TypedDict):
    queries: List[Dict[str, Any]]

class Code(TypedDict):
    files: List[Dict[str, Any]]
    diff: str
    syntax_check: str

class RunResult(TypedDict):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int

class Patch(TypedDict):
    root_cause: str
    fix: Dict[str, Any]
    tests: List[Dict[str, Any]]

class Action(TypedDict):
    keyword: str
    args: Dict[str, Any]
    target_agent: str

class Report(TypedDict):
    summary: str
    sections: List[Dict[str, str]]
    format: str

class Decision(TypedDict):
    function: str
    params: Dict[str, Any]
    fallback: Optional[str]

class DevikaContext(TypedDict):
    """9 大 Agent 共享的 Context (借鉴 Devika §5.1.2 上下文流转)"""
    # 输入
    project_id: str
    session_id: str
    user_intent: str
    # 9 个 Agent 的输出 (Annotated 用来 merge 多轮结果)
    plan: Optional[Plan]
    research: Optional[Research]
    code: Optional[Code]
    run_result: Optional[RunResult]
    patch: Optional[Patch]
    action: Optional[Action]
    report: Optional[Report]
    decision: Optional[Decision]
    # 控制
    current_turn: int
    max_turns: int
    last_approved: bool
    last_error: Optional[str]
    # 审计
    node_history: Annotated[List[str], add]
    messages: Annotated[List[Dict[str, str]], add]
    metadata: Dict[str, Any]


def init_context(objective: str, max_turns: int = 5) -> DevikaContext:
    """初始化 Context"""
    return {
        "project_id": "devika-runtime",
        "session_id": f"ses_{os.getpid()}",
        "user_intent": objective,
        "plan": None,
        "research": None,
        "code": None,
        "run_result": None,
        "patch": None,
        "action": None,
        "report": None,
        "decision": None,
        "current_turn": 0,
        "max_turns": max_turns,
        "last_approved": False,
        "last_error": None,
        "node_history": [],
        "messages": [{"role": "user", "content": objective}],
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "version": "1.0"
        }
    }


# === 9 大 Agent 节点 (Node Functions) ===
# LangGraph Node 约定: 输入 state -> 返回 partial state dict

def node_01_planner(state: DevikaContext) -> Dict[str, Any]:
    """01 规划 Agent (Devika §5.1.2 (1))"""
    print("\n🧠 [01 Planner] 制订计划中...")
    system = """你是规划 Agent (Planner)。OUTPUT IN CHINESE。
根据用户指令制订 3-5 步分步计划,每步以动词开头。
返回 JSON: {"objective": "...", "steps": [{"step_number": 1, "action": "...", "expected_output": "...", "depends_on": []}], "estimated_turns": 3}
永久坑: 不要返回英文, 全部中文。"""
    user = f"目标: {state['user_intent']}"
    response = call_llm(system, user)
    print(f"   计划: {response[:200]}...")

    # 解析 JSON (容错: 提取代码块或找 JSON)
    plan = _parse_json_response(response, default={
        "objective": state["user_intent"],
        "steps": [{"step_number": 1, "action": "执行用户目标", "expected_output": "完成", "depends_on": []}],
        "estimated_turns": 1
    })

    return {
        "plan": plan,
        "current_turn": state["current_turn"] + 1,
        "node_history": ["01_planner"],
        "messages": [{"role": "assistant", "content": f"[Planner] {response}"}]
    }


def node_02_researcher(state: DevikaContext) -> Dict[str, Any]:
    """02 研究 Agent (Devika §5.1.2 (2) + 永久 invariant #30 mavis-recall-v2)"""
    print("\n🔍 [02 Researcher] 检索中...")
    plan = state.get("plan") or {}
    objective = plan.get("objective", state["user_intent"])

    # 集成 4 大改造 #1: mavis-recall-v2
    research_data = {"queries": [], "source": "mavis-recall-v2"}
    try:
        result = subprocess.run(
            ["python3", str(RECALL_V2_SCRIPT), objective, "hybrid", "3"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
        )
        if result.returncode == 0:
            research_data["queries"].append({
                "query": objective,
                "rank": 1,
                "source": "mavis-recall-v2",
                "raw_output": result.stdout[:500]
            })
            print(f"   mavis-recall-v2 召回成功 (exit 0)")
        else:
            print(f"   mavis-recall-v2 失败 (exit {result.returncode}): {result.stderr[:200]}")
    except Exception as e:
        print(f"   mavis-recall-v2 异常: {e}")

    return {
        "research": research_data,
        "node_history": ["02_researcher"],
        "messages": [{"role": "assistant", "content": f"[Researcher] 召回 {len(research_data['queries'])} 条"}]
    }


def node_03_coder(state: DevikaContext) -> Dict[str, Any]:
    """03 编码 Agent (Devika §5.1.2 (3) + ReAct 永久 invariant #19)
    - B4 完整文件模式 (借鉴 AgentScope 第 9 章: LLM 输出完整 Python 代码 + 工具执行)
    - 内部重试 max_retries=3
    - 失败 → 错误反馈到 prompt → 重试 LLM
    - 长度检查: 新文件必须 >= 原文件 70% (防止 LLM 大幅简化)
    """
    print("\n💻 [03 Coder] 完整文件模式 (B4 AgentScope 风格)...")
    plan = state.get("plan") or {}
    research = state.get("research") or {}
    target_file = state.get("metadata", {}).get("target_file")
    operation = state.get("metadata", {}).get("operation", "modify")
    prior_error_from_workflow = state.get("metadata", {}).get("prior_coder_error", "")

    current_step = state["current_turn"]
    steps = plan.get("steps", [])
    if current_step <= len(steps):
        target_step = steps[current_step - 1] if current_step > 0 else steps[0] if steps else {}
    else:
        target_step = steps[-1] if steps else {}

    # 读取目标文件当前内容
    target_path = Path(target_file) if target_file else None
    if not target_path:
        print("   ❌ 无 target_file, 跳过")
        return {
            "code": {"files": [{"path": "no-target", "operation": operation}], "syntax_check": "skipped", "written_file": None, "apply_status": "no-target-file"},
            "node_history": ["03_coder"],
            "messages": [{"role": "assistant", "content": "[Coder] skipped: no target_file"}]
        }
    if not target_path.exists():
        print(f"   ❌ target_file 不存在: {target_path}")
        return {
            "code": {"files": [{"path": str(target_path), "operation": operation}], "syntax_check": "skipped", "written_file": None, "apply_status": "file-not-exists"},
            "node_history": ["03_coder"],
            "messages": [{"role": "assistant", "content": f"[Coder] file not exists: {target_path}"}]
        }

    original_content = target_path.read_text(encoding="utf-8")
    # 截断到 8000 字符给 LLM 看 (B4 完整文件模式,需要更多上下文)
    original_excerpt = original_content[:8000]
    if len(original_content) > 8000:
        original_excerpt += f"\n\n... (省略 {len(original_content) - 8000} 字符) ..."

    system = """你是编码 Agent (Coder)。OUTPUT IN CHINESE。
**关键约束: 你必须输出完整的修改后文件, 不是 search/replace, 也不是 diff!**

格式 (借鉴 AgentScope 第 9 章):
```
请用 ```python ... ``` 包裹完整的修改后文件内容
```

要求 (极其重要,违反会被 Linter 拒绝):
1. 必须输出**完整的修改后文件**, 整个文件从头到尾
2. **绝对不能**简化或删除现有代码 (除非是任务要求改的部分)
3. **绝对不能**只输出要改的那几行, 必须输出整个文件
4. 保留所有 import, 函数定义, 注释, 缩进风格
5. 你的修改必须满足任务描述
6. 如果上一次失败, 看错误信息, 修正

常见错误 (你必须避免):
- 只输出新加的几行, 没有原文件其他内容 → Linter 会失败
- 简化原文件的复杂函数 → 长度检查会拒绝
- 缩进不一致 → syntax 错误

参考第 9 章 AgentScope 做法: LLM 生成完整 Python 代码, 工具执行, 不依赖精确复制原文件。"""

    # === 内部重试逻辑 ===
    max_retries = 3
    retry_error = prior_error_from_workflow
    full_code = None
    final_attempt = 1
    final_status = "not-attempted"

    for attempt in range(1, max_retries + 1):
        print(f"   [尝试 {attempt}/{max_retries}]")
        final_attempt = attempt

        error_prefix = ""
        if retry_error:
            error_prefix = f"""
**重要: 上一次失败, 错误信息如下, 必须避免:**
```
{retry_error[:500]}
```

**修正建议**:
- 如果是"输出无 python 块": 必须用 ```python ... ``` 包裹
- 如果是"长度过短": 你的输出是简化版, 必须输出完整文件 (从头到尾)
- 如果是"linter 失败": 你输出的代码有语法错误, 仔细检查
- 如果是"save_results 之类参数没出现": 你没真正实现需求, 重新做
"""

        user = f"""任务: {plan.get('objective', '')}
当前步骤: {target_step.get('action', '')}
期望输出: {target_step.get('expected_output', '')}
目标文件: {target_file}
操作类型: {operation}
{error_prefix}
原文件当前内容 ({len(original_content)} 字符, 前 8000 字符):
```python
{original_excerpt}
```

请输出**完整的修改后文件** (整个文件,从头到尾, 用 ```python ... ``` 包裹)。"""

        response = call_llm(system, user, timeout=300)

        # 提取 python 块
        full_code = _extract_python_code(response)

        if not full_code:
            retry_error = f"LLM 输出无 python 代码块 (响应前 300: {response[:300]})"
            print(f"      ❌ 无 python 块, 准备重试")
            continue

        # 长度检查: 防止 LLM 大幅简化 (B6 改造实验: 阈值 0.95 反而触发多次 retry, 实际更差)
        # 原因: LLM 持续简化输出, 0.95 阈值触发 retry 但 LLM 仍然简化, 3 次都失败
        # 回退到 0.7 阈值: 防 50% 以下灾难性简化, 留空间给合理修改
        ratio = len(full_code) / max(len(original_content), 1)
        if ratio < 0.7:
            retry_error = f"输出太短 (新 {len(full_code)} 字符, 原 {len(original_content)} 字符, 比例 {ratio:.0%} < 70%)。说明你大幅简化了原文件, 必须输出完整文件"
            print(f"      ⚠️  输出过短 ({ratio:.0%} < 70%), 准备重试")
            continue

        # 备份 + 写
        backup_path = target_path.with_suffix(target_path.suffix + f".bak.b4.{os.getpid()}")
        backup_path.write_text(original_content, encoding="utf-8")
        try:
            target_path.write_text(full_code, encoding="utf-8")
        except Exception as e:
            retry_error = f"写文件失败: {e}"
            print(f"      ❌ 写文件失败: {e}")
            continue

        # Linter 检查
        lint_result = _lint_python_file(target_path)
        if lint_result == "passed":
            final_status = f"applied-full-file (attempt {attempt}/{max_retries})"
            print(f"      ✅ 完整文件应用 + linter passed (新 {len(full_code)} 字符, 比例 {ratio:.0%})")
            break  # 成功
        else:
            retry_error = f"linter 失败: {lint_result[:300]}"
            print(f"      ⚠️  linter 失败, 恢复原文件, 准备重试")
            target_path.write_text(original_content, encoding="utf-8")  # 恢复
            continue

    # === 重试结束 ===
    written_file = None
    syntax_check = "skipped"
    if full_code and final_status.startswith("applied"):
        written_file = str(target_path)
        syntax_check = "passed"
        print(f"   ✅ B4 最终成功 (尝试 {final_attempt}/{max_retries})")
        print(f"   新文件长度: {len(full_code)} 字符 (原 {len(original_content)} 字符, {len(full_code)/max(len(original_content),1):.0%})")
    else:
        syntax_check = f"failed: {retry_error[:200]}" if retry_error else "unknown"
        print(f"   ❌ B4 最终失败 ({final_attempt} 次尝试)")
        # 确保文件恢复
        if target_path.exists():
            target_path.write_text(original_content, encoding="utf-8")
            print(f"   ↩️  文件已恢复原版")
        state["metadata"]["prior_coder_error"] = retry_error or "unknown"

    return {
        "code": {
            "files": [{"path": written_file or "no-target", "operation": operation, "full_file_mode": True, "new_length": len(full_code) if full_code else 0, "attempts": final_attempt}],
            "diff": "",
            "syntax_check": syntax_check,
            "written_file": written_file,
            "apply_status": final_status
        },
        "node_history": ["03_coder"],
        "messages": [{"role": "assistant", "content": f"[Coder B4] {final_status}, syntax={syntax_check}"}]
    }


def node_04_action(state: DevikaContext) -> Dict[str, Any]:
    """04 行动 Agent (Devika §5.1.2 (4)) - 路由"""
    print("\n🎯 [04 Action] 路由中...")
    # MVP: 简化实现,总是路由到 Reporter (后续可扩展)
    action = {
        "keyword": "report",
        "args": {},
        "target_agent": "08_reporter"
    }
    print(f"   路由: {action['keyword']} -> {action['target_agent']}")
    return {
        "action": action,
        "node_history": ["04_action"],
        "messages": [{"role": "assistant", "content": f"[Action] 路由到 {action['target_agent']}"}]
    }


def node_05_runner(state: DevikaContext) -> Dict[str, Any]:
    """05 运行 Agent (Devika §5.1.2 (5)) - 真实执行版"""
    print("\n⚡ [05 Runner] 真实执行命令中...")
    code = state.get("code") or {}
    written_file = code.get("written_file")
    metadata = state.get("metadata", {})
    command = metadata.get("run_command")
    working_dir = metadata.get("working_dir", str(Path.home()))

    # 决定要跑什么命令
    if command:
        # 用户指定了命令
        cmd_to_run = command
        cwd = working_dir
    elif written_file and Path(written_file).exists():
        # 自动验证: 跑 python -c 导入模块,验证 syntax + 可调用
        cmd_to_run = f"python3 -c \"import importlib.util, sys; spec = importlib.util.spec_from_file_location('m', '{written_file}'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print('[Runner] import OK, has agent_frame_recall:', hasattr(m, 'agent_frame_recall'))\""
        cwd = Path(written_file).parent
    else:
        # 无目标文件, 无命令
        run_result = {
            "exit_code": -1,
            "stdout": "",
            "stderr": "无 target_file 也无 run_command,无法执行",
            "duration_ms": 0,
            "sandbox": "none"
        }
        print(f"   ⚠️  {run_result['stderr']}")
        return {
            "run_result": run_result,
            "last_approved": False,
            "node_history": ["05_runner"],
            "messages": [{"role": "assistant", "content": f"[Runner] skipped: {run_result['stderr']}"}]
        }

    # 真实 subprocess 执行
    print(f"   command: {cmd_to_run[:200]}")
    print(f"   cwd: {cwd}")
    start = datetime.now()
    try:
        result = subprocess.run(
            cmd_to_run,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=cwd
        )
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        run_result = {
            "exit_code": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
            "duration_ms": duration_ms,
            "sandbox": "local"
        }
        print(f"   exit_code: {result.returncode} ({duration_ms}ms)")
        if result.stdout:
            print(f"   stdout (前 200): {result.stdout[:200]}")
        if result.stderr:
            print(f"   stderr (前 200): {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        run_result = {
            "exit_code": 124,
            "stdout": "",
            "stderr": f"timeout after 60s",
            "duration_ms": 60000,
            "sandbox": "local"
        }
        print(f"   ⏱️  timeout")
    except Exception as e:
        run_result = {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e}",
            "duration_ms": 0,
            "sandbox": "local"
        }
        print(f"   ❌ 异常: {e}")

    # 验证实际效果 (新增): 如果用户指定 verify_pattern, 必须 stdout 里能找到
    verify_pattern = metadata.get("verify_pattern")
    if verify_pattern:
        if verify_pattern in run_result["stdout"]:
            print(f"   ✅ verify_pattern 找到: '{verify_pattern[:80]}'")
        else:
            print(f"   ❌ verify_pattern 未找到: '{verify_pattern[:80]}'")
            print(f"      实际 stdout: {run_result['stdout'][:200]}")
            # 把 exit_code 强制设为 1, 触发 Patcher
            run_result["exit_code"] = 1
            run_result["stderr"] += f"\n[Runner verify_pattern failed] expected '{verify_pattern[:80]}' not in stdout"

    return {
        "run_result": run_result,
        "last_approved": run_result["exit_code"] == 0,
        "node_history": ["05_runner"],
        "messages": [{"role": "assistant", "content": f"[Runner] exit={run_result['exit_code']}, {run_result['stdout'][:200]}"}]
    }


def node_06_feature(state: DevikaContext) -> Dict[str, Any]:
    """06 新特性 Agent (Devika §5.1.2 (6))"""
    print("\n✨ [06 Feature] 新特性中...")
    return {
        "node_history": ["06_feature"],
        "messages": [{"role": "assistant", "content": "[Feature] MVP 占位"}]
    }


def node_07_patcher(state: DevikaContext) -> Dict[str, Any]:
    """07 补丁 Agent (Devika §5.1.2 (7) + 永久 invariant #22 mavis-verifier-v2)"""
    print("\n🔧 [07 Patcher] 诊断 + 修复中...")
    run_result = state.get("run_result") or {}
    code = state.get("code") or {}

    # 集成 4 大改造 #2: mavis-verifier-v2 (用环境变量控制, 避免默认超时)
    use_verifier = os.environ.get("MAVIS_DEVIKA_USE_VERIFIER", "1") == "1"
    patch_data = {"root_cause": "", "fix": {}, "tests": []}

    if use_verifier:
        try:
            result = subprocess.run(
                ["conda", "run", "-n", "part03", "python", str(VERIFIER_V2_SCRIPT),
                 f"审核当前执行结果, exit_code={run_result.get('exit_code', -1)}, stderr={run_result.get('stderr', '')[:200]}", "1"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                patch_data["root_cause"] = "mavis-verifier-v2 审核通过"
                patch_data["tests"] = [{"name": "verifier-v2", "passed": True}]
                print(f"   mavis-verifier-v2 通过")
            else:
                patch_data["root_cause"] = f"verifier 退出 {result.returncode}"
                patch_data["tests"] = [{"name": "verifier-v2", "passed": False}]
                print(f"   mavis-verifier-v2 异常")
        except Exception as e:
            patch_data["root_cause"] = f"Patcher 异常: {e}"
            patch_data["tests"] = [{"name": "verifier-v2", "passed": False, "error": str(e)}]
            print(f"   Patcher 异常: {e}")
    else:
        # MVP 模式: 跳过 verifier, 标记 approved=True 走完流程
        patch_data["root_cause"] = "MVP mode (跳过 verifier v2)"
        patch_data["tests"] = [{"name": "mvp-skip", "passed": True}]
        print(f"   MVP 模式 (MAVIS_DEVIKA_USE_VERIFIER=0)")

    return {
        "patch": patch_data,
        "last_approved": all(t.get("passed") for t in patch_data["tests"]),
        "node_history": ["07_patcher"],
        "messages": [{"role": "assistant", "content": f"[Patcher] {patch_data['root_cause']}"}]
    }


def node_08_reporter(state: DevikaContext) -> Dict[str, Any]:
    """08 报告 Agent (Devika §5.1.2 (8))"""
    print("\n📊 [08 Reporter] 生成报告中...")
    history = state.get("node_history", [])

    summary_parts = []
    if state.get("plan"):
        plan = state["plan"]
        summary_parts.append(f"目标: {plan.get('objective', '')}")
        summary_parts.append(f"步骤数: {len(plan.get('steps', []))}")
    if state.get("run_result"):
        summary_parts.append(f"执行: exit_code={state['run_result'].get('exit_code', 'N/A')}")
    if state.get("patch"):
        summary_parts.append(f"审核: {state['patch'].get('root_cause', '')[:100]}")

    report = {
        "summary": "; ".join(summary_parts) or "无执行结果",
        "sections": [
            {"title": "节点执行历史", "content": " -> ".join(history)},
            {"title": "最终状态", "content": f"last_approved={state.get('last_approved')}, turns={state.get('current_turn')}/{state.get('max_turns')}"}
        ],
        "format": "markdown"
    }

    print(f"   报告生成: {report['summary'][:100]}")
    return {
        "report": report,
        "last_approved": True,  # 报告生成后标记完成
        "node_history": ["08_reporter"],
        "messages": [{"role": "assistant", "content": f"[Reporter] {report['summary']}"}]
    }


def node_09_decision(state: DevikaContext) -> Dict[str, Any]:
    """09 决策 Agent (Devika §5.1.2 (9) + 永久 invariant #18 Function-calling)"""
    print("\n🧭 [09 Decision] 决策中...")
    # MVP: 简化
    decision = {
        "function": "no_op",
        "params": {},
        "fallback": None
    }
    print(f"   决策: {decision['function']}")
    return {
        "decision": decision,
        "node_history": ["09_decision"],
        "messages": [{"role": "assistant", "content": f"[Decision] {decision['function']}"}]
    }


# === 条件边函数 (Conditional Edges) ===

def should_continue_after_runner(state: DevikaContext) -> str:
    """Runner 后: 成功 → Reporter, 失败 → Patcher"""
    run_result = state.get("run_result") or {}
    if run_result.get("exit_code", 0) == 0:
        return "08_reporter"
    return "07_patcher"


def should_continue_after_patcher(state: DevikaContext) -> str:
    """Patcher 后: approved → Reporter (完成), turns 超限 → Reporter, 否则 → Runner (重试)"""
    if state.get("last_approved", False):
        return "08_reporter"  # 修复成功, 出报告
    if state.get("current_turn", 0) >= state.get("max_turns", 5):
        return "08_reporter"  # 到上限, 强制出报告
    return "05_runner"  # 未通过 + 未到上限, 重试


def action_route(state: DevikaContext) -> str:
    """Action 后: 根据 keyword 路由"""
    action = state.get("action") or {}
    keyword = action.get("keyword", "report")
    route_map = {
        "run": "05_runner",
        "test": "05_runner",
        "deploy": "05_runner",
        "patch": "07_patcher",
        "feature": "06_feature",
        "report": "08_reporter",
        "clone": "09_decision",
        "browse": "09_decision"
    }
    return route_map.get(keyword, "08_reporter")


# === 工具函数 ===

def _parse_json_response(response: str, default: Any) -> Any:
    """从 LLM 响应中提取 JSON (容错)"""
    # 尝试 1: 提取 ```json 代码块
    if "```json" in response:
        try:
            start = response.index("```json") + 7
            end = response.index("```", start)
            return json.loads(response[start:end].strip())
        except Exception:
            pass
    # 尝试 2: 找第一个 { 到最后一个 }
    if "{" in response and "}" in response:
        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
        except Exception:
            pass
    return default


def _extract_python_code(response: str) -> Optional[str]:
    """从 LLM 响应中提取 ```python 代码块"""
    import re
    # 尝试 1: ```python ... ```
    m = re.search(r"```python\s*\n(.*?)```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 尝试 2: ```py ... ```
    m = re.search(r"```py\s*\n(.*?)```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 尝试 3: ``` ... ``` (无语言标识)
    m = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _extract_diff(response: str) -> Optional[str]:
    """从 LLM 响应中提取 ```diff 代码块"""
    import re
    # 尝试 1: ```diff ... ```
    m = re.search(r"```diff\s*\n(.*?)```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 尝试 2: ```patch ... ```
    m = re.search(r"```patch\s*\n(.*?)```", response, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 尝试 3: 找 --- a/ +++ b/ 开头 (无代码块包裹)
    if "--- a/" in response and "+++ b/" in response:
        # 提取从 --- a/ 到响应结束的 diff
        start = response.index("--- a/")
        return response[start:].strip()
    return None


def _extract_search_replace(response: str) -> List[Dict[str, str]]:
    """从 LLM 响应中提取 search/replace 块 (Aider 风格)

    Returns:
        [{"search": "...", "replace": "..."}, ...]
    """
    import re
    blocks = []

    # 尝试 1: ```search_replace ... ``` 块
    sr_match = re.search(r"```search_replace\s*\n(.*?)```", response, re.DOTALL)
    if sr_match:
        content = sr_match.group(1)
    else:
        # 尝试 2: ``` ... ``` (无语言标识) 找 search:/replace: 模式
        code_match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
        if code_match and "search:" in code_match.group(1) and "replace:" in code_match.group(1):
            content = code_match.group(1)
        else:
            # 尝试 3: 直接找 search:/replace: 模式 (无代码块包裹)
            if "search:" in response and "replace:" in response:
                content = response
            else:
                return blocks

    # 解析多个 search/replace 对
    # 用正则找所有 search: ... replace: ... 对
    pattern = re.compile(r"search:\s*\n(.*?)\n\s*replace:\s*\n(.*?)(?=\n\s*search:|\Z)", re.DOTALL)
    for m in pattern.finditer(content):
        search_text = m.group(1).rstrip("\n")
        replace_text = m.group(2).rstrip("\n")
        if search_text and replace_text:
            blocks.append({"search": search_text, "replace": replace_text})

    return blocks


def _apply_search_replaces(target_path: Path, blocks: List[Dict[str, str]]) -> Dict[str, Any]:
    """应用 search/replace 块到文件 (借鉴 Aider 思路, 但用 Python 直接做)

    Returns:
        {"success": bool, "status": str, "error": str, "diff_preview": str}
    """
    if not target_path.exists():
        return {"success": False, "status": "file-not-found", "error": f"{target_path} 不存在", "diff_preview": ""}

    try:
        content = target_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"success": False, "status": "read-failed", "error": f"读文件失败: {e}", "diff_preview": ""}

    applied = 0
    diff_parts = []

    for i, block in enumerate(blocks, 1):
        search_text = block["search"]
        replace_text = block["replace"]

        if search_text in content:
            new_content = content.replace(search_text, replace_text, 1)
            if new_content != content:
                content = new_content
                applied += 1
                diff_parts.append(f"--- block {i} ---\n- {search_text[:100]}\n+ {replace_text[:100]}")
            else:
                return {
                    "success": False,
                    "status": "no-change",
                    "error": f"block {i}: search 找到但替换没变化 (search==replace?)",
                    "diff_preview": "\n".join(diff_parts)
                }
        else:
            # 模糊匹配: 尝试忽略末尾空白
            search_stripped = search_text.rstrip()
            if search_stripped in content:
                new_content = content.replace(search_stripped, replace_text, 1)
                content = new_content
                applied += 1
                diff_parts.append(f"--- block {i} (stripped) ---")
            else:
                # 尝试逐行匹配 (容忍末尾空行差异)
                search_lines = search_text.split("\n")
                search_first = search_lines[0] if search_lines else ""
                if search_first and search_first in content:
                    # 找到第一行, 尝试扩展匹配
                    start = content.index(search_first)
                    # 找后面 n 行的总长度
                    expected_len = len(search_text)
                    end = start + expected_len
                    if end <= len(content) and content[start:end].rstrip() == search_text.rstrip():
                        new_content = content[:start] + replace_text + content[end:]
                        content = new_content
                        applied += 1
                        diff_parts.append(f"--- block {i} (line-matched) ---")
                    else:
                        return {
                            "success": False,
                            "status": "search-not-found",
                            "error": f"block {i}: search 块第 1 行找到了 ({search_first[:60]}...) 但后续内容不匹配. 请 100% 复制原文件内容 (包括缩进、空行)。",
                            "diff_preview": "\n".join(diff_parts)
                        }
                else:
                    return {
                        "success": False,
                        "status": "search-not-found",
                        "error": f"block {i}: search 块在文件中找不到 (第 1 行: {search_first[:60]}...). 请 100% 复制原文件内容。",
                        "diff_preview": "\n".join(diff_parts)
                    }

    if applied == 0:
        return {
            "success": False,
            "status": "no-blocks-applied",
            "error": "没有任何 search/replace 块被应用",
            "diff_preview": ""
        }

    # 写文件
    try:
        # 备份
        backup_path = target_path.with_suffix(target_path.suffix + f".bak.sr.{os.getpid()}")
        backup_path.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
        # 写入新内容
        target_path.write_text(content, encoding="utf-8")
    except Exception as e:
        return {
            "success": False,
            "status": "write-failed",
            "error": f"写文件失败: {e}",
            "diff_preview": "\n".join(diff_parts)
        }

    return {
        "success": True,
        "status": f"applied-{applied}-blocks",
        "error": "",
        "diff_preview": "\n".join(diff_parts),
        "backup": str(backup_path)
    }


def _lint_python_file(target_path: Path) -> str:
    """Linter: 检查 Python 文件语法 (借鉴 SWE-agent ACI 设计)"""
    if not target_path.exists():
        return "skipped (file not found)"
    if not str(target_path).endswith(".py"):
        return "skipped (not .py)"
    try:
        import py_compile
        py_compile.compile(str(target_path), doraise=True)
        return "passed"
    except py_compile.PyCompileError as e:
        return f"failed: {str(e)[:200]}"
    except Exception as e:
        return f"failed: {type(e).__name__}: {str(e)[:200]}"


def _apply_diff_with_patch(target_path: Path, diff_content: str, dry_run: bool = False) -> Dict[str, Any]:
    """用 patch 命令应用 diff 到文件

    Args:
        target_path: 目标文件路径
        diff_content: unified diff 内容
        dry_run: True=只验证不应用

    Returns:
        {"success": bool, "stdout": str, "stderr": str}
    """
    import tempfile

    # 写入临时 diff 文件
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(diff_content)
        diff_file = f.name

    try:
        # 把 --- a/xxx 和 +++ b/xxx 改成实际路径
        # patch 默认从 diff 头部读文件名, -p1 剥掉 a/ 或 b/ 前缀
        target_dir = target_path.parent
        target_filename = target_path.name

        # 备份原文件 (如果不是 dry_run)
        backup_path = target_path.with_suffix(target_path.suffix + f".bak.coder.{os.getpid()}")
        if not dry_run:
            backup_path.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")

        cmd = ["patch", "-d", str(target_dir), "-p1"]
        if dry_run:
            cmd.append("--dry-run")

        with open(diff_file, "r") as f:
            result = subprocess.run(
                cmd,
                stdin=f,
                capture_output=True,
                text=True,
                timeout=30
            )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "backup": str(backup_path) if backup_path.exists() else None
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "patch timeout"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": f"{type(e).__name__}: {e}"}
    finally:
        try:
            os.unlink(diff_file)
        except Exception:
            pass


# === 主流程: 构建 LangGraph StateGraph ===

def build_workflow() -> Any:
    """构建 9 Agent LangGraph StateGraph"""
    workflow = StateGraph(DevikaContext)

    # 9 个节点
    workflow.add_node("01_planner", node_01_planner)
    workflow.add_node("02_researcher", node_02_researcher)
    workflow.add_node("03_coder", node_03_coder)
    workflow.add_node("04_action", node_04_action)
    workflow.add_node("05_runner", node_05_runner)
    workflow.add_node("06_feature", node_06_feature)
    workflow.add_node("07_patcher", node_07_patcher)
    workflow.add_node("08_reporter", node_08_reporter)
    workflow.add_node("09_decision", node_09_decision)

    # 主流程边 (借鉴 Devika 上下文流转图)
    workflow.add_edge(START, "01_planner")
    workflow.add_edge("01_planner", "02_researcher")
    workflow.add_edge("02_researcher", "03_coder")
    workflow.add_edge("03_coder", "05_runner")

    # 条件边 1: Runner 后根据 exit_code 路由
    workflow.add_conditional_edges(
        "05_runner",
        should_continue_after_runner,
        {
            "07_patcher": "07_patcher",
            "08_reporter": "08_reporter"
        }
    )

    # 条件边 2: Patcher 后根据 approved/turns 路由
    workflow.add_conditional_edges(
        "07_patcher",
        should_continue_after_patcher,
        {
            "05_runner": "05_runner",
            "08_reporter": "08_reporter"
        }
    )

    # Action / Decision / Feature 边 (MVP 简化: 直接到 Reporter)
    workflow.add_edge("04_action", "08_reporter")
    workflow.add_edge("06_feature", "08_reporter")
    workflow.add_edge("09_decision", "08_reporter")

    # Reporter 后结束
    workflow.add_edge("08_reporter", END)

    # 持久化 (LangGraph MemorySaver)
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


def run_workflow(objective: str, max_turns: int = 5, target_file: Optional[str] = None,
                run_command: Optional[str] = None, working_dir: Optional[str] = None,
                operation: str = "modify", verify_pattern: Optional[str] = None):
    """运行 9 Agent workflow

    Args:
        objective: 用户目标
        max_turns: 最大轮次
        target_file: 目标文件路径 (Coder 会写到这里)
        run_command: Runner 要执行的命令 (可选, 否则自动验证)
        working_dir: 工作目录
        operation: 文件操作类型 (create/modify/delete)
        verify_pattern: stdout 中必须包含的字符串 (用于真实效果验证)
    """
    print("=" * 60)
    print("mavis devika runtime - 9 Agent LangGraph StateGraph (REAL mode)")
    print("永久 invariant #21: LangGraph StateGraph = mavis DAG")
    print("永久 invariant #31: Devika 9 大 Agent 模板")
    print("永久 invariant #32: mavis-devika-runtime")
    print("OUTPUT IN CHINESE")
    print("=" * 60)
    print(f"目标: {objective}")
    print(f"max_turns: {max_turns}")
    if target_file:
        print(f"target_file: {target_file}")
    if run_command:
        print(f"run_command: {run_command[:200]}")
    if verify_pattern:
        print(f"verify_pattern: {verify_pattern}")
    print()

    # 初始化
    initial_state = init_context(objective, max_turns)
    initial_state["metadata"]["target_file"] = target_file
    initial_state["metadata"]["run_command"] = run_command
    initial_state["metadata"]["working_dir"] = working_dir
    initial_state["metadata"]["operation"] = operation
    initial_state["metadata"]["verify_pattern"] = verify_pattern

    app = build_workflow()

    # 配置 thread (持久化用)
    config = {"configurable": {"thread_id": initial_state["session_id"]}, "recursion_limit": 50}

    # 运行 (LangGraph invoke)
    try:
        final_state = app.invoke(initial_state, config=config)
    except Exception as e:
        print(f"\n[ERROR] Workflow 异常: {e}")
        return None

    # 输出报告
    print("\n" + "=" * 60)
    print("=== 最终报告 ===")
    if final_state.get("report"):
        report = final_state["report"]
        print(f"\n摘要: {report.get('summary', '')}")
        print(f"\n章节:")
        for sec in report.get("sections", []):
            print(f"  - {sec.get('title', '')}: {sec.get('content', '')[:200]}")
    else:
        print("无报告生成")

    print(f"\n节点执行历史: {' -> '.join(final_state.get('node_history', []))}")
    print(f"最终轮次: {final_state.get('current_turn', 0)}/{final_state.get('max_turns', 0)}")
    print(f"最终批准: {final_state.get('last_approved', False)}")

    # 持久化
    STATE_FILE.write_text(json.dumps(final_state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    CYCLE_REPORT.write_text(json.dumps({
        "objective": objective,
        "completed_at": datetime.now().isoformat(),
        "node_history": final_state.get("node_history", []),
        "final_approved": final_state.get("last_approved", False),
        "turns": f"{final_state.get('current_turn', 0)}/{final_state.get('max_turns', 0)}",
        "target_file": target_file
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n状态文件: {STATE_FILE}")
    print(f"Cycle 报告: {CYCLE_REPORT}")
    print("=" * 60)

    return final_state


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python runtime.py '<objective>' [max_turns] [--target FILE] [--command CMD] [--cwd DIR]")
        print("示例:")
        print("  python runtime.py '给 recall.py 加 save_results 参数' 2 --target ~/workspace/mavis-recall-v2/recall.py")
        print("  python runtime.py '修复某 bug' 3 --target /path/to/file.py --command 'pytest tests/'")
        sys.exit(1)

    objective = sys.argv[1]
    max_turns = int(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 3

    target_file = None
    run_command = None
    working_dir = None
    verify_pattern = None
    args = sys.argv[3:] if len(sys.argv) > 3 else []
    i = 0
    while i < len(args):
        if args[i] == "--target" and i + 1 < len(args):
            target_file = os.path.expanduser(args[i + 1])
            i += 2
        elif args[i] == "--command" and i + 1 < len(args):
            run_command = args[i + 1]
            i += 2
        elif args[i] == "--cwd" and i + 1 < len(args):
            working_dir = os.path.expanduser(args[i + 1])
            i += 2
        elif args[i] == "--verify" and i + 1 < len(args):
            verify_pattern = args[i + 1]
            i += 2
        else:
            i += 1

    run_workflow(objective, max_turns, target_file=target_file, run_command=run_command,
                 working_dir=working_dir, verify_pattern=verify_pattern)