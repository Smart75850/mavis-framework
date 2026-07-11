#!/usr/bin/env python3
"""
P6.6 Qwen-7B-Instruct 下载 (永久 invariant #93)
- ModelScope 镜像替代 HuggingFace Hub
- 14GB, 96GB Mac 完全胜任
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# 避 proxy
for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

# 用 LLaMA-Factory venv (有 modelscope)
sys.path.insert(0, '/Users/apple/workspace/LLaMA-Factory/.venv/lib/python3.12/site-packages')

from modelscope import snapshot_download


def main():
    print("=" * 70)
    print("P6.6 Qwen-7B-Instruct ModelScope 下载 (永久 invariant #93)")
    print("=" * 70)
    print()
    print("开始时间:", datetime.now().isoformat())
    print("目标模型: qwen/Qwen2-7B-Instruct (14GB)")
    print("缓存路径: /tmp/ms_cache/models/")
    print()

    start = time.time()

    # 关键: ModelScope 国内可用, 避开 HuggingFace 网络限制
    model_dir = snapshot_download(
        'qwen/Qwen2-7B-Instruct',
        cache_dir='/tmp/ms_cache',
        revision='master',
    )

    elapsed = time.time() - start
    print()
    print(f"下载完成: {model_dir}")
    print(f"耗时: {elapsed:.1f} 秒 ({elapsed / 60:.1f} 分钟)")

    # 检查文件大小
    total_size = 0
    for root, dirs, files in os.walk(model_dir):
        for f in files:
            fp = os.path.join(root, f)
            total_size += os.path.getsize(fp)
    print(f"总大小: {total_size / 1024 / 1024 / 1024:.2f} GB")

    # 写报告
    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P6.6 Qwen-7B-Instruct ModelScope 下载",
        "model_dir": model_dir,
        "elapsed_s": round(elapsed, 1),
        "total_size_gb": round(total_size / 1024 / 1024 / 1024, 2),
        "files_count": len(list(Path(model_dir).rglob('*'))),
    }
    report_path = Path(__file__).parent / "qwen7b_download_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {report_path}")

    return model_dir


if __name__ == "__main__":
    main()
