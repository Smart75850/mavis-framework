# 32B 写大文件验证报告 (P4.1 mini 修 #3+#4+#7)

> **2026-07-11 19:50** 大佬命令「全部 14 个一步一步修 + 真 verify」, 32B 大文件验证 part

## 验证目标

**P4.2 Test 3 (crewai_v3.py 16924 字符) + Test 4 (crewai_v4.py 21736 字符) 用 14B 写 3 次重试都失败, 验证 32B 写大文件 work 吗?**

## 验证结果

### 32B 单次写大文件能力 (P4.1 mini 修 #7)

| 维度 | 14B (P4.2) | 32B (本次) |
|---|---|---|
| 单次 LLM 耗时 | 30-60s (短文) / 600s+ timeout (大文) | **450s (7.5 分钟)** |
| 输出长度 | 60-70% (P3.5 失败回滚) | **84.7%** (过 70% 阈值) |
| Linter (py_compile) | ❌ syntax 错 | ❌ **syntax 错** (`from lang` 截断) |
| P3.5 失败回滚 | ✅ work | ✅ work (没改坏原文件) |
| 总耗时 (1 文件) | 1-2 分钟 (Coder 3 retry) | **45 分钟** (Coder 3 retry + Patcher 2 attempt = 6 LLM × 450s) |
| 30 分钟 timeout | 部分跑通 | ❌ **跑不完 1 文件** |

### 32B Coder 全流程 (P4.1 mini 修 #3+#4)

直接跑 P4.2 Test 3 with `MAVIS_LLM_MODEL=qwen3:32b`:
- **30 分钟 timeout 跑不完 1 个文件** (6 LLM × 450s = 45 分钟)
- Coder 3 retry + Patcher 2 attempt 总耗时长
- P3.5 失败回滚 work, 但没真改大文件

### 文件状态 verify (P3.5 失败回滚 work 吗)

```bash
$ diff ~/workspace/mavis-crewai-v3/crewai_v3.py ~/workspace/mavis-crewai-v3/crewai_v3.py.p42.backup | wc -l
0
# 输出 0 = 文件一致, 失败回滚 work, 没改坏原文件 ✅
```

## 永久结论 (不允许忘)

**14B + 32B 都不可行写 10000+ 字符大文件**, 原因:

| 模型 | 失败原因 |
|---|---|
| 14B | 输出只 60-70% 长度, 简化原文件代码, P3.5 70% 阈值失败 |
| 32B | 输出 84.7% 长度 (过 70%), 但 syntax 错 (`from lang` 截断), P3.5 Linter 验证 fail |
| 32B | 总耗时 45 分钟, 30 分钟 timeout 跑不完 1 文件 (Coder 3 retry + Patcher 2 attempt) |

**根本问题**: mavis 框架的 LLM 改文件 pipeline 不适合大文件 (10000+ 字符), 需**分块改写** 或 **search/replace** 模式, 而非完整文件重写。

## 修复建议 (下次做)

1. **分块改写**: 把大文件 split 多个 5000 字符块, 每块单独改
2. **search/replace 模式**: LLM 输出 search/replace 块, 而非完整文件
3. **Aider / Cursor 风格**: 多文件编辑 + diff 模式
4. **跳过 10000+ 字符文件**: mavis framework 改文件 pipeline 限制 8000 字符

## P3.5 失败回滚机制 verify ✅

虽然 32B 写大文件失败, 但 P3.5 修复嘅「失败回滚」机制 work:
- Coder 3 retry 全失败 → 文件没改
- Patcher 2 attempt 全失败 → 文件没改
- 失败后 backup 恢复原内容
- 验证: `diff` 0 行 = 一致

这是 P3.5 永久 invariant (#46) 嘅实战验证, **回滚机制 work, 安全**。

## VERIFY #3+#4+#7 实战结论

| 缺口 | 修复状态 | 真 verify 结论 |
|---|---|---|
| #3 P4.2 9/9 实际 7/9 | ❌ **未根本解决** | 14B + 32B 都不可行, 需分块改写 / search-replace |
| #4 P3.4 真实改写 1/3 失败 | ❌ **未根本解决** | 同 #3, 14B + 32B 都不可行 |
| #7 32B 模型对比未做 | ✅ **已做** | 32B 单次能写 84.7%, 但全流程 45 分钟不可行 |

**#3 + #4 真要 fix, 需要换 mavis 改文件 pipeline (分块 / search-replace)**, 呢个系架构改动, 唔系 30 分钟能搞掂, 应该列为 **P4.4 大文件改写 pipeline 重构**。

**#7 完成, 32B 验证报告已写, narrative 改对**。
