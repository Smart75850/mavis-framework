#!/usr/bin/env python3
"""
mavis memory LlamaIndex 4 步索引 - P1.3
永久 invariant #36: LlamaIndex 4 步索引 (Load/Index/Store/Query) = mavis memory RAG
来源: 高强文书第 13 章 §基于 LlamaIndex 的 RAG Agent 综合应用开发
"""
import sys
import os
import json
import time
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# 强制 HTTPS proxy 关闭 (避免 SOCKS 错误)
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    StorageContext,
    load_index_from_storage,
    Settings,
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.llms.ollama import Ollama
import llama_index.core


# === 路径配置 ===
MAVIS_MEMORY_DIR = Path.home() / ".mavis" / "agents" / "mavis" / "memory"
P13_DIR = Path.home() / "workspace" / "mavis-llamaindex-v2"
STORAGE_DIR = P13_DIR / "storage"
CYCLE_REPORT = P13_DIR / "cycle-report.json"
P13_DIR.mkdir(parents=True, exist_ok=True)


# === 永久 invariant #14: OUTPUT IN CHINESE ===
# === 永久 invariant #34: 14B 模型选择 ===
OLLAMA_BASE = "http://127.0.0.1:11434/v1"
EMBED_MODEL = os.environ.get("MAVIS_EMBED_MODEL", "nomic-embed-text")
LLM_MODEL = os.environ.get("MAVIS_LLM_MODEL", "qwen2.5:14b")


# === 自定义 Ollama Embedding (绕过 ollama lib, 走 HTTP API) ===

class HttpxOllamaEmbedding(BaseEmbedding):
    """绕过 ollama Python lib, 直接 httpx 调 Ollama /v1/embeddings"""

    def __init__(self, model_name: str = "nomic-embed-text", base_url: str = "http://127.0.0.1:11434/v1"):
        super().__init__()
        self._model_name = model_name
        self._base_url = base_url

    @classmethod
    def class_name(cls) -> str:
        return "HttpxOllamaEmbedding"

    def _get_embedding(self, text: str) -> List[float]:
        """调 Ollama /v1/embeddings"""
        r = httpx.post(
            f"{self._base_url}/embeddings",
            json={"model": self._model_name, "input": text},
            timeout=30
        )
        r.raise_for_status()
        data = r.json()
        return data["data"][0]["embedding"]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_embedding(text)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_embedding(text)


# === LlamaIndex 4 步 ===

def step1_load(memory_dir: Path) -> List:
    """步骤 1: 装载 (Load) - SimpleDirectoryReader (显式 .md 文件列表)"""
    print("\n📥 Step 1: Load 装载 mavis memory 文件")
    print(f"   目录: {memory_dir}")

    # 显式列 .md 文件, 排除 archive / hooks-templates / .bak / .summary / 隐藏文件
    md_files = []
    exclude_names = {".summary.md"}
    exclude_suffixes = (".bak", ".bak-2026-07-10")
    exclude_dirs = {"archive", "hooks-templates"}
    for f in sorted(memory_dir.rglob("*.md")):
        # 排除隐藏文件 + 备份
        if f.name in exclude_names or any(f.name.endswith(s) for s in exclude_suffixes):
            continue
        # 排除 archive / hooks-templates 子目录
        if any(part in exclude_dirs for part in f.parts):
            continue
        # 排除 topics/ 下的子目录 (如果有)
        md_files.append(f)

    print(f"   发现有效 .md 文件数: {len(md_files)}")
    for f in md_files:
        print(f"     - {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    reader = SimpleDirectoryReader(
        input_files=[str(f) for f in md_files],
        filename_as_id=True,
    )
    docs = reader.load_data()
    print(f"   装载文档数: {len(docs)}")
    for i, d in enumerate(docs[:5]):
        meta = d.metadata or {}
        fname = meta.get('file_path', '?').split('/')[-1] or '?'
        print(f"   [{i+1}] {fname} ({len(d.text)} 字符)")
    if len(docs) > 5:
        print(f"   ... +{len(docs) - 5} more")
    return docs


def step2_index(docs: List, embed_model: HttpxOllamaEmbedding) -> VectorStoreIndex:
    """步骤 2: 索引 (Index) - VectorStoreIndex + SentenceSplitter"""
    print("\n🔨 Step 2: Index 索引构建")
    print(f"   嵌入模型: {EMBED_MODEL} (Ollama)")
    print(f"   LLM 模型: {LLM_MODEL} (用于 query 总结)")

    # 全局配置
    Settings.embed_model = embed_model
    Settings.llm = Ollama(model=LLM_MODEL, base_url="http://127.0.0.1:11434", request_timeout=60.0)
    Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    Settings.chunk_size = 512
    Settings.chunk_overlap = 50

    print(f"   chunk_size: 512, overlap: 50 (固定长度分块)")
    print("   构建索引中 (这会调 N 次 embed API)...")

    t0 = time.time()
    index = VectorStoreIndex.from_documents(docs, show_progress=True)
    elapsed = time.time() - t0

    print(f"   索引构建完成, 耗时 {elapsed:.1f}s")
    return index


def step3_store(index: VectorStoreIndex, storage_dir: Path):
    """步骤 3: 存储 (Store) - 持久化到本地"""
    print(f"\n💾 Step 3: Store 持久化")
    print(f"   存储目录: {storage_dir}")
    storage_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(storage_dir))

    # 列出文件
    files = list(storage_dir.iterdir())
    print(f"   写入文件数: {len(files)}")
    total = sum(f.stat().st_size for f in files)
    print(f"   总大小: {total / 1024:.1f} KB")
    for f in files:
        print(f"   - {f.name} ({f.stat().st_size / 1024:.1f} KB)")


def step4_query(index: VectorStoreIndex, query: str, top_k: int = 3) -> dict:
    """步骤 4: 查询 (Query) - query_engine + LLM 总结"""
    print(f"\n🔍 Step 4: Query 语义检索")
    print(f"   query: {query}")

    query_engine = index.as_query_engine(
        similarity_top_k=top_k,
        response_mode="compact",
    )

    t0 = time.time()
    response = query_engine.query(query)
    elapsed = time.time() - t0

    # 召回的 source nodes
    sources = []
    for node in response.source_nodes:
        meta = node.node.metadata or {}
        fname = meta.get('file_path', '?').split('/')[-1] or '?'
        score = node.score or 0
        sources.append({
            "file": fname,
            "score": round(score, 4),
            "text_preview": node.node.text[:150].replace("\n", " "),
        })

    return {
        "query": query,
        "answer": str(response),
        "elapsed_s": round(elapsed, 2),
        "top_k": top_k,
        "sources": sources,
    }


def build_index(memory_dir: Path = MAVIS_MEMORY_DIR, storage_dir: Path = STORAGE_DIR):
    """主流程: 4 步构建索引"""
    print("=" * 60)
    print("mavis memory LlamaIndex 4 步索引 - P1.3")
    print("永久 invariant #36: Load/Index/Store/Query")
    print("来源: 高强文书第 13 章 §基于 LlamaIndex 的 RAG Agent")
    print("=" * 60)

    # 自定义 embedding (绕过 ollama lib, 走 HTTP)
    embed_model = HttpxOllamaEmbedding(model_name=EMBED_MODEL)

    # 4 步
    docs = step1_load(memory_dir)
    index = step2_index(docs, embed_model)
    step3_store(index, storage_dir)

    # 输出报告
    report = {
        "build_at": datetime.now().isoformat(),
        "memory_dir": str(memory_dir),
        "storage_dir": str(storage_dir),
        "doc_count": len(docs),
        "embed_model": EMBED_MODEL,
        "llm_model": LLM_MODEL,
        "chunk_size": 512,
        "chunk_overlap": 50,
    }
    CYCLE_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {CYCLE_REPORT}")

    return index


def load_or_build_index(memory_dir: Path = MAVIS_MEMORY_DIR, storage_dir: Path = STORAGE_DIR):
    """加载已构建的索引, 没构建过就 build"""
    if (storage_dir / "docstore.json").exists():
        print(f"📂 加载已存在索引: {storage_dir}")
        embed_model = HttpxOllamaEmbedding(model_name=EMBED_MODEL)
        Settings.embed_model = embed_model
        Settings.llm = Ollama(model=LLM_MODEL, base_url="http://127.0.0.1:11434", request_timeout=60.0)
        storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
        index = load_index_from_storage(storage_context)
        print("   加载成功")
        return index
    else:
        print("📂 索引不存在, 重新构建")
        return build_index(memory_dir, storage_dir)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        # python build_index.py build
        build_index()
    else:
        # python build_index.py
        build_index()
