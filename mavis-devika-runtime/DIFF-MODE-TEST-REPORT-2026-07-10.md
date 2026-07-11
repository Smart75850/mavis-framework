# Diff 模式真实测试报告 (2026-07-10)

> 真实尝试用 9 Agent runtime 给 recall.py 加 save_results 参数。**结果: 没成功**。

---

## 1. 真实进展

### 1.1 runtime.py 改造 (成功)

| 改造 | 状态 | 说明 |
|------|------|------|
| Coder 输出 diff 而非完整文件 | ✅ | 改 system prompt, 要求 ```diff 块 |
| 提取 diff (regex) | ✅ | `_extract_diff()` 工具函数 |
| 应用 diff (patch 命令) | ✅ | `_apply_diff_with_patch()` 工具函数 |
| dry_run 验证 | ✅ | `--dry-run` 模式先验证 |
| syntax check | ✅ | `py_compile.compile()` |
| Runner 加 verify_pattern | ✅ | 检查 stdout 关键字段, 失败时强制 exit_code=1 |

### 1.2 真实场景测试 (失败但有价值)

**任务**: 给 recall.py 加 save_results 参数
**工具链**: Planner → Researcher → Coder → Runner → Reporter

**真实结果**:

| 步骤 | 真实发生 |
|------|---------|
| 01 Planner | 生成 3 步计划 (argparse 改造等) |
| 02 Researcher | 真实调 mavis-recall-v2 (exit 0) |
| 03 Coder | **生成了 malformed diff** → patch 命令拒绝 (`malformed patch at line 19: +`) → dry_run 失败 → 文件未修改 |
| 05 Runner | 真实跑 import 测试 → stdout: `save_results in signature: False` |
| 05 Runner (改进后) | 加 verify_pattern 后, stdout 不包含 `save_results in signature: True` → exit_code 强制改 1 |
| 07 Patcher | 触发 verifier v2 (慢) |
| ... | **超时 600s, 被自动 kill, 陷入循环** |

---

## 2. 暴露的真实问题

### 问题 1: LLM 生成 unified diff 不规范 ⭐⭐⭐ (根本问题)

**现象**: LLM 输出 diff 时,上下文行或添加行的格式不对,导致 patch 命令拒绝

**例子**: LLM 输出 `@@ -143,7 +143,7 @@` 但实际只改了 5 行,导致 patch 计数不匹配

**根本原因**: LLM 是用统计模式生成 diff,不真正理解 unified diff 规范的细节

**解决方向**:
1. **更严格的 prompt**: 加 1 个完整 diff 示例 (3000 字符)
2. **重试机制**: Coder 失败 → 自动重试最多 3 次, 每次附上 patch 错误信息
3. **改用别的格式**: 比如用 JSON 描述改动 (old_text / new_text / line_number), 自己生成 diff
4. **更小的改动**: 任务拆得更细, 每次只改 1 行

### 问题 2: Runner 之前只看 exit_code (已修)

**现象**: 即使 stdout 显示 `save_results in signature: False`,Runner 也认为成功

**修复**: 加 `verify_pattern` 参数, Runner 检查 stdout 必须包含指定字符串, 否则强制 exit_code=1

### 问题 3: Patcher 触发后可能循环 (待观察)

**现象**: verify_pattern 模式下, Patcher 触发 → verifier 给建议 → 但 Patcher 没真正应用建议 (MVP 模式只记录) → 回到 Runner → 还是失败 → 循环

**解决方向**:
1. **Patcher 真实应用 verifier 建议**: 从 verifier 输出提取代码块, 写文件
2. **Patcher 改 prompt 而不是 Coder**: 让 Patcher 输出更具体的修复 diff
3. **加循环限制**: max_turns 强制到上限 (已经做了,但 600s 超时不够)

---

## 3. 真实文件状态

```
/Users/apple/workspace/mavis-recall-v2/recall.py (原版, 9976 字节, 246 行, 未修改)
   ↓ 上次改造前备份
recall.py.bak.before-devika (保留, 9976 字节)
```

---

## 4. 接下来该怎么做 (给大佬选)

| 选项 | 工作量 | 价值 | 风险 |
|------|-------|------|------|
| **B1: Coder 加重试机制** | 1-2 小时 | 高,根治 diff 生成问题 | 中,可能重试也失败 |
| **B2: 简化场景(单行修改)** | 30 分钟 | 中,先验证框架 | 低,但价值有限 |
| **B3: Patcher 真实应用建议** | 2-3 小时 | 高,补齐最后一环 | 中,verifier 输出格式也要改 |
| **B4: 改用 JSON 描述改动** | 3-4 小时 | 高,绕开 diff 格式 | 高,等于重写 Coder |

**我的建议**: 先 B2 验证框架 (30 分钟),然后看具体哪个环节卡住,再针对性做 B1 或 B3。

---

## 5. 真实价值总结

虽然没成功加 save_results,但端到端跑通的过程中**真实发现了 3 个工程问题**:

1. **LLM 不可靠生成 unified diff** (根本限制)
2. **Runner 不验证实际效果** (已修)
3. **Patcher 没真实应用修复** (待修)

这些问题是**真实做事的副产品**,不是设计缺陷,需要在工程实践中一个个解决。这就是"假端到端"和"真端到端"的区别 — 假端到端永远 happy path,真端到端暴露问题。

**当前 runtime 的真实能力**:
- ✅ 框架 OK (LangGraph StateGraph, 9 节点, 2 条件边, MemorySaver)
- ✅ 集成 OK (recall v2 + verifier v2)
- ✅ 写文件 OK (diff 模式基础)
- ⚠️ 写正确代码 不行 (LLM 不擅长生成规范 diff)
- ⚠️ 自动修复 不行 (Patcher 是 MVP)

**差距**: 距"真正能解决问题"还差 2-3 天针对性优化 (重试 + 真实 Patcher + prompt 调优)。