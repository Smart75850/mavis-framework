#!/usr/bin/env python3
"""
P8.0 Ollama Qwen-7B 足球 chat 实战验证 (永久 invariant #97)
- 5 真 query 实战 chat 通过 Ollama HTTP API
- 预期: 真实足球 LoRA 风格化输出, 但数据准确度仍受 LoRA step 限制
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime

for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

BASE = Path(__file__).parent

TEST_QUERIES = [
    "曼联对利物浦历史对战 211 次, 边个胜多?",
    "2024-25 季英超射手榜前 5 系边个?",
    "凯恩 2024-25 季喺拜仁入咗几多球?",
    "5 大联赛争冠激烈程度对比, 边个最激烈?",
    "C 朗 2024 年喺 Al Nassr 入咗几多球?",
]


def ollama_chat(model: str, query: str, timeout: int = 120) -> tuple:
    """调 ollama generate API"""
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": model,
        "prompt": f"<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n",
        "stream": False,
        "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 300},
    }
    start = time.time()
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        elapsed = time.time() - start
        return data.get("response", ""), elapsed, ""
    except Exception as e:
        return "", time.time() - start, str(e)[:200]


def main():
    print("=" * 70)
    print("P8.0 Ollama Qwen-7B 足球 chat 实战验证 (永久 invariant #97)")
    print("=" * 70)
    print()
    print("Model: qwen-football-7b (Qwen-7B + LoRA merged via Ollama)")
    print(f"Queries: {len(TEST_QUERIES)}")
    print()

    model = "qwen-football-7b"
    results = []
    total_start = time.time()

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] Query: {query}")
        response, elapsed, error = ollama_chat(model, query)
        if error:
            print(f"  错误: {error}")
        else:
            preview = response[:200].replace("\n", " ")
            print(f"  耗时 {elapsed:.1f}s")
            print(f"  Response: {preview}...")
        results.append({
            "query": query,
            "response": response[:500],
            "elapsed_s": round(elapsed, 1),
            "error": error,
        })
        print()

    total_elapsed = time.time() - total_start
    print("=" * 70)
    print(f"P8.0 Ollama chat 实战完成: 5 query, 总耗时 {total_elapsed:.1f}s")
    print("=" * 70)

    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P8.0 Ollama Qwen-7B 足球 chat 实战",
        "model": model,
        "test_count": len(TEST_QUERIES),
        "total_elapsed_s": round(total_elapsed, 1),
        "results": results,
    }
    report_path = BASE / "ollama_qwen7b_chat_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
