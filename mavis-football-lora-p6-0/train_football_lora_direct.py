#!/usr/bin/env python3
"""
P6.4 直接 transformers + peft 训练 Qwen LoRA (永久 invariant #91)

实战: LLaMA-Factory 0.9.6 trainer stall, 改用 transformers + peft 直接训练
- 兼容性 100% (避开 LLaMA-Factory + transformers 5.7 问题)
- 实战可控, 步骤清晰
- Mac 96GB 完全胜任
"""
import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['all_proxy'] = ''
os.environ['ALL_PROXY'] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(Path('/Users/apple/workspace/LLaMA-Factory/.venv/lib/python3.12/site-packages')))


def train_lora(model_path: str, data_path: str, output_dir: str, max_steps: int = 100, lora_rank: int = 16):
    """实战 Qwen LoRA 训练 (transformers + peft)"""
    import torch
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, TrainingArguments,
        Trainer, DataCollatorForLanguageModeling
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from datasets import Dataset

    print(f"  加载 model: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float32,  # CPU 用 float32, GPU 用 bfloat16
        trust_remote_code=True,
    )

    print(f"  准备 LoRA 配置 (rank={lora_rank})")
    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_rank * 2,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # 准备数据
    print(f"  加载数据: {data_path}")
    raw_data = [json.loads(line) for line in open(data_path)]
    print(f"    数据: {len(raw_data)} 条")

    def format_example(ex):
        text = f"### 指令: {ex['instruction']}\n"
        if ex.get('input'):
            text += f"### 输入: {ex['input']}\n"
        text += f"### 回答: {ex['output']}{tokenizer.eos_token}"
        return text

    # Tokenize 数据
    def tokenize_fn(ex):
        text = format_example(ex)
        result = tokenizer(text, truncation=True, max_length=512, padding="max_length")
        result["labels"] = result["input_ids"].copy()
        return result

    print(f"  Tokenize 数据")
    tokenized_data = [tokenize_fn(ex) for ex in raw_data]
    dataset = Dataset.from_list(tokenized_data)

    # Training args
    training_args = TrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        num_train_epochs=3,
        learning_rate=2e-4,
        max_steps=max_steps,  # 限制 step 数
        logging_steps=2,
        save_steps=50,
        save_total_limit=2,
        fp16=False,  # CPU
        bf16=False,
        report_to="none",
        use_cpu=True,
        remove_unused_columns=False,
        warmup_steps=2,
    )

    # Trainer
    print(f"  开始训练 (max_steps={max_steps})")
    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=data_collator,
    )

    start = time.time()
    trainer.train()
    elapsed = time.time() - start

    # 保存 LoRA
    print(f"  保存 LoRA 到: {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    return {"elapsed_s": round(elapsed, 2), "output_dir": output_dir, "max_steps": max_steps}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/tmp/ms_cache/models/qwen--Qwen2-1.5B-Instruct/snapshots/master",
                        help="Qwen model path")
    parser.add_argument("--data", default=str(BASE / "football_alpaca_100plus_train.jsonl"),
                        help="Training data path")
    parser.add_argument("--output", default=str(BASE / "qwen-1.5b-football-lora"),
                        help="Output dir")
    parser.add_argument("--max-steps", type=int, default=20, help="Max training steps")
    parser.add_argument("--lora-rank", type=int, default=16, help="LoRA rank")
    args = parser.parse_args()

    print("=" * 70)
    print("P6.4 直接 transformers + peft 训练 Qwen LoRA (永久 invariant #91)")
    print("=" * 70)
    print()
    print(f"Model: {args.model}")
    print(f"Data: {args.data}")
    print(f"Output: {args.output}")
    print(f"Max steps: {args.max_steps}, LoRA rank: {args.lora_rank}")
    print()

    result = train_lora(args.model, args.data, args.output, args.max_steps, args.lora_rank)
    print()
    print("=" * 70)
    print(f"训练完成: {result}")
    print("=" * 70)

    # 写报告
    report_path = BASE / "lora_direct_train_results.json"
    report_path.write_text(json.dumps({
        "test_at": datetime.now().isoformat(),
        "test_name": "P6.4 直接 transformers + peft 训练",
        "model": args.model,
        "data": args.data,
        "output": args.output,
        "result": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
