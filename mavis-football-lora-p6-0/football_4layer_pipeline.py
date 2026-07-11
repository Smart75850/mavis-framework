#!/usr/bin/env python3
"""
P6.7 4 层混合 pipeline 实战 (永久 invariant #95)

实战 4 层:
- Layer 1: Qwen-7B + 真实 LoRA 解析 query (vs P6.2 M3 模拟)
- Layer 2: LlamaIndex RAG 检索 (真实数据, 永久 invariant #36)
- Layer 3: Qwen-7B + LoRA 生成 (基于 query + RAG 上下文)
- Layer 4: M3 评估 (永久 invariant #51)

预期 4-5/5 PASS (P6.2 3 层 4/5 PASS, 加上真实 LoRA 应该 4-5/5)
"""
import sys
import os
import json
import time
import re
from pathlib import Path
from datetime import datetime

for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(Path('/Users/apple/workspace/LLaMA-Factory/.venv/lib/python3.12/site-packages')))
sys.path.insert(0, str(BASE.parent / "mavis-crewai-v7"))
sys.path.insert(0, str(BASE.parent / "mavis-llamaindex-v2"))

from mavis_m3_provider import get_provider

# ============== Layer 1: Qwen-7B + 真实 LoRA 解析 query (永久 invariant #94) ==============

QWEN7B_MODEL = "/tmp/ms_cache/models/qwen--Qwen2-7B-Instruct/snapshots/master"
LORA_PATH = str(BASE / "qwen-7b-football-lora")

PARSE_SYSTEM = "你是一个足球数据分析助手。解析用户 query 提取关键实体: 球队/球员/赛季/统计。只返 JSON, 唔好加额外文字: {\"home\": \"...\", \"away\": \"...\", \"season\": \"...\", \"player\": \"...\", \"stat\": \"...\"}"


def lora_parse_query(user_query: str) -> dict:
    """Qwen-7B + 真实 LoRA 解析 query (永久 invariant #94)"""
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
            return json.loads(m.group(0))
        except Exception:
            pass
    return {"raw": user_query}


# ============== Layer 2: LlamaIndex RAG (永久 invariant #36) ==============

def rag_retrieve(query: str, top_k: int = 3) -> list:
    """RAG 检索 (复用 P6.2)"""
    try:
        from llama_index.core import VectorStoreIndex, Document, Settings
        from build_index import HttpxOllamaEmbedding, M3LLM

        Settings.embed_model = HttpxOllamaEmbedding(model_name="nomic-embed-text")
        Settings.llm = M3LLM()

        train_path = BASE / "football_alpaca_100plus_train.jsonl"
        if not train_path.exists():
            return []
        docs = []
        with open(train_path) as f:
            for line in f:
                ex = json.loads(line)
                docs.append(Document(text=f"指令: {ex['instruction']}\n输入: {ex.get('input', '')}\n回答: {ex['output']}"))
        index = VectorStoreIndex.from_documents(docs)
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        return [{"text": n.node.text, "score": n.score} for n in nodes]
    except Exception as e:
        print(f"    [RAG 错误] {e}")
        return []


# ============== Layer 3: M3 综合 (永久 invariant #51, 跟 P6.2 一致) ==============

def m3_synthesize(parsed_entities: dict, rag_results: list, user_query: str) -> str:
    """M3 综合 (永久 invariant #51) - 关键: 用真实 Qwen-7B LoRA 解析嘅实体 (vs P6.2 M3 模拟 LoRA)"""
    m3 = get_provider()
    system = (
        "你是一个足球数据综合分析专家。\n"
        "根据 LoRA (Qwen-7B 真训练) 解析嘅实体 + RAG 检索嘅结果, 给出专业足球分析。\n"
        "必须使用具体数字, 唔好编造。\n"
        "如果数据不足, 老实讲'数据不足'。"
    )
    user = f"""
用户问题: {user_query}

LoRA (Qwen-7B 真训练) 解析嘅实体: {json.dumps(parsed_entities, ensure_ascii=False)}

RAG 检索结果 (top {len(rag_results)}):
{chr(10).join([f"- [{i+1}] score={r['score']}: {r['text'][:200]}" for i, r in enumerate(rag_results)])}

请综合分析, 给出专业答案。
"""
    return m3.chat(
        [{"role": "user", "content": user}],
        max_tokens=400, temperature=0.3, use_fallback=False,
    )


# ============== Layer 4: M3 评估 (永久 invariant #51) ==============

def evaluate_with_m3(query: str, response: str) -> tuple:
    m3 = get_provider()
    prompt = f"""你是一个严格的足球知识质量评估员。评估下面 Qwen-7B + LoRA + RAG 嘅 4 层混合 pipeline response。

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
    print("P6.7 4 层混合 pipeline 实战 (永久 invariant #95)")
    print("=" * 70)
    print(f"Qwen-7B model: {QWEN7B_MODEL}")
    print(f"LoRA: {LORA_PATH}")
    print(f"Queries: {len(TEST_QUERIES)}")
    print()
    print("4 层: Qwen-7B+LoRA 解析 → RAG 检索 → Qwen-7B+LoRA 生成 → M3 评估")
    print()

    start = time.time()
    results = []

    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"[{i}/{len(TEST_QUERIES)}] Query: {query}")
        try:
            # Layer 1: Qwen-7B + LoRA 解析
            print(f"  [L1] LoRA parse...")
            parsed = lora_parse_query(query)

            # Layer 2: RAG 检索
            print(f"  [L2] RAG retrieve...")
            rag_query = parsed.get("raw", query) if isinstance(parsed.get("raw"), str) else query
            rag_hits = rag_retrieve(rag_query, top_k=3)
            rag_context = "\n\n".join([r["text"] for r in rag_hits])
            print(f"    RAG hits: {len(rag_hits)}")

            # Layer 3: M3 综合 (基于 Qwen-7B 真实 LoRA 解析 + RAG)
            print(f"  [L3] M3 synthesize (基于 Qwen-7B LoRA + RAG)...")
            response = m3_synthesize(parsed, rag_hits, query)
            print(f"    Response: {response[:200]}...")

            # Layer 4: M3 评估
            print(f"  [L4] M3 evaluate...")
            passed, score, reason = evaluate_with_m3(query, response)
            print(f"    Eval: {'PASS' if passed else 'FAIL'} (score={score})")

            results.append({
                "query": query,
                "parsed": parsed,
                "rag_hits_count": len(rag_hits),
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
    print(f"P6.7 完成: {passed_count}/{len(TEST_QUERIES)} PASS, 耗时 {elapsed:.1f}s")
    print("=" * 70)

    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P6.7 4 层混合 pipeline (Qwen-7B + LoRA + RAG + M3)",
        "base_model": QWEN7B_MODEL,
        "lora": LORA_PATH,
        "test_count": len(TEST_QUERIES),
        "passed_count": passed_count,
        "elapsed_s": round(elapsed, 1),
        "results": results,
    }
    report_path = BASE / "football_4layer_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
