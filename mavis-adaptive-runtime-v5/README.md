# mavis Adaptive Runtime v5 - P3.0 完整版

> **永久 invariant #41**: P1.1.a 真功能 + P2.z adaptive 框架 = mavis adaptive runtime v5
> **永久 invariant #21**: LangGraph StateGraph = mavis team plan DAG
> **永久 invariant #36**: LlamaIndex 4 步索引 = mavis memory RAG
> **永久 invariant #37**: mavis 8 机制 query 路由
> **永久 invariant #38**: adaptive runtime (P2.x 基础)
> **永久 invariant #39**: adaptive runtime v3 (P2.y 完整版)
> **永久 invariant #40**: LLM 动态选节点 (P2.z)

## 解决什么问题

P2.z 是轻量版 (researcher 调 P1.4 query_engine / coder 调 14B mock / runner mock / patcher 随机), 没有真 P1.1.a subprocess。
**P3.0 = P1.1.a 4 大真功能 + P2.z adaptive 框架**。

效果:
- 6/8 query 真调 recall.py (P1.1.a 真功能)
- 5/8 query 真调 14B 写代码
- 4/8 query 真跑白名单命令
- 平均 20.52 秒/次 (跟 P2.z 20.57s 几乎一样, P1.1.a 真功能不增加耗时)

## P2.z → P3.0 整合

| 节点 | P2.z 轻量版 | P3.0 整合 P1.1.a 真功能 |
|---|---|---|
| 02_researcher | 调 P1.4 query_engine | **调 mavis-recall-v2/recall.py 真 subprocess** |
| 03_coder | 调 14B mock | **B4 完整文件模式 (P3.0 query 模式不真写)** |
| 05_runner | mock 随机 exit_code | **真 subprocess (P1.1.a 60s timeout + P2.z 白名单)** |
| 07_patcher | 随机 approved | **调 mavis-verifier-v2/verifier.py 真 subprocess** |
| 其他 6 节点 | 跟 P2.z 一样 | 跟 P2.z 一样 (00_router, 01_planner, 04_action, 06_feature, 08_reporter, 09_decision) |

## 4 大 P1.1.a 真功能

### 1. 02_researcher (调 recall.py)

```python
def researcher_v5(query: str) -> dict:
    result = subprocess.run(
        ["python3", str(RECALL_V2_SCRIPT), query, "hybrid", "3"],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "HTTP_PROXY": "", "HTTPS_PROXY": ""}
    )
    # 解析 recall.py 输出, 取 top-3
    return {"research": top_results, "source": "mavis-recall-v2 (P1.1.a 真功能)"}
```

### 2. 03_coder (B4 完整文件模式)

```python
def coder_v5(query: str, plan: str) -> dict:
    code = _call_llm_14b(
        system="你是编码 Agent (Coder)。OUTPUT IN CHINESE。",
        user=f"用户 query: {query}\nplan: {plan}"
    )
    return {"code": code, "apply_status": "P3.0-query-mode (不真写文件)"}
```

### 3. 05_runner (真 subprocess)

```python
def runner_v5(query: str) -> dict:
    cmd = _call_llm_14b("白名单命令", query)  # 14B 决定跑什么
    result = safe_subprocess_run(cmd, timeout=10)  # P2.z 白名单 + P3.0 强化黑名单
    return {"command": cmd, "exit_code": result["exit_code"], ...}
```

### 4. 07_patcher (调 verifier.py)

```python
def patcher_v5(run_result: dict) -> dict:
    result = subprocess.run(
        ["python3", str(VERIFIER_V2_SCRIPT), f"审核 exit_code={run_result.get('exit_code', -1)}", "1"],
        capture_output=True, text=True, timeout=60
    )
    return {"patch": "mavis-verifier-v2 审核", "approved": (result.returncode == 0)}
```

## 实战验证 (2026-07-11 05:30)

**8 query 全部跑通, 路由准确率 8/8 = 100%!**

| Test | 机制 | 00_router 决定 | 节点 | 耗时 |
|---|---|---|---|---|
| 1 | CLAUDE.md | 01+02+04+05+08 | 5 | 20.73s |
| 2 | 子智能体 | 01+04+05+08+09 | 5 | 16.28s |
| 3 | Skills | 02+05+08 | 3 | **8.32s** |
| 4 | Hooks | 01+03+08 | 3 | 29.69s |
| 5 | MCP | 02+03+08 | 3 | 20.56s |
| 6 | Headless | 02+03+04+05+08 | 5 | 29.21s |
| 7 | Agent SDK | 01+02+03+08 | 4 | 18.18s |
| 8 | Plugins | 01+02+03+08 | 4 | 21.21s |

**P1.1.a 真功能调用统计**:
- researcher (recall.py): **6/8 真调**
- coder (14B B4): **5/8 真调**
- runner (subprocess): **4/8 真跑**
- patcher (verifier.py): 0/8 (query 任务不需要)

**平均 20.52 秒/次** (跟 P2.z 20.57s 几乎一样)

## 用法

```bash
# 1. 激活 venv
source ~/workspace/mavis-llamaindex/bin/activate

# 2. 跑 8 query 完整测试
python3 ~/workspace/mavis-adaptive-runtime-v5/adaptive_runtime_v5.py

# 3. 自定义 query
python3 ~/workspace/mavis-adaptive-runtime-v5/adaptive_runtime_v5.py "mavis 怎么 work" 5
```

## 复用今晚经验 (P1.x + P2.x + P2.y + P2.z + P3.0)

| 经验 | 来源 | P3.0 应用 |
|---|---|---|
| P1.1.a 真功能 (researcher/runner/patcher subprocess) | 永久 invariant #32 | P3.0 4 大节点整合 |
| P2.z 00_router LLM 动态选节点 | 永久 invariant #40 | P3.0 保留 |
| P2.z 真 subprocess 白名单安全 | 永久 invariant #40 | P3.0 强化黑名单 19+ 模式 |
| P2.y hierarchical Manager | 永久 invariant #39 | P3.0 01_planner 当 Manager |
| P2.y decision_route 真回 planner | 永久 invariant #39 | P3.0 保留 |
| P1.4 8 机制 query 路由 | 永久 invariant #37 | P3.0 入口处路由 |
| P1.3 LlamaIndex 4 步索引 | 永久 invariant #36 | P3.0 02_researcher 优先 recall.py (真), 备 query_engine |
| 14B 模型 | 永久 invariant #34 | P3.0 全 10 节点用 14B |

## 下一步 (P3.1+)

- **P3.1**: P3.0 + CrewAI 4 组件完整对接 (per 永久 invariant #35)
- **P3.2**: 真 subprocess 跑 mavis 内置测试 (例如 `python3 -c "import mavis"`)
- **P3.3**: hierarchical Manager 委派 sub-Agent (per CrewAI P1.2 hierarchical)
- **P3.4**: auto rebuild 索引 (mavis memory 更新时)
- **P3.5**: 扩展 query 库 8 → 50 测 (scale up 验证)

## 验收 checklist

- [x] P1.1.a 4 大真功能整合 (researcher/runner/patcher subprocess + coder B4)
- [x] P2.z adaptive 框架保留 (00_router 动态选节点)
- [x] 8 机制 query 路由 (复用 P1.4)
- [x] 真 subprocess 安全 (白名单 11 + 黑名单 23+ 模式)
- [x] 真 decision_route (revise → 01_planner)
- [x] 8 query 实战验证
- [x] 路由准确率 8/8 = 100%
- [x] P1.1.a 真功能调用统计: researcher 6/8, coder 5/8, runner 4/8
- [x] 平均 20.52 秒/次 (跟 P2.z 几乎一样)

## 文件清单

- `adaptive_runtime_v5.py` (主入口, 530 行)
- `cycle-report.json` (单 query 报告)
- `adaptive-v5-test-results.json` (8 query 验证)
- `README.md` (本文)
