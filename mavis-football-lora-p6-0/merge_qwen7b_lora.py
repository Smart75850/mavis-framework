#!/usr/bin/env python3
"""
P8.0 Qwen-7B + LoRA merge_and_unload 实战 (永久 invariant #97)
- 复用 P6.5 (#92) 实战模式, 升级到 Qwen-7B (14GB)
- 输出: qwen-7b-football-merged/ (Ollama 直接 import)
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(Path('/Users/apple/workspace/LLaMA-Factory/.venv/lib/python3.12/site-packages')))


def merge_lora(base_model: str, lora_path: str, output_dir: str):
    """merge_and_unload (永久 invariant #17 + #92 实战)"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    print(f"  加载 base model: {base_model}")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )

    print(f"  加载 LoRA adapter: {lora_path}")
    model = PeftModel.from_pretrained(model, lora_path)
    print(f"  merge_and_unload (永久 invariant #17)...")

    start = time.time()
    model = model.merge_and_unload()
    elapsed = time.time() - start
    print(f"  merge 耗时: {elapsed:.1f}s")

    print(f"  保存到: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir, safe_serialization=True)
    tokenizer.save_pretrained(output_dir)
    return {"elapsed_s": round(elapsed, 1), "output_dir": output_dir}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/tmp/ms_cache/models/qwen--Qwen2-7B-Instruct/snapshots/master")
    parser.add_argument("--lora", default=str(BASE / "qwen-7b-football-lora"))
    parser.add_argument("--output", default=str(BASE / "qwen-7b-football-merged"))
    args = parser.parse_args()

    print("=" * 70)
    print("P8.0 Qwen-7B + LoRA merge_and_unload 实战 (永久 invariant #97)")
    print("=" * 70)
    print()
    print(f"Base model: {args.model}")
    print(f"LoRA: {args.lora}")
    print(f"Output: {args.output}")
    print()

    result = merge_lora(args.model, args.lora, args.output)
    print()
    print("=" * 70)
    print(f"Merge 完成: {result}")
    print("=" * 70)

    # 写报告
    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P8.0 Qwen-7B + LoRA merge_and_unload",
        "base_model": args.model,
        "lora": args.lora,
        "output": args.output,
        "result": result,
    }
    report_path = BASE / "merge_7b_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
