#!/usr/bin/env python3
"""
Ollama qwen-football-7b (20 step) 实战 chat 体验
- 8 个真足球 query 实战 (覆盖 P7 实战 query + 新 query)
- 实战体验, 报告 + transcript 完整记录
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

# 8 个真足球 query
EXPERIENCE_QUERIES = [
    "曼联对利物浦历史对战 211 次, 边个胜多?",
    "2024-25 季英超射手榜前 5 系边个?",
    "凯恩 2024-25 季喺拜仁入咗几多球?",
    "5 大联赛争冠激烈程度对比, 边个最激烈?",
    "C 朗 2024 年喺 Al Nassr 入咗几多球?",
    "曼城 4-3-3 阵型有咩特点?",
    "皇马快速反击战术点样运作?",
    "姆巴佩 2024 年加盟咗边支队?",
]


def ollama_chat(model: str, query: str, timeout: int = 120) -> tuple:
    """调 ollama generate API"""
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
    print("Ollama qwen-football-7b (20 step LoRA) 实战 chat 体验")
    print("=" * 80)
    print()
    print("Model: qwen-football-7b (P8.0 部署, Qwen-7B + 20 step 足球 LoRA)")
    print(f"Queries: {len(EXPERIENCE_QUERIES)}")
    print()

    model = "qwen-football-7b"
    results = []
    total_start = time.time()

    for i, query in enumerate(EXPERIENCE_QUERIES, 1):
        print(f"[{i}/{len(EXPERIENCE_QUERIES)}] Q: {query}")
        response, elapsed, error = ollama_chat(model, query)
        if error:
            print(f"  错误: {error}")
        else:
            print(f"  耗时 {elapsed:.1f}s")
            # 输出前 350 字 (避太长)
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
    print(f"实战体验完成: {len(EXPERIENCE_QUERIES)} query, 总耗时 {total_elapsed:.1f}s")
    print("=" * 80)

    # 写报告 (含完整 transcript)
    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "Ollama qwen-football-7b (20 step) 实战 chat 体验",
        "model": model,
        "test_count": len(EXPERIENCE_QUERIES),
        "total_elapsed_s": round(total_elapsed, 1),
        "results": results,
    }
    report_path = BASE / "ollama_experience_20step.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完整报告: {report_path}")


if __name__ == "__main__":
    main()
