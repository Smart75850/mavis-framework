#!/usr/bin/env python3
"""
P9.5 Ollama qwen-football-7b-200step 实战 chat 验证 (永久 invariant #99)
- 8 个真足球 query 实战 2025-26 季数据
- 实战体验 200 step 训练 + 2025-26 季 alpaca 实战
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

# 8 query 重点测试 2025-26 季数据 (永久 invariant #99 实战)
EXPERIENCE_QUERIES = [
    "2025-26 季英超射手榜前 5 系边个?",
    "2025-26 季西甲射手榜前 5 系边个?",
    "2025-26 季德甲射手榜前 5 系边个?",
    "凯恩 2025-26 季喺拜仁入咗几多球?",
    "C 朗 2024 年喺 Al Nassr 入咗几多球?",
    "2026 世界杯 8 强有边支队?",
    "姆巴佩 2025-26 季喺皇马入咗几多球?",
    "2025-26 欧冠射手榜排第一系边个?",
]


def ollama_chat(model: str, query: str, timeout: int = 120) -> tuple:
    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": model,
        "prompt": f"<|im_start|>user\n{query}<|im_end|>\n<|im_start|>assistant\n",
        "stream": False,
        "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 400},
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
    print("=" * 80)
    print("P9.5 Ollama qwen-football-7b-200step 实战 chat 验证 (永久 invariant #99)")
    print("=" * 80)
    print()
    print("Model: qwen-football-7b-200step (P9.3 训练, Qwen-7B + 200 step + 2025-26 季 390 条 alpaca)")
    print(f"Queries: {len(EXPERIENCE_QUERIES)} (重点 2025-26 季数据)")
    print()

    model = "qwen-football-7b-200step"
    results = []
    total_start = time.time()

    for i, query in enumerate(EXPERIENCE_QUERIES, 1):
        print(f"[{i}/{len(EXPERIENCE_QUERIES)}] Q: {query}")
        response, elapsed, error = ollama_chat(model, query)
        if error:
            print(f"  错误: {error}")
        else:
            print(f"  耗时 {elapsed:.1f}s")
            preview = response[:350].replace("\n", "\n  ")
            print(f"  A: {preview}")
            if len(response) > 350:
                print(f"  ... ({len(response) - 350} more chars)")
        print()
        results.append({
            "query": query,
            "response": response,
            "elapsed_s": round(elapsed, 1),
            "error": error,
        })

    total_elapsed = time.time() - total_start
    print("=" * 80)
    print(f"实战完成: {len(EXPERIENCE_QUERIES)} query, 总耗时 {total_elapsed:.1f}s")
    print("=" * 80)

    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P9.5 Ollama qwen-football-7b-200step 实战 chat 验证",
        "model": model,
        "training": "Qwen-7B + 200 step LoRA + 2025-26 季 390 条 alpaca",
        "test_count": len(EXPERIENCE_QUERIES),
        "total_elapsed_s": round(total_elapsed, 1),
        "results": results,
    }
    report_path = BASE / "ollama_experience_200step.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完整报告: {report_path}")


if __name__ == "__main__":
    main()
