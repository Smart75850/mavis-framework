"""
mavis M3 Provider - MiniMax M3 统一 API 接入 (永久 invariant #51)
M3 = api.minimaxi.com/anthropic (Anthropic 兼容 API)

设计:
- LLM 端: M3 API (MiniMax-M3) 0.4s/次
- Embedding 端: 仍用本地 ollama nomic-embed (274MB, 不违反"不用本地大模型"原则)
- 跨夜战 22 小时所有 LLM 调用统一改用 M3
- 失败 fallback 到本地 14B

使用:
    from mavis_m3_provider import M3Provider
    p = M3Provider()
    out = p.chat([{"role": "user", "content": "..."}], max_tokens=500)
    vec = p.embed("hello world")
"""
import os
import json
import time
import httpx
from typing import List, Dict, Optional, Any

# 关闭 SOCKS proxy
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# === 永久 invariant #51: M3 Provider 统一 API 接入 ===
# 从 ~/.claude/settings.json 读 (避免 hardcode 敏感 token)
import re
from pathlib import Path

SETTINGS_FILE = Path.home() / ".claude" / "settings.json"


def _load_m3_creds():
    """从 ~/.claude/settings.json 加载 M3 API base + token + model"""
    try:
        with open(SETTINGS_FILE) as f:
            cfg = json.load(f)
        env = cfg.get("env", {})
        return {
            "base_url": env.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com/anthropic"),
            "token": env.get("ANTHROPIC_AUTH_TOKEN", ""),
            "model": env.get("ANTHROPIC_MODEL", "MiniMax-M3"),
        }
    except Exception as e:
        return {
            "base_url": "https://api.minimaxi.com/anthropic",
            "token": "",
            "model": "MiniMax-M3",
        }


_CREDS = _load_m3_creds()
M3_BASE = _CREDS["base_url"]  # https://api.minimaxi.com/anthropic
M3_TOKEN = _CREDS["token"]
M3_MODEL = _CREDS["model"]  # MiniMax-M3

# OpenAI 兼容 embedding (本地 ollama, 274MB nomic-embed, 不算大模型)
OLLAMA_BASE = "http://127.0.0.1:11434/v1"
OLLAMA_EMBED_MODEL = "nomic-embed-text"

# Local LLM fallback (qwen2.5:14b 本地)
LOCAL_LLM_BASE = "http://127.0.0.1:11434/v1"
LOCAL_LLM_MODEL = "qwen2.5:14b"


class M3Provider:
    """MiniMax M3 统一 Provider (永久 invariant #51)"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.total_calls = 0
        self.total_errors = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: float = 0.7,
        use_fallback: bool = True,
    ) -> str:
        """调 M3 API (Anthropic 兼容), 失败 fallback 到本地 14B"""
        # 1. 尝试 M3
        try:
            return self._chat_m3(messages, max_tokens, system, temperature)
        except Exception as e:
            self.total_errors += 1
            if self.verbose:
                print(f"  ⚠️  M3 失败: {type(e).__name__}: {e}")
            if not use_fallback:
                raise
            # 2. fallback 到本地 14B
            if self.verbose:
                print(f"  ↪️  fallback 到本地 {LOCAL_LLM_MODEL}")
            return self._chat_local(messages, max_tokens, system, temperature)

    def _chat_m3(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        system: Optional[str],
        temperature: float,
    ) -> str:
        """直接调 M3 Anthropic 兼容 API"""
        t0 = time.time()
        # Anthropic 格式: system 顶层 + messages 列表
        payload = {
            "model": M3_MODEL,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            payload["system"] = system

        r = httpx.post(
            f"{M3_BASE}/v1/messages",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": M3_TOKEN,
                "anthropic-version": "2023-06-01",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        r.raise_for_status()
        data = r.json()

        # Anthropic 格式返回: content[0].text
        text = data.get("content", [{}])[0].get("text", "")
        usage = data.get("usage", {})
        self.total_calls += 1
        self.total_input_tokens += usage.get("input_tokens", 0)
        self.total_output_tokens += usage.get("output_tokens", 0)
        if self.verbose:
            elapsed = time.time() - t0
            print(f"  ✅ M3 OK ({elapsed:.2f}s, {usage.get('input_tokens', 0)}+{usage.get('output_tokens', 0)} tokens)")
        return text

    def _chat_local(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        system: Optional[str],
        temperature: float,
    ) -> str:
        """Fallback 到本地 ollama 14B (OpenAI 兼容格式)"""
        # OpenAI 格式: system 在 messages 开头
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages)

        r = httpx.post(
            f"{LOCAL_LLM_BASE}/chat/completions",
            json={
                "model": LOCAL_LLM_MODEL,
                "messages": msgs,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        r.raise_for_status()
        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        self.total_calls += 1
        return text

    def embed(self, text: str) -> List[float]:
        """Embedding: 仍用本地 ollama nomic-embed (274MB)"""
        r = httpx.post(
            f"{OLLAMA_BASE}/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "input": text},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]

    def stats(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_errors": self.total_errors,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "model": M3_MODEL,
        }


# === Singleton (避免重复初始化) ===
_PROVIDER = None


def get_provider() -> M3Provider:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = M3Provider(verbose=False)
    return _PROVIDER


# === 便捷函数 (替换原 call_llm 模式) ===

def call_llm_m3(
    system: str,
    user: str,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    use_fallback: bool = True,
) -> str:
    """单次 LLM 调用 (永久 invariant #51 替代品)"""
    return get_provider().chat(
        messages=[{"role": "user", "content": user}],
        max_tokens=max_tokens,
        system=system,
        temperature=temperature,
        use_fallback=use_fallback,
    )


def embed_m3(text: str) -> List[float]:
    """Embedding 调用 (永久 invariant #51 替代品, 仍走本地 ollama)"""
    return get_provider().embed(text)


# === CLI 测试 ===
if __name__ == "__main__":
    print("=" * 60)
    print("M3 Provider 测试 (永久 invariant #51)")
    print("=" * 60)
    print(f"  M3 base: {M3_BASE}")
    print(f"  M3 model: {M3_MODEL}")
    print(f"  Embed model: {OLLAMA_EMBED_MODEL} (本地 ollama, 274MB)")
    print()

    p = M3Provider(verbose=True)

    # 1. chat
    print("Test 1: M3 chat")
    r1 = p.chat(
        messages=[{"role": "user", "content": "用 5 字符回 1+1=?"}],
        max_tokens=20,
    )
    print(f"  reply: {r1!r}")

    # 2. embed
    print("\nTest 2: 本地 ollama embed")
    v = p.embed("hello world")
    print(f"  vector dim: {len(v)}, first 3: {v[:3]}")

    # 3. stats
    print("\nStats:", json.dumps(p.stats(), indent=2))
