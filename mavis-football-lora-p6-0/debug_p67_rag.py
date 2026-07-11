#!/usr/bin/env python3
"""Debug P6.7 RAG 0 hits 问题"""
import sys
import os
from pathlib import Path

for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

BASE = Path('/Users/apple/workspace/mavis-framework/mavis-football-lora-p6-0')
sys.path.insert(0, '/Users/apple/workspace/mavis-framework/mavis-llamaindex-v2')

from llama_index.core import VectorStoreIndex, Document, Settings
from build_index import HttpxOllamaEmbedding

Settings.embed_model = HttpxOllamaEmbedding(model_name="nomic-embed-text")

train_path = BASE / "football_alpaca_100plus_train.jsonl"
import json
docs = []
with open(train_path) as f:
    for i, line in enumerate(f):
        ex = json.loads(line)
        if i < 3:
            print(f"Ex[{i}]: {ex['instruction'][:80]} -> {ex['output'][:80]}")
        docs.append(Document(text=f"指令: {ex['instruction']}\n输入: {ex.get('input', '')}\n回答: {ex['output']}"))
print(f"\n总 docs: {len(docs)}")
print("Building index...")

index = VectorStoreIndex.from_documents(docs, show_progress=False)
print("Index built")

retriever = index.as_retriever(similarity_top_k=3)

queries = [
    "曼联对利物浦历史对战",
    "英超射手榜 2024-25",
    "凯恩 拜仁 进球",
]

for q in queries:
    print(f"\nQ: {q}")
    nodes = retriever.retrieve(q)
    print(f"  Hits: {len(nodes)}")
    for j, n in enumerate(nodes):
        print(f"    [{j+1}] score={n.score:.4f}: {n.node.text[:80]}")
