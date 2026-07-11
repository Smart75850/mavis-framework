#!/usr/bin/env python3
"""
P6.6 Qwen-7B 足球 LoRA 真训练 verify (永久 invariant #94)
- 5 真 query 验证 (M3 评估 PASS/FAIL)
- 预期 4-5/5 PASS (vs Qwen-1.5B 0/5 实战限制)
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

# 5 真 query (足球 LoRA 实战测试)
TEST_QUERIES = [
    "曼联对利物浦历史对战 211 次, 边个胜多?",
    "2024-25 季英超射手榜前 5 系边个?",
    "凯恩 2024-25 季喺拜仁入咗几多球?",
    "5 大联赛争冠激烈程度对比, 边个最激烈?",
    "C 朗 2024 年喺 Al Nassr 入咗几多球?",
]


def verify_with_lora(base_model_path: str, lora_path: str, query: str, max_new_tokens: int = 256) -> str:
    """用 LoRA 实战推理 (永久 invariant #94)"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"    加载 base model: {base_model_path}")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float32,
        trust_remote_code=True,
    )

    print(f"    加载 LoRA adapter: {lora_path}")
    model = PeftModel.from_pretrained(model, lora_path)
    model.eval()

    # 准备输入
    prompt = f"### 指令: {query}\n### 回答: "
    inputs = tokenizer(prompt, return_tensors="pt")

    print(f"    推理 (max_new_tokens={max_new_tokens})")
    start = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            temperature=1.0,
            top_p=1.0,
            num_beams=1,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    elapsed = time.time() - start

    response = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    print(f"    推理耗时: {elapsed:.1f}s")

    # 清理
    del model
    del tokenizer
    import gc
    gc.collect()

    return response


def evaluate_with_m3(query: str, response: str) -> bool:
    """M3 评估 PASS/FAIL (永久 invariant #51)"""
    try:
        sys.path.insert(0, '/Users/apple/workspace/mavis-framework/mavis-crewai-v7')
        from mavis_m3_provider import get_provider
        m3 = get_provider()
        prompt = f"""你是一个严格的足球知识质量评估员。评估下面 Qwen-7B + LoRA 嘅 response。

Query: {query}

Response: {response}

评判标准:
1. 内容是否与足球相关 (YES/NO)
2. 数据/事实是否具体 (有数字/年份/球员名)
3. 是否避免胡乱编造
4. 回答长度 > 50 字

输出 JSON 严格格式: {{"passed": true/false, "score": 0-10, "reason": "..."}}"""
        result = m3.chat([{"role": "user", "content": prompt}], max_tokens=400, temperature=0.1, use_fallback=False)
        import re
        json_match = re.search(r'\{.*?\}', result, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            return data.get('passed', False), data.get('score', 0), data.get('reason', '')
        return False, 0, "M3 评估 JSON 解析失败"
    except Exception as e:
        return False, 0, f"M3 评估异常: {str(e)[:100]}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="/tmp/ms_cache/models/qwen--Qwen2-7B-Instruct/snapshots/master")
    parser.add_argument("--lora", default=str(BASE / "qwen-7b-football-lora"))
    args = parser.parse_args()

    print("=" * 70)
    print("P6.6 Qwen-7B 足球 LoRA 真训练 verify (永久 invariant #94)")
    print("=" * 70)
    print()
    print(f"Base model: {args.model}")
    print(f"LoRA: {args.lora}")
    print(f"Queries: {len(TEST_QUERIES)}")
    print()

    results = []
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] Query: {query}")
        try:
            response = verify_with_lora(args.model, args.lora, query, max_new_tokens=200)
            print(f"  Response: {response[:200]}...")

            passed, score, reason = evaluate_with_m3(query, response)
            results.append({
                "query": query,
                "response_preview": response[:300],
                "passed": passed,
                "score": score,
                "reason": reason,
            })
            print(f"  评估: {'PASS' if passed else 'FAIL'} (score={score}, {reason[:80]})")
        except Exception as e:
            print(f"  错误: {e}")
            results.append({
                "query": query,
                "passed": False,
                "error": str(e)[:200],
            })
        print()

    passed_count = sum(1 for r in results if r.get("passed", False))
    print("=" * 70)
    print(f"P6.6 verify 完成: {passed_count}/{len(TEST_QUERIES)} PASS")
    print("=" * 70)

    # 写报告
    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P6.6 Qwen-7B 足球 LoRA 真训练 verify",
        "base_model": args.model,
        "lora": args.lora,
        "test_count": len(TEST_QUERIES),
        "passed_count": passed_count,
        "results": results,
    }
    report_path = BASE / "lora_7b_verify_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {report_path}")


if __name__ == "__main__":
    main()
