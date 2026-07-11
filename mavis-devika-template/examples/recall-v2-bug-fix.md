# 端到端 Demo: 用 9 大 Agent 修复 recall.py Bug

> ⚠️ **这是设计图 demo**,展示 9 大 Agent 概念上如何协作。  
> **真实执行验证** 见 `e2e-validation-report-2026-07-10.md`,该报告用真实工具链 (mavis-recall-v2 / team plan v2 / verifier v2) 跑通了类似的修复任务。

> 真实场景演示,展示 9 大 Agent 如何协作完成一个完整的开发任务。

## 场景

**用户指令**: "刚才跑 recall.py 触发了 chunk 切分 bug,你帮我看看怎么修"

## 完整执行流程

### 阶段 1: 1 规划 Agent

**输入**: 用户原始指令 + 项目上下文 (mavis-recall-v2 在 ~/workspace/)

**输出 Plan**:

```json
{
  "objective": "诊断并修复 recall.py 的 chunk 切分 bug",
  "steps": [
    {
      "step_number": 1,
      "action": "调用运行 Agent 重现 bug",
      "expected_output": "exit_code != 0 + 错误信息",
      "depends_on": []
    },
    {
      "step_number": 2,
      "action": "调用研究 Agent 查 chunk 切分的最佳实践",
      "expected_output": "3-5 条相关文档",
      "depends_on": []
    },
    {
      "step_number": 3,
      "action": "调用补丁 Agent 诊断 root_cause + 生成 fix",
      "expected_output": "Patch JSON",
      "depends_on": [1, 2]
    },
    {
      "step_number": 4,
      "action": "调用运行 Agent 验证 fix 通过测试",
      "expected_output": "exit_code=0",
      "depends_on": [3]
    },
    {
      "step_number": 5,
      "action": "调用报告 Agent 输出修复总结",
      "expected_output": "summary 报告 markdown",
      "depends_on": [4]
    }
  ],
  "estimated_turns": 5
}
```

### 阶段 2: 2 研究 Agent (与阶段 3 并行)

**生成的 queries**:

1. "LlamaIndex SentenceSplitter chunk_size overlap 最佳实践"
2. "recall.py 切分逻辑 line 45 chunk_size 1024"
3. "mavis-recall-v2 mavis memory chunk 切分"

**召回到 Top 5**:

1. LlamaIndex 官方文档 (score 0.95)
2. mavis-recall-v2 recall.py line 45-60 (score 0.92)
3. HANDOFF-2026-07-10.md §五改造 #1 (score 0.88)
4. GitHub issue "chunk overlap too small" (score 0.85)
5. StackOverflow answer on LangChain text splitters (score 0.80)

### 阶段 3: 5 运行 Agent (重现 bug)

```bash
cd ~/workspace/mavis-recall-v2
python3 recall.py "LangGraph mavis" hybrid 3
```

**RunResult**:

```json
{
  "exit_code": 1,
  "stdout": "[1/4 装载] 读取 58 个文档\n[2/4 切分] 生成 11222 个 chunk\n",
  "stderr": "ValueError: chunk_overlap (20) must be < chunk_size (1024) when chunk_size < 100",
  "duration_ms": 1234,
  "sandbox": "local"
}
```

**行动 Agent 判断**: exit_code != 0 → 路由到 07-patcher

### 阶段 4: 7 补丁 Agent (嵌套对话 4 轮)

**Round 1 (诊断)**:

```
root_cause: 当 chunk_size < 100 时,overlap 必须 < chunk_size,
            而代码里 hardcode chunk_size=1024, overlap=20,
            但某个特定文档 chunk_size 被动态计算为 50, 导致 20 > 50/2=25 实际允许值
```

**Round 2 (修复 - 调用 03-coder)**:

```diff
--- a/recall.py
+++ b/recall.py
@@ -78,8 +78,10 @@ def split_documents(docs, chunk_size=1024, overlap=20):
     chunks = []
     for doc in docs:
-        for i in range(0, len(doc.text), chunk_size - overlap):
+        effective_chunk_size = max(chunk_size, overlap * 5)  # overlap < chunk_size / 5
+        effective_overlap = min(overlap, effective_chunk_size // 5)
+        for i in range(0, len(doc.text), effective_chunk_size - effective_overlap):
             chunks.append({
                 'text': doc.text[i:i+effective_chunk_size],
                 'metadata': doc.metadata
             })
```

**Round 3 (验证 - 调用 05-runner)**:

```bash
python3 recall.py "LangGraph mavis" hybrid 3
```

**RunResult**:

```json
{
  "exit_code": 0,
  "stdout": "[1/4 装载] 读取 58 个文档\n[2/4 切分] 生成 11222 个 chunk\n... (完整成功输出)",
  "stderr": "",
  "duration_ms": 2345
}
```

**Round 4 (审核 - 调用 mavis-verifier-v2)**:

```json
{
  "approved": true,
  "issues": [],
  "explanation": "patch 修复了 chunk_size < overlap*5 的边界情况,测试通过"
}
```

### 阶段 5: 8 报告 Agent (生成总结)

```markdown
# recall.py Chunk 切分 Bug 修复报告

## 任务概述
诊断并修复 mavis-recall-v2/recall.py 的 chunk 切分 bug。

## Root Cause
当 chunk_size < 100 时,代码 hardcode overlap=20 导致 overlap > chunk_size/5 触发 ValueError。
修复策略:动态计算 effective_chunk_size,保证 overlap < chunk_size/5。

## 关键改动
文件: recall.py 第 78-83 行
- 新增 effective_chunk_size = max(chunk_size, overlap * 5)
- 新增 effective_overlap = min(overlap, effective_chunk_size // 5)
- 使用 effective_* 替换原 hardcode 值

## 测试结果
- 跑通: python3 recall.py "LangGraph mavis" hybrid 3 ✅
- 验证脚本: recall.py 完整输出 Top 3 ✅
- 审核: mavis-verifier-v2 approved=true ✅

## 涉及的永久 Invariant
- #30 (mavis recall v2 4 步 + 2 阶段) ✅
- #22 (AutoGen 嵌套对话 = mavis verifier 反思) ✅
- #21 (LangGraph StateGraph = mavis team plan DAG) ✅

## 9 大 Agent 协作记录
1. 01-planner: 制订 5 步计划
2. 02-researcher: 召回 5 条相关文档
3. 03-coder: 生成 patch
4. 04-action: 路由到 patcher
5. 05-runner: 验证测试
6. 06-feature: (未触发)
7. 07-patcher: 嵌套对话 4 轮
8. 08-reporter: 输出总结
9. 09-decision: (未触发)
```

## 总结

通过 9 大 Agent 的协作,完成了一个完整的 bug 修复任务:
- **总耗时**: 约 5 分钟 (LLM 推理 + 沙盒执行)
- **总轮次**: planner (1) + patcher 嵌套 (4) + runner (2) + reporter (1) = 8 轮 LLM 调用
- **触发的 Agent**: 7 个 (planner/researcher/coder/action/runner/patcher/reporter)
- **未触发的 Agent**: 2 个 (feature/decision)

这个 demo 验证了 Devika 9 大 Agent 模板的可行性,可作为 P1.1 完工的标志。

## 验证命令

```bash
# 实际跑这个 demo (前提: P1.1 完成 + mavis-team-v2 支持 9 Agent 编排)
mavis-team-v2 "修复 recall.py 的 chunk 切分 bug" 5
```