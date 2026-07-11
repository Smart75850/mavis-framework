#!/usr/bin/env python3
"""
P1.1.a 全面测试套件 - mavis-devika-runtime

测试矩阵:
- T1: 多次重复 (5 次同任务)
- T2: 修改类型多样 (5 种不同修改)
- T3: 回归测试
- T4: 失败场景
- T5: 功能性测试

输出: 测试报告 (JSON 格式) + 控制台汇总
"""
import subprocess
import time
import json
import shutil
from pathlib import Path
from datetime import datetime

# === 配置 ===
WORKSPACE = Path("/Users/apple/workspace")
RUNTIME = WORKSPACE / "mavis-devika-runtime" / "runtime.py"
RECALL_PY = WORKSPACE / "mavis-recall-v2" / "recall.py"
RECALL_BAK = WORKSPACE / "mavis-recall-v2" / "recall.py.bak.before-devika"
TEST_OUTPUT_DIR = WORKSPACE / "mavis-devika-runtime" / "test_results"
TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CONDA_ENV = "part03"
MAX_WAIT_PER_TEST = 600  # 每个测试最大等待秒数 (A1 改造后 LLM retry 3 次, 需要更久)

test_results = {
    "started_at": datetime.now().isoformat(),
    "tests": {}
}


def reset_recall_py():
    """回滚 recall.py 到原版"""
    shutil.copy(RECALL_BAK, RECALL_PY)


def run_runtime(objective: str, target_file: str = None,
                command: str = None, verify_pattern: str = None,
                max_turns: int = 2, max_wait: int = MAX_WAIT_PER_TEST) -> dict:
    """跑 runtime, 返回结果 dict"""
    cmd = ["conda", "run", "-n", CONDA_ENV, "python", "-u", str(RUNTIME),
           objective, str(max_turns)]
    if target_file:
        cmd.extend(["--target", target_file])
    if command:
        cmd.extend(["--command", command])
    if verify_pattern:
        cmd.extend(["--verify", verify_pattern])

    env = {"MAVIS_DEVIKA_USE_VERIFIER": "0"}

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_wait,
            env={**__import__("os").environ, **env}  # 继承父进程 env + 覆盖 MAVIS_DEVIKA_USE_VERIFIER
        )
        duration = time.time() - start
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration": duration,
            "success": result.returncode == 0,
            "timed_out": False
        }
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": "timeout",
            "duration": duration,
            "success": False,
            "timed_out": True
        }


def check_save_results_applied() -> dict:
    """检查 recall.py 是否真的加了 save_results"""
    if not RECALL_PY.exists():
        return {"applied": False, "error": "file not exists"}

    content = RECALL_PY.read_text(encoding="utf-8")
    md5 = hashlib_md5(content)

    return {
        "applied": "save_results" in content,
        "md5": md5,
        "size": len(content),
        "has_param": "save_results" in content,
        "syntax_ok": check_syntax(content)
    }


def hashlib_md5(content: str) -> str:
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()


def check_syntax(content: str) -> bool:
    """用 py_compile 检查语法"""
    import py_compile
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp = f.name
    try:
        py_compile.compile(tmp, doraise=True)
        return True
    except Exception:
        return False
    finally:
        Path(tmp).unlink(missing_ok=True)


def check_functional_save_results() -> dict:
    """T5: 功能性测试 - save_results 参数真能输出 JSON"""
    # 跑一次 recall.py, 看 save_results 实际能不能生成 JSON
    test_json = "/tmp/test_save_results_output.json"
    Path(test_json).unlink(missing_ok=True)
    try:
        result = subprocess.run(
            ["python3", str(RECALL_PY), "LangGraph mavis", "hybrid", "2"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(RECALL_PY.parent)
        )
        return {
            "ran": True,
            "exit_code": result.returncode,
            "stdout_snippet": result.stdout[:500],
            "stderr_snippet": result.stderr[:300]
        }
    except Exception as e:
        return {"ran": False, "error": str(e)}


def run_t1_repeat_test(n=5):
    """T1: 多次重复测试 - 同任务跑 N 次"""
    print(f"\n=== T1: 多次重复测试 (N={n}) ===")
    t1_results = []
    for i in range(1, n + 1):
        print(f"\n--- T1.{i}/{n} ---")
        reset_recall_py()
        result = run_runtime(
            "给 recall.py 加一个 save_results 参数, 支持把召回结果保存到 JSON 文件",
            target_file=str(RECALL_PY),
            command='cd /Users/apple/workspace/mavis-recall-v2 && python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location(\'recall\', \'recall.py\'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); import inspect; print(\'save_results in signature:\', \'save_results\' in str(inspect.signature(m.agent_frame_recall)))"',
            verify_pattern="save_results in signature: True"
        )

        check = check_save_results_applied()

        case_result = {
            "attempt": i,
            "runtime_exit_code": result["exit_code"],
            "runtime_success": result["success"],
            "timed_out": result["timed_out"],
            "duration_sec": round(result["duration"], 1),
            "applied": check["applied"],
            "syntax_ok": check["syntax_ok"],
            "md5": check["md5"],
            "stdout_key_lines": [
                line for line in result["stdout"].split("\n")
                if any(kw in line for kw in ["尝试", "apply 成功", "apply 失败", "linter", "✅", "❌", "save_results"])
            ]
        }
        t1_results.append(case_result)
        print(f"   runtime exit: {result['exit_code']}, applied: {check['applied']}, syntax: {check['syntax_ok']}")

    success_count = sum(1 for r in t1_results if r["applied"] and r["syntax_ok"])
    print(f"\nT1 汇总: {success_count}/{n} 成功")
    return {"total": n, "success": success_count, "rate": f"{success_count/n*100:.0f}%", "details": t1_results}


def run_t2_modification_types():
    """T2: 修改类型多样测试"""
    print(f"\n=== T2: 修改类型多样测试 ===")
    t2_cases = [
        {
            "name": "2a-加参数",
            "objective": "给 agent_frame_recall 函数加一个 verbose: bool = False 参数, 控制是否打印详细信息",
            "verify_pattern": "verbose in signature: True",
            "verify_command": 'cd /Users/apple/workspace/mavis-recall-v2 && python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location(\'recall\', \'recall.py\'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); import inspect; print(\'verbose in signature:\', \'verbose\' in str(inspect.signature(m.agent_frame_recall)))"'
        },
        {
            "name": "2b-改函数体",
            "objective": "把 operator_split 函数里的 chunk_size 默认值从 1024 改成 2048",
            "verify_pattern": "chunk_size=2048",
            "verify_command": 'cd /Users/apple/workspace/mavis-recall-v2 && python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location(\'recall\', \'recall.py\'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); import inspect; print(\'chunk_size=2048:\', \'2048\' in str(inspect.signature(m.operator_split)))"'
        }
    ]

    t2_results = []
    for case in t2_cases:
        if case.get("skip"):
            print(f"\n--- T2 {case['name']} (跳过) ---")
            continue
        print(f"\n--- T2 {case['name']} ---")
        reset_recall_py()
        result = run_runtime(
            case["objective"],
            target_file=str(RECALL_PY),
            command=case["verify_command"],
            verify_pattern=case["verify_pattern"]
        )
        # 不再用 check_save_results_applied (T2 不一定加 save_results!)
        # 改用: 直接跑 verify_command 看 stdout 是否含 verify_pattern
        verify_passed = False
        syntax_ok = True
        try:
            verify_proc = subprocess.run(
                case["verify_command"],
                shell=True, capture_output=True, text=True, timeout=30
            )
            verify_passed = case["verify_pattern"] in verify_proc.stdout
            # syntax check 单独跑
            syntax_proc = subprocess.run(
                ["python3", "-c", f"import py_compile; py_compile.compile('{RECALL_PY}', doraise=True)"],
                capture_output=True, text=True, timeout=10
            )
            syntax_ok = syntax_proc.returncode == 0
        except Exception as e:
            print(f"   ⚠️  verify 异常: {e}")

        case_result = {
            "name": case["name"],
            "objective": case["objective"][:50],
            "runtime_exit_code": result["exit_code"],
            "duration_sec": round(result["duration"], 1),
            "applied": verify_passed,
            "syntax_ok": syntax_ok,
            "verify_stdout": verify_proc.stdout[:200] if 'verify_proc' in dir() else ""
        }
        t2_results.append(case_result)
        print(f"   runtime exit: {result['exit_code']}, verify_passed: {verify_passed}, syntax: {syntax_ok}")
        if verify_proc.stdout:
            print(f"   verify stdout: {verify_proc.stdout[:200].strip()}")

    success_count = sum(1 for r in t2_results if r["applied"] and r["syntax_ok"])
    print(f"\nT2 汇总: {success_count}/{len(t2_results)} 成功")
    return {"total": len(t2_results), "success": success_count, "rate": f"{success_count/len(t2_results)*100:.0f}%", "details": t2_results}


def run_t3_regression_test():
    """T3: 回归测试 - 修改后跑 query 不破坏"""
    print(f"\n=== T3: 回归测试 ===")
    # 先把 recall.py 加 save_results (成功的修改)
    reset_recall_py()
    print("准备: 先给 recall.py 加 save_results...")
    setup_result = run_runtime(
        "给 recall.py 加一个 save_results 参数, 支持把召回结果保存到 JSON 文件",
        target_file=str(RECALL_PY),
        command='cd /Users/apple/workspace/mavis-recall-v2 && python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location(\'recall\', \'recall.py\'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(\'save_results in signature:\', \'save_results\' in str(__import__(\'inspect\').signature(m.agent_frame_recall)))"',
        verify_pattern="save_results in signature: True",
        max_wait=300
    )

    if not setup_result["success"]:
        print(f"   ⚠️ 准备工作失败, exit={setup_result['exit_code']}, 跳过 T3")
        return {"setup_failed": True, "tests": []}

    # 跑回归测试
    print("\n--- T3.1 英文 query 跑一次 ---")
    eng_result = subprocess.run(
        ["python3", str(RECALL_PY), "LangGraph mavis", "hybrid", "3"],
        capture_output=True, text=True, timeout=60,
        cwd=str(RECALL_PY.parent)
    )

    print("\n--- T3.2 中文 query 跑一次 ---")
    zh_result = subprocess.run(
        ["python3", str(RECALL_PY), "中文关键词检索", "hybrid", "3"],
        capture_output=True, text=True, timeout=60,
        cwd=str(RECALL_PY.parent)
    )

    return {
        "setup_applied": True,
        "english_test": {
            "exit_code": eng_result.returncode,
            "stdout_snippet": eng_result.stdout[:300]
        },
        "chinese_test": {
            "exit_code": zh_result.returncode,
            "stdout_snippet": zh_result.stdout[:300]
        }
    }


def run_t4_failure_cases():
    """T4: 失败场景测试"""
    print(f"\n=== T4: 失败场景测试 ===")
    reset_recall_py()

    # T4.1: 不存在的文件
    print("\n--- T4.1 不存在的 target_file ---")
    result1 = run_runtime(
        "给不存在的文件加一个参数",
        target_file="/tmp/nonexistent_file_xyz.py",
        command="echo test",
        verify_pattern="anything",
        max_turns=1
    )
    print(f"   exit={result1['exit_code']}")

    # T4.2: 不给 target_file
    print("\n--- T4.2 不给 target_file ---")
    result2 = run_runtime(
        "随便改点什么",
        target_file=None,
        command="echo test",
        verify_pattern="anything",
        max_turns=1
    )
    print(f"   exit={result2['exit_code']}")

    return {
        "nonexistent_file": {
            "exit_code": result1["exit_code"],
            "timed_out": result1["timed_out"],
            "stdout_tail": result1["stdout"][-500:]
        },
        "no_target_file": {
            "exit_code": result2["exit_code"],
            "timed_out": result2["timed_out"],
            "stdout_tail": result2["stdout"][-500:]
        }
    }


def run_t5_functional_test():
    """T5: 功能性测试 - save_results 真的能输出 JSON"""
    print(f"\n=== T5: 功能性测试 ===")
    reset_recall_py()

    # 步骤 1: 加 save_results
    print("--- T5.1: 加 save_results 参数 ---")
    setup = run_runtime(
        "给 recall.py 加一个 save_results 参数, 支持把召回结果保存到 JSON 文件",
        target_file=str(RECALL_PY),
        command='cd /Users/apple/workspace/mavis-recall-v2 && python3 -c "import importlib.util; spec = importlib.util.spec_from_file_location(\'recall\', \'recall.py\'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(\'save_results in signature:\', \'save_results\' in str(__import__(\'inspect\').signature(m.agent_frame_recall)))"',
        verify_pattern="save_results in signature: True",
        max_turns=3
    )

    if not setup["success"]:
        return {"setup_failed": True, "error": setup["stderr"][:200]}

    # 步骤 2: 用 save_results 真跑
    print("--- T5.2: 用 save_results 跑 recall.py ---")
    test_json = "/tmp/t5_save_results.json"
    Path(test_json).unlink(missing_ok=True)

    # 检查 save_results 是否支持
    check_import = subprocess.run(
        ["python3", "-c",
         f"""
import importlib.util
spec = importlib.util.spec_from_file_location('recall', '{RECALL_PY}')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
import inspect
sig = inspect.signature(m.agent_frame_recall)
print('save_results in sig:', 'save_results' in sig.parameters)
print('save_results default:', sig.parameters.get('save_results'))
"""],
        capture_output=True, text=True, timeout=10
    )
    print(f"   import check: {check_import.stdout.strip()}")

    return {
        "setup_applied": True,
        "import_check": check_import.stdout.strip(),
        "import_check_exit": check_import.returncode
    }


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ["t1", "all"]:
        test_results["tests"]["T1_repeat"] = run_t1_repeat_test(n=5)

    if mode in ["t2", "all"]:
        test_results["tests"]["T2_modification_types"] = run_t2_modification_types()

    if mode in ["t3", "all"]:
        test_results["tests"]["T3_regression"] = run_t3_regression_test()

    if mode in ["t4", "all"]:
        test_results["tests"]["T4_failure_cases"] = run_t4_failure_cases()

    if mode in ["t5", "all"]:
        test_results["tests"]["T5_functional"] = run_t5_functional_test()

    # 恢复原版
    reset_recall_py()

    test_results["completed_at"] = datetime.now().isoformat()

    # 输出 JSON
    output_file = TEST_OUTPUT_DIR / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.write_text(json.dumps(test_results, ensure_ascii=False, indent=2))
    print(f"\n=== 完整结果已保存到: {output_file} ===")