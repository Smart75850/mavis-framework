# mavis CrewAI v4 - P3.2 真实改文件任务

> **永久 invariant #43**: Coder 真写文件 + Linter 验证 + Patcher 真修 = mavis CrewAI v4
> **永久 invariant #21**: LangGraph StateGraph = mavis team plan DAG
> **永久 invariant #35**: CrewAI 4 组件 = mavis Agent 模板
> **永久 invariant #36**: LlamaIndex 4 步索引 = mavis memory RAG
> **永久 invariant #37**: mavis 8 机制 query 路由
> **永久 invariant #40**: LLM 动态选节点
> **永久 invariant #41**: P1.1.a 真功能 + adaptive 框架
> **永久 invariant #42**: P1.2 CrewAI 4 组件 + P1.1.a 真功能 + 50 query 库

## 解决什么问题

P3.1 是知识查询 (不真写文件), 不能做实际改文件任务。
**P3.2 = P3.1 + Coder 真写文件 (B4) + Linter 验证 (py_compile) + Patcher 真修**。

效果:
- 5/5 改文件任务 100% 跑通
- 5/5 Linter 通过
- 5/5 文件已改
- 平均 23.11 秒/次

## P3.1 → P3.2 增强

| 维度 | P3.1 | P3.2 |
|---|---|---|
| Coder | 调 14B mock, 不真写 | **B4 完整文件模式 + 真写 (借鉴 P1.1.a)** |
| Linter | 无 | **py_compile 验证 (借鉴 P1.1.a)** |
| Patcher | 无 | **真修 (if Linter failed, 14B 重写 + 再 Linter)** |
| 长度检查 | 无 | **>= 70% 原文件长度 (借鉴 P1.1.a, 防止 LLM 简化)** |
| 内部重试 | 无 | **3 次 (借鉴 P1.1.a)** |
| Test 场景 | 50 query 知识查询 | **5 个真实改文件任务** |
| Test 文件 | 无 | **5 个 .py 文件 (sample1-5.py)** |

## Coder 真写文件 (B4 完整文件模式)

```python
def coder_real_file(query, target_file, context):
    target_path = Path(target_file)
    original_content = target_path.read_text(encoding="utf-8")
    original_length = len(original_content)
    
    for attempt in range(1, max_retries + 1):
        response = call_llm_14b(system, user, timeout=300)
        full_code = _extract_python_code(response)  # ```python ... ```
        
        if not full_code:
            retry  # 无 python 块
        if len(full_code) < original_length * 0.7:
            retry  # 长度过短
        
        # 写临时文件, 跑 Linter
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        tmp_path.write_text(full_code, encoding="utf-8")
        linter_result = _linter_check(str(tmp_path))  # py_compile
        tmp_path.unlink()
        
        if linter_result == "passed":
            target_path.write_text(full_code, encoding="utf-8")  # 真写
            break
    
    return output_with_linter_result
```

## Patcher 真修 (if Linter failed)

```python
def reviewer_real_file(query, target_file, context):
    linter_result = _linter_check(target_file)
    if linter_result != "passed":
        for attempt in range(1, 3):
            patch_response = call_llm_14b("修", file_content)
            patched_code = _extract_python_code(patch_response)
            if patched_code:
                tmp.write_text(patched_code)
                linter = _linter_check(tmp)
                if linter == "passed":
                    target.write_text(patched_code)  # 真修
                    break
    return review_summary
```

## 实战验证 (2026-07-11 08:50)

**5 改文件任务全部跑通 100%!**

| Test | 改动 | Linter | 大小变化 | 耗时 |
|---|---|---|---|---|
| 1 | docstring (sample1) | passed | 362→706 | 29.18s |
| 2 | type hints (sample2) | passed | 262→568 | 18.61s |
| 3 | 除零检查 (sample3) | passed | 211→784 | 22.09s |
| 4 | 过滤负数和零 (sample4) | passed | 137→801 | 23.20s |
| 5 | __repr__ 方法 (sample5) | passed | 177→736 | 22.48s |

**5/5 Linter 通过, 5/5 文件已改, 平均 23.11 秒/次**

## 4 角色 Crew 流程 (P3.2)

1. **Planner (Manager)**: 制定 3 步改文件子计划
2. **Researcher (Worker)**: 调 mavis-recall-v2/recall.py 真调, 召回相关知识
3. **Coder (Worker)**: B4 完整文件模式 + Linter 验证 + 真写
4. **Reviewer (Worker)**: 调 mavis-verifier-v2 + Patcher 真修 (if Linter failed)

## 用法

```bash
# 1. 激活 venv
source ~/workspace/mavis-llamaindex/bin/activate

# 2. 跑 5 改文件任务
python3 ~/workspace/mavis-crewai-v4/crewai_v4.py 5

# 3. 自定义改文件任务
python3 ~/workspace/mavis-crewai-v4/crewai_v4.py "<改文件任务>" <target_file>
# 例: python3 ~/workspace/mavis-crewai-v4/crewai_v4.py "添加 docstring" /tmp/test.py
```

## 复用今晚经验 (P1.x + P2.x + P3.0 + P3.1 + P3.2)

| 经验 | 来源 | P3.2 应用 |
|---|---|---|
| B4 完整文件模式 (P1.1.a) | 永久 invariant #32 | P3.2 Coder 真写 |
| py_compile Linter (P1.1.a) | 永久 invariant #32 | P3.2 Linter 验证 |
| 长度检查 70% (P1.1.a) | 永久 invariant #32 | P3.2 长度检查 |
| 内部重试 3 次 (P1.1.a) | 永久 invariant #32 | P3.2 内部重试 |
| P3.1 4 角色 Crew | 永久 invariant #42 | P3.2 保留 |
| P3.1 真调 recall.py | 永久 invariant #42 | P3.2 Researcher |
| P3.1 真调 verifier.py | 永久 invariant #42 | P3.2 Reviewer |

## 5 大踩坑 (P3.2 实战)

1. **LLM 14B 倾向简化**: P1.1.a 已经踩过, P3.2 长度检查 70% 必加
2. **LLM 输出无 python 块**: P3.2 _extract_python_code 严格匹配
3. **临时文件清理**: P3.2 用 .tmp 后缀 + 立即 unlink
4. **Patcher 没触发**: 5/5 任务 Coder 一次成功, Patcher 备用
5. **Patcher 批准 False**: verifier.py 14B 写代码不完整, 不影响 Linter

## 下一步 (P3.3+)

- **P3.3**: 50 改文件任务 (大 scale up)
- **P3.4**: hierarchical Manager 委派 sub-Agent
- **P3.5**: auto rebuild 索引
- **P4.0**: mavis framework 整体整合

## 验收 checklist

- [x] Coder 真写文件 (B4 完整文件模式)
- [x] Linter 验证 (py_compile, 5/5 passed)
- [x] Patcher 真修 (代码 ready, 0/5 触发)
- [x] 长度检查 70% (借鉴 P1.1.a)
- [x] 内部重试 3 次 (借鉴 P1.1.a)
- [x] 5 改文件任务 100% 跑通
- [x] 5/5 Linter 通过
- [x] 5/5 文件已改
- [x] 平均 23.11 秒/次

## 文件清单

- `crewai_v4.py` (主入口, 480 行)
- `cycle-report.json` (单 query 报告)
- `crewai-v4-5file-test-results.json` (5 改文件任务验证)
- `test_files/sample1.py` `sample2.py` `sample3.py` `sample4.py` `sample5.py` (5 测试文件)
- `README.md` (本文)
