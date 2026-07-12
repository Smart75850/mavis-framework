#!/usr/bin/env python3
"""
P8.1 4 层混合 pipeline 升级实战 (永久 invariant #98)
- 复用 P7 (#96) 跨 venv pattern
- 升级 1: 200 条 alpaca (vs 70 条) → RAG 命中率提升
- 升级 2: 100 step LoRA (vs 20 step) → LoRA 解析 bias 降低
- 升级 3: entity query 改写 (Layer 1 抽出实体, 重新 query RAG) → RAG 命中率提升
- 预期: 4-5/5 PASS (vs P7 0/5 PASS)
"""
import sys
import os
import json
import time
import re
import subprocess
from pathlib import Path
from datetime import datetime

for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(Path('/Users/apple/workspace/LLaMA-Factory/.venv/lib/python3.12/site-packages')))
sys.path.insert(0, str(BASE.parent / "mavis-crewai-v7"))

from mavis_m3_provider import get_provider

# ============== Layer 1: Qwen-7B 100 step LoRA 解析 (永久 invariant #98) ==============

QWEN7B_MODEL = "/tmp/ms_cache/models/qwen--Qwen2-7B-Instruct/snapshots/master"
LORA_PATH = str(BASE / "qwen-7b-football-lora-100step")

PARSE_SYSTEM = (
    "你是一个足球数据分析助手。\n"
    "解析用户 query 提取关键实体: 球队/球员/赛季/统计。\n"
    "如果查询不限于特定赛季, season 字段必须为 null (字符串 \"null\")。\n"
    "**只返 JSON**, 唔好加额外文字: {\"home\": \"...\", \"away\": \"...\", \"season\": \"null\", \"player\": \"...\", \"stat\": \"...\"}"
)


def lora_parse_query(user_query: str) -> dict:
    """Qwen-7B 100 step LoRA 解析 query (永久 invariant #98)"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(QWEN7B_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        QWEN7B_MODEL, torch_dtype=torch.float32, trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(model, LORA_PATH)
    model.eval()

    prompt = f"{PARSE_SYSTEM}\n\n### 指令: {user_query}\n### 回答: "
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        outputs = model.generate(
            **inputs, max_new_tokens=120, do_sample=False, temperature=1.0,
            pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id,
        )
    raw = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
    del model, tokenizer
    import gc; gc.collect()

    print(f"    [LoRA parse] {raw[:120]}")
    m = re.search(r"\{[\s\S]*?\}", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            return data
        except Exception:
            pass
    return {"raw": user_query}


# ============== Layer 2: RAG via subprocess (200 条 alpaca) ==============

RAG_SUBPROCESS_PATH = str(BASE / "rag_subprocess.py")
RAG_VENV_PYTHON = "/Users/apple/workspace/mavis-framework/mavis-llamaindex-v2/.venv/bin/python3"
RAG_DATA_PATH = str(BASE / "football_alpaca_200plus_train.jsonl")


def rag_retrieve(query: str, top_k: int = 5) -> list:
    """RAG 检索 (200 条 alpaca, top_k=5 提升命中率)"""
    req = {"query": query, "top_k": top_k, "data_path": RAG_DATA_PATH}
    try:
        result = subprocess.run(
            [RAG_VENV_PYTHON, RAG_SUBPROCESS_PATH],
            input=json.dumps(req, ensure_ascii=False),
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"    [RAG subprocess fail] rc={result.returncode}, stderr={result.stderr[:200]}")
            return []
        out = json.loads(result.stdout)
        if out.get("error"):
            print(f"    [RAG error] {out['error'][:200]}")
            return []
        return out.get("hits", [])
    except subprocess.TimeoutExpired:
        print(f"    [RAG timeout 120s]")
        return []
    except Exception as e:
        print(f"    [RAG exception] {str(e)[:200]}")
        return []


def build_entity_query(parsed: dict, original: str) -> str:
    """从 LoRA 解析嘅实体重新 query RAG (永久 invariant #98 创新)"""
    parts = []
    if parsed.get("home") and parsed["home"] not in ("", "null"):
        parts.append(parsed["home"])
    if parsed.get("away") and parsed["away"] not in ("", "null"):
        parts.append(parsed["away"])
    if parsed.get("player") and parsed["player"] not in ("", "null"):
        parts.append(parsed["player"])
    if parsed.get("season") and parsed["season"] not in ("", "null"):
        parts.append(parsed["season"])
    if parsed.get("stat") and parsed["stat"] not in ("", "null"):
        parts.append(parsed["stat"])
    if parts:
        return " ".join(parts) + " " + original[:50]
    return original


# ============== Layer 3: M3 综合 ==============

def m3_synthesize(parsed_entities: dict, rag_results: list, user_query: str) -> str:
    """M3 综合 (永久 invariant #51)"""
    m3 = get_provider()
    system = (
        "你是一个足球数据综合分析专家。\n"
        "根据 LoRA (Qwen-7B 100 step) 解析嘅实体 + RAG 检索嘅结果, 给出专业足球分析。\n"
        "必须使用具体数字, 唔好编造。\n"
        "如果数据不足, 老实讲'数据不足'。"
    )
    user = f"""
用户问题: {user_query}

LoRA (Qwen-7B 100 step) 解析嘅实体: {json.dumps(parsed_entities, ensure_ascii=False)}

RAG 检索结果 (top {len(rag_results)}):
{chr(10).join([f"- [{i+1}] score={r['score']}: {r['text'][:200]}" for i, r in enumerate(rag_results)])}

请综合分析, 给出专业答案。
"""
    return m3.chat(
        [{"role": "user", "content": user}],
        max_tokens=400, temperature=0.3, use_fallback=False,
    )


# ============== Layer 4: M3 评估 ==============

def evaluate_with_m3(query: str, response: str) -> tuple:
    m3 = get_provider()
    prompt = f"""你是一个严格的足球知识质量评估员。评估下面 Qwen-7B 100 step LoRA + 200 条 RAG 嘅 4 层混合 pipeline response。

Query: {query}

Response: {response}

评判标准:
1. 内容是否与足球相关 (YES/NO)
2. 数据/事实是否具体 (有数字/年份/球员名)
3. 是否避免胡乱编造
4. 回答长度 > 50 字
5. 综合 RAG 上下文 (YES/NO)

输出 JSON 严格格式: {{"passed": true/false, "score": 0-10, "reason": "..."}}"""
    try:
        result = m3.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=400, temperature=0.1, use_fallback=False,
        )
        m = re.search(r'\{.*?\}', result, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            return data.get('passed', False), data.get('score', 0), data.get('reason', '')
        return False, 0, "M3 评估 JSON 解析失败"
    except Exception as e:
        return False, 0, f"M3 评估异常: {str(e)[:100]}"


# ============== 5 真 query ==============

TEST_QUERIES = [
    "曼联对利物浦历史对战 211 次, 边个胜多?",
    "2024-25 季英超射手榜前 5 系边个?",
    "凯恩 2024-25 季喺拜仁入咗几多球?",
    "5 大联赛争冠激烈程度对比, 边个最激烈?",
    "C 朗 2024 年喺 Al Nassr 入咗几多球?",
]


def main():
    print("=" * 70)
    print("P8.1 4 层混合 pipeline 升级实战 (永久 invariant #98)")
    print("=" * 70)
    print(f"Qwen-7B 100 step LoRA: {LORA_PATH}")
    print(f"RAG data: 200 条 alpaca (vs P7 70 条)")
    print(f"Entity query 改写: ON")
    print(f"Queries: {len(TEST_QUERIES)}")
    print()

    start = time.time()
    results = []

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] Query: {query}")
        try:
            # Layer 1: LoRA 解析
            print(f"  [L1] LoRA parse (100 step)...")
            parsed = lora_parse_query(query)

            # Layer 2a: RAG 用 entity 改写 query
            print(f"  [L2a] RAG entity query rewrite...")
            entity_query = build_entity_query(parsed, query)
            rag_hits = rag_retrieve(entity_query, top_k=5)
            print(f"    RAG hits (entity query): {len(rag_hits)}")

            # Layer 2b: RAG 用原 query 也 retrieve (双保险)
            rag_hits_orig = rag_retrieve(query, top_k=3)
            print(f"    RAG hits (orig query): {len(rag_hits_orig)}")

            all_rag = rag_hits + rag_hits_orig
            # dedup by text
            seen = set()
            deduped = []
            for r in all_rag:
                if r["text"] not in seen:
                    seen.add(r["text"])
                    deduped.append(r)
            all_rag = deduped[:5]  # 限制 5

            # Layer 3: M3 综合
            print(f"  [L3] M3 synthesize (100 step LoRA + 200 条 RAG)...")
            response = m3_synthesize(parsed, all_rag, query)
            print(f"    Response: {response[:200]}...")

            # Layer 4: M3 评估
            print(f"  [L4] M3 evaluate...")
            passed, score, reason = evaluate_with_m3(query, response)
            print(f"    Eval: {'PASS' if passed else 'FAIL'} (score={score})")

            results.append({
                "query": query,
                "parsed": parsed,
                "entity_query": entity_query,
                "rag_hits_count": len(all_rag),
                "rag_hits_entity": len(rag_hits),
                "rag_hits_orig": len(rag_hits_orig),
                "response_preview": response[:400],
                "passed": passed,
                "score": score,
                "reason": reason,
            })
        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "query": query,
                "passed": False,
                "error": str(e)[:200],
            })
        print()

    elapsed = time.time() - start
    passed_count = sum(1 for r in results if r.get("passed", False))
    print("=" * 70)
    print(f"P8.1 完成: {passed_count}/{len(TEST_QUERIES)} PASS, 耗时 {elapsed:.1f}s")
    print("=" * 70)

    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P8.1 4 层混合 pipeline 升级实战 (Qwen-7B 100 step + 200 条 alpaca + entity query 改写)",
        "base_model": QWEN7B_MODEL,
        "lora": LORA_PATH,
        "rag_data": RAG_DATA_PATH,
        "rag_subprocess": RAG_SUBPROCESS_PATH,
        "entity_query_rewrite": True,
        "test_count": len(TEST_QUERIES),
        "passed_count": passed_count,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    report_path = BASE / "football_p81_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
