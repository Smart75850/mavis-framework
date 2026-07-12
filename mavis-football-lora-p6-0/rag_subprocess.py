#!/usr/bin/env python3
"""
P7 RAG subprocess (永久 invariant #96)
- 跑在 mavis-llamaindex-v2/.venv (有 llama_index + nomic-embed)
- stdin JSON: {"query": str, "top_k": int, "data_path": str}
- stdout JSON: {"hits": [{"text": str, "score": float}], "count": int}

实战: P6.7 4 层 pipeline 跨 venv (永久 invariant #95 实战教训)
"""
import sys
import os
import json
from pathlib import Path

# 避 proxy
for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

# 加 build_index 所在目录到 sys.path
LLAMAINDEX_V2_DIR = Path('/Users/apple/workspace/mavis-framework/mavis-llamaindex-v2')
sys.path.insert(0, str(LLAMAINDEX_V2_DIR))

try:
    from llama_index.core import VectorStoreIndex, Document, Settings
    from build_index import HttpxOllamaEmbedding
except Exception as e:
    print(json.dumps({"error": f"import error: {str(e)[:200]}", "hits": [], "count": 0}))
    sys.exit(1)


def main():
    # 读 stdin
    try:
        raw = sys.stdin.read()
        req = json.loads(raw)
        query = req["query"]
        top_k = int(req.get("top_k", 3))
        data_path = req["data_path"]
    except Exception as e:
        print(json.dumps({"error": f"stdin parse error: {str(e)[:200]}", "hits": [], "count": 0}))
        sys.exit(1)

    # 配 embed
    try:
        Settings.embed_model = HttpxOllamaEmbedding(model_name="nomic-embed-text")
    except Exception as e:
        print(json.dumps({"error": f"embed setup error: {str(e)[:200]}", "hits": [], "count": 0}))
        sys.exit(1)

    # 加载 docs
    try:
        docs = []
        with open(data_path) as f:
            for line in f:
                ex = json.loads(line)
                docs.append(Document(
                    text=f"指令: {ex['instruction']}\n输入: {ex.get('input', '')}\n回答: {ex['output']}"
                ))
    except Exception as e:
        print(json.dumps({"error": f"data load error: {str(e)[:200]}", "hits": [], "count": 0}))
        sys.exit(1)

    if not docs:
        print(json.dumps({"error": "no docs", "hits": [], "count": 0}))
        sys.exit(1)

    # 检索
    try:
        index = VectorStoreIndex.from_documents(docs, show_progress=False)
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        hits = [{"text": n.node.text, "score": round(n.score or 0, 4)} for n in nodes]
        print(json.dumps({"hits": hits, "count": len(hits), "error": ""}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": f"retrieve error: {str(e)[:200]}", "hits": [], "count": 0}))
        sys.exit(1)


if __name__ == "__main__":
    main()
