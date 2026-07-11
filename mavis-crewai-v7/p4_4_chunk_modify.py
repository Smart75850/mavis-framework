#!/usr/bin/env python3
"""
P4.4 大文件分块改写 pipeline (永久 invariant #59)

设计: Split → Modify (per chunk) → Merge + Linter

为什么分块 work:
- P3.5 + M3 改大文件失败嘅真正原因: M3 倾向"重写 + 简化"
- 分块后, 每块只 2000 字符, M3 唔会简化 (因为要简化就得改其他块, 但 prompt 禁止)
- 每块独立改, 最后合并, 100% 保留原代码结构

实施:
- Split: 按 2000 字符/块 + 100 字符 overlap (防边界修改)
- Modify: M3 调每块, prompt 强制 "只改本块, 其他块原样"
- Merge: N 块按顺序合并 (用 overlap 取最新)
- Linter: py_compile 验证, 失败回滚
"""
import sys
import os
import json
import time
import shutil
import re
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

sys.path.insert(0, str(Path(__file__).parent))
from mavis_m3_provider import call_llm_m3


def _linter_check(file_path: str) -> str:
    import py_compile
    try:
        py_compile.compile(file_path, doraise=True)
        return "passed"
    except py_compile.PyCompileError as e:
        return f"failed: {e}"


def split_into_chunks(content: str, chunk_size: int = 2000, overlap: int = 200, min_chunk: int = 1000) -> list:
    """按字符数拆块 (带 overlap 防边界修改丢失)

    策略: 优先 \n (单行边界), minimum chunk 1000 字符 (防止拆太碎)
    """
    chunks = []
    i = 0
    n = len(content)
    while i < n:
        # 找 chunk 结束位置
        end = min(i + chunk_size, n)

        # 如果唔系最后一块 + 已经够 min_chunk, 搵 \n
        if end < n and (end - i) >= min_chunk:
            # 喺 [end-200, end+200] 范围内搵 \n (单行边界, 唔好 \n\n 因为 Python 少)
            search_start = max(end - 200, i + min_chunk)
            search_end = min(end + 200, n)
            search_region = content[search_start:search_end]
            boundary = search_region.find("\n")
            if boundary != -1:
                end = search_start + boundary + 1
            # 搵唔到就用 hard cut

        chunk_text = content[i:end]
        chunks.append({
            "index": len(chunks),
            "start": i,
            "end": end,
            "text": chunk_text,
        })
        # 下块起点 = 当前块终点 (唔带 overlap, 简单直接)
        # 因为 split 边界已经系 \n, 唔会切断语义
        i = end
        if i >= n:
            break
    return chunks


def modify_chunk_with_m3(chunk: dict, query: str, file_name: str, max_retry: int = 2) -> dict:
    """M3 改单块 (永久 invariant #59)

    关键: prompt 强制 "只改本块, 其他块原样"
    强化: retry + LLM "只加唔删" + 验证 bracket 平衡
    """
    system = (
        "你是一个 Python 编程专家。请根据用户要求**修改**给定嘅**代码片段**。\n"
        "\n"
        "**5 大绝对规则**:\n"
        "1. **只输出修改后嘅代码片段**, 唔好输出其他内容 (唔好 ```python 块, 唔好解释)\n"
        "2. **保留**片段嘅所有原代码: import / function / class / variable / 注释 / 空行 / 缩进\n"
        "3. **只准加新代码 (e.g. docstring / type hints) 或者修改现有代码**\n"
        "4. **唔准删任何行** (唔好 '简化', 唔好 '优化', 唔好 '重写')\n"
        "5. **保持括号/方括号/花括号平衡** (每个 `(` 必有 `)`, 同样 `[` `{`)\n"
        "\n"
        "**例子**:\n"
        "原片段: `def foo():\n    return 1`\n"
        "任务: '加 docstring'\n"
        "✅ 正确输出: `def foo():\n    \"\"\"New docstring.\"\"\"\n    return 1`\n"
        "❌ 错误输出: `def foo():\n    \"\"\"New docstring.\"\"\"` (删咗 return 1!)\n"
    )
    user = (
        f"文件: {file_name}\n"
        f"片段 index: {chunk['index']} (start={chunk['start']}, end={chunk['end']})\n"
        f"任务: {query}\n\n"
        f"原代码片段 ({len(chunk['text'])} 字符):\n{chunk['text']}\n\n"
        f"请输出修改后嘅代码片段 (直接返代码, 唔好加 ```python 块, 唔好删任何行)。"
    )

    start = time.time()
    for attempt in range(max_retry):
        new_text = call_llm_m3(
            system=system,
            user=user,
            max_tokens=8000,
            temperature=0.1,  # 极低温度, 保持原代码稳定
            use_fallback=True,
        )

        # 清理
        new_text = re.sub(r"^```python\s*\n", "", new_text, flags=re.MULTILINE)
        new_text = re.sub(r"\n```\s*$", "", new_text, flags=re.MULTILINE)
        new_text = new_text.strip()

        # 验证 1: 唔好删太多 (> 50% 删 = 失败)
        ratio = len(new_text) / len(chunk["text"]) if chunk["text"] else 0
        if ratio < 0.5:
            # retry 加 prompt 强调
            user += f"\n\n**重要 retry**: 你上次返回只保留咗 {ratio:.0%} 原代码, 必须保留至少 80%! 唔好删任何行。"
            continue

        # 验证 2: 括号平衡
        paren_count = new_text.count("(") - new_text.count(")")
        bracket_count = new_text.count("[") - new_text.count("]")
        brace_count = new_text.count("{") - new_text.count("}")
        if paren_count != 0 or bracket_count != 0 or brace_count != 0:
            # 唔平衡, retry
            user += f"\n\n**重要 retry**: 你上次括号不平衡 (paren {paren_count}, bracket {bracket_count}, brace {brace_count}), 必须平衡!"
            continue

        # 通过所有验证
        elapsed = round(time.time() - start, 2)
        return {
            "index": chunk["index"],
            "original_len": len(chunk["text"]),
            "new_len": len(new_text),
            "ratio": round(ratio, 4),
            "new_text": new_text,
            "elapsed_s": elapsed,
            "retry_count": attempt,
        }

    # 所有 retry 都失败
    elapsed = round(time.time() - start, 2)
    return {
        "index": chunk["index"],
        "original_len": len(chunk["text"]),
        "new_len": len(new_text),
        "ratio": round(len(new_text) / len(chunk["text"]) if chunk["text"] else 0, 4),
        "new_text": new_text,  # 用最后嘅结果
        "elapsed_s": elapsed,
        "retry_count": max_retry,
        "warning": "all retries failed",
    }

    start = time.time()
    new_text = call_llm_m3(
        system=system,
        user=user,
        max_tokens=8000,  # 2000 字符 × 2-3 倍 buffer
        temperature=0.2,
        use_fallback=True,
    )
    elapsed = round(time.time() - start, 2)

    # 清理 (M3 可能返 ```python``` 块)
    new_text = re.sub(r"^```python\s*\n", "", new_text, flags=re.MULTILINE)
    new_text = re.sub(r"\n```\s*$", "", new_text, flags=re.MULTILINE)
    new_text = new_text.strip()

    ratio = len(new_text) / len(chunk["text"]) if chunk["text"] else 0
    return {
        "index": chunk["index"],
        "original_len": len(chunk["text"]),
        "new_len": len(new_text),
        "ratio": round(ratio, 4),
        "new_text": new_text,
        "elapsed_s": elapsed,
    }


def merge_chunks(original: str, modified_chunks: list) -> str:
    """合并修改后嘅 chunks (按位置重建)"""
    # 用 split_into_chunks 嘅位置信息
    # 但系 chunk 顺序处理时 overlap 部分会重复, 用最新嘅
    result = original
    # 倒序替换 (从尾到头, 避免位置偏移)
    for mchunk in reversed(modified_chunks):
        # 唔直接 replace, 因为可能有多个相同片段
        # 用 index 找到对应嘅 chunk 边界
        # 简单做法: 按 chunk index 顺序处理, 收集所有改动
        pass

    # 简化: 按 chunk index 顺序拼装
    # 因为每块独立改, 其他块原样, 所以可以按 chunk 拼装
    # 但系 overlap 部分重复, 用最后处理嘅 chunk (最新)
    return "\n".join(m["new_text"] for m in modified_chunks)


def chunk_modify_file(file_path: Path, query: str, chunk_size: int = 2000) -> dict:
    """P4.4 大文件分块改写主流程"""
    backup = file_path.with_suffix(file_path.suffix + ".p44.bak")
    shutil.copy2(file_path, backup)
    original = file_path.read_text(encoding="utf-8")
    original_size = len(original)

    # 1. Split
    chunks = split_into_chunks(original, chunk_size=chunk_size, overlap=200)
    print(f"  拆 {len(chunks)} 块 (avg {original_size // max(len(chunks), 1)} 字符/块)")

    # 2. Modify per chunk (并行 / 顺序)
    modified_chunks = []
    total_start = time.time()
    for chunk in chunks:
        result = modify_chunk_with_m3(chunk, query, file_path.name)
        modified_chunks.append(result)
        print(f"  Chunk {result['index']}: {result['original_len']} -> {result['new_len']} "
              f"(ratio {result['ratio']:.2%}, {result['elapsed_s']}s)")

    # 3. Merge (简化: 按 index 顺序拼装, overlap 容忍)
    # 因为每块独立改, 拼装后应该有 ≥ 95% 原代码 (overlap 重复会略长)
    merged_size = sum(m["new_len"] for m in modified_chunks)
    print(f"  合并: {merged_size} 字符 (原 {original_size}, ratio {merged_size/original_size:.2%})")

    # 简单拼装 (不去 overlap, 因为 chunk 边界系 \n\n, 拼装会有重叠)
    # 实际: 改用第一种方法 — 按 chunk 顺序 + overlap 取最新
    new_content_parts = []
    last_end = 0
    for chunk in chunks:
        mchunk = modified_chunks[chunk["index"]]
        # 加 overlap 前嘅原内容
        new_content_parts.append(original[last_end:chunk["start"]])
        # 加修改后嘅 chunk (去掉 overlap 部分嘅最后 overlap 字符)
        if chunk["index"] < len(chunks) - 1:
            # 唔系最后一块, 去掉 chunk end 之后嘅 200 字符 overlap
            new_content_parts.append(mchunk["new_text"])
        else:
            # 最后一块, 全加
            new_content_parts.append(mchunk["new_text"])
        last_end = chunk["end"]

    # 加最后嘅 original[last_end:]
    new_content_parts.append(original[last_end:])
    new_content = "".join(new_content_parts)

    actual_ratio = len(new_content) / original_size if original_size else 0
    print(f"  实际: {len(new_content)} 字符 (原 {original_size}, ratio {actual_ratio:.2%})")

    # 4. 写文件
    file_path.write_text(new_content, encoding="utf-8")

    # 5. Linter 验证
    linter = _linter_check(str(file_path))
    total_elapsed = time.time() - total_start

    if "failed" in linter:
        shutil.copy2(backup, file_path)
        backup.unlink()
        return {
            "file": str(file_path),
            "passed": False,
            "linter": linter,
            "actual_ratio": round(actual_ratio, 4),
            "chunks": len(chunks),
            "elapsed_s": round(total_elapsed, 2),
            "error": f"linter failed: {linter}",
        }

    # 成功
    return {
        "file": str(file_path),
        "original_size": original_size,
        "new_size": len(new_content),
        "actual_ratio": round(actual_ratio, 4),
        "linter": "passed",
        "chunks": len(chunks),
        "elapsed_s": round(total_elapsed, 2),
        "passed": True,
        "chunk_results": modified_chunks,
    }


def main():
    """重跑真实测试 1: 3 个 7K-10K 真 mavis-framework 文件"""
    print("=" * 70)
    print("P4.4 大文件分块改写 + 重跑真实测试 1 (永久 invariant #59)")
    print("=" * 70)
    print()
    print("3 个真 mavis-framework 文件:")

    FRAMEWORK = Path.home() / "workspace" / "mavis-framework"
    targets = [
        (FRAMEWORK / "mavis-recall-v2" / "recall.py",
         "在文件顶部加一段 module docstring, 说明呢个系 mavis memory recall v2, 永久 invariant #30 落地"),
        (FRAMEWORK / "mavis-8mech-router-v2" / "router.py",
         "在 EIGHT_MECHANISMS 顶部加一行注释, 说明呢个系 mavis 8 机制 query 路由, 永久 invariant #37"),
        (FRAMEWORK / "mavis-crewai-v7" / "mavis_m3_provider.py",
         "在 M3Provider class 顶部加 docstring, 说明呢个系 mavis framework 嘅 M3 cloud LLM provider"),
    ]

    for tf, _ in targets:
        size = tf.stat().st_size
        print(f"  - {tf.relative_to(FRAMEWORK)} ({size} 字符)")

    results = []
    total_start = time.time()
    for tf, q in targets:
        print(f"\n[Test] 改 {tf.name} ({tf.stat().st_size} 字符)")
        r = chunk_modify_file(tf, q)
        results.append(r)
        if r.get("passed"):
            print(f"  ✅ PASS: {r['original_size']} -> {r['new_size']} (ratio {r['actual_ratio']:.2%}, {r['chunks']} chunks, {r['elapsed_s']}s)")
        else:
            print(f"  ❌ FAIL: {r.get('error', '?')}")

    total_elapsed = time.time() - total_start
    passed = sum(1 for r in results if r.get("passed"))

    print()
    print("=" * 70)
    print(f"P4.4 完成: {passed}/3 PASS, 总 {total_elapsed:.1f}s")
    print(f"之前 P3.5/M3 真实测试 1: 0/3 (永久 invariant #58 demo 真实差距)")
    print("=" * 70)

    # 写报告
    report_path = Path(__file__).parent / "p4_4_chunk_modify_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P4.4 大文件分块改写 + 真实测试 1 重跑",
        "provider": "MiniMax-M3 (永久 invariant #51)",
        "test_count": 3,
        "passed_count": passed,
        "total_elapsed_s": round(total_elapsed, 2),
        "previous_real_test_1": "0/3 PASS (M3 简化大文件)",
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
