#!/usr/bin/env python3
"""
mavis 8 机制节点查询路由 - P1.4
永久 invariant #37: mavis 8 机制 query_engine 路由 = 永久 invariant #36 落地

来源: mavis-2-roadmap.md §四、与 8 机制协奏嘅映射
8 机制: CLAUDE.md / 子智能体 / Skills / Hooks / MCP / Headless / Agent SDK / Plugins
"""
import sys
import os
import json
import time
import httpx  # T2 修: call_llm_router 用 httpx.post 但冇 import, 加埋
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# 关闭 SOCKS proxy (永久 invariant: 避开 ollama lib socks 问题)
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''

# 复用 P1.3 的 LlamaIndex 索引
sys.path.insert(0, str(Path(__file__).parent.parent / "mavis-llamaindex-v2"))
from build_index import load_or_build_index, HttpxOllamaEmbedding, OLLAMA_BASE, LLM_MODEL

# 全局参数定义
EIGHT_MECHANISMS = [
    {
        "id": 1,
        "name": "CLAUDE.md",
        "description": "项目级 AGENTS.md, init script auto-inject",
        "keywords": ["CLAUDE.md", "AGENTS.md", "项目级", "企业级", "用户级", "五层记忆", "init", "harness"],
        "current_status": "✅ 13+ 项目",
    },
    {
        "id": 2,
        "name": "子智能体",
        "description": "5 模式 (P1.1.a 9 Agent 模式)",
        "keywords": ["子智能体", "subagent", "team plan", "sub-agent", "9 节点", "Patcher", "verifier", "反射"],
        "current_status": "✅ 5 模式",
    },
    {
        "id": 3,
        "name": "Skills",
        "description": "技能系统, AWEL 三层架构",
        "keywords": ["Skills", "skill", "技能", "AWEL", "三层架构", "skill-creator", "skill-refiner"],
        "current_status": "✅ 3 个 skill",
    },
    {
        "id": 4,
        "name": "Hooks",
        "description": "Shell hooks 17/17 PASS + 未来 Python 原生",
        "keywords": ["Hooks", "hook", "钩子", "PreToolUse", "PostToolUse", "block-dangerous", "protect-files", "17/17"],
        "current_status": "✅ Shell 17/17",
    },
    {
        "id": 5,
        "name": "MCP",
        "description": "Model Context Protocol, 6 server 注册",
        "keywords": ["MCP", "Model Context Protocol", "stdio", "HTTP", "mcp server", "6 server", "mcp-cli"],
        "current_status": "✅ 6 server",
    },
    {
        "id": 6,
        "name": "Headless",
        "description": "Headless 模式 + CI/CD, GitHub Actions",
        "keywords": ["Headless", "CI/CD", "claude -p", "GitHub Actions", "max-turns", "max-budget-usd", "output-format"],
        "current_status": "✅ GitHub Actions",
    },
    {
        "id": 7,
        "name": "Agent SDK",
        "description": "完整 Agent SDK (类似 claude-agent-sdk)",
        "keywords": ["Agent SDK", "mavis SDK", "@tool", "canUseTool", "ClaudeAgentOptions", "session resume", "fork_session"],
        "current_status": "🟡 50% (Phase 4)",
    },
    {
        "id": 8,
        "name": "Plugins",
        "description": "plugin.json manifest + install CLI",
        "keywords": ["Plugins", "plugin", "plugin.json", "install", "manifest", "Phase 2"],
        "current_status": "✅ plugin.json",
    },
]


def route_by_keywords(query: str) -> List[Tuple[str, float]]:
    """第一级路由: 关键词匹配 (中英都支持)"""
    query_lower = query.lower()
    matches = []
    for mech in EIGHT_MECHANISMS:
        score = 0
        for kw in mech["keywords"]:
            if kw.lower() in query_lower:
                # 多字关键词权重更高
                score += len(kw) / 5.0
        if score > 0:
            matches.append((mech["name"], score))

    # 按 score 降序排
    matches.sort(key=lambda x: -x[1])
    return matches


def call_llm_router(query: str, mechanisms: List[Tuple[str, Dict]]) -> Optional[str]:
    """第二级路由: LLM 决策 (兜底, 关键词不命中时)"""
    # 构造机制简介
    mech_summaries = "\n".join([f"{i+1}. {m['name']} - {m['description']}" for i, m in enumerate(mechanisms)])
    
    system_message = "根据用户提供的问题，选择最相关的8个机制中的一个。只输出该机制的名称，不需要解释原因。"
    user_query = f"以下是可用的八个机制:\n{mech_summaries}\n\n问题是：\n'{query}'"

    try:
        response_content = httpx.post(
            OLLAMA_BASE + '/chat/completions',
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "system", "content": system_message}, {"role": "user", "content": user_query}]
            },
            timeout=30
        ).json()['choices'][0]['message']['content'].strip()
        
        return response_content

    except Exception as e:
        print(f"   [LLM 路由失败] {e}")
        return None


class EightMechRouter(object):
    """8 机制 query_engine 实现 (根据永久不变量#36)"""

    def __init__(self, top_k: int = 2) -> None:
        self.index = load_or_build_index()
        self.top_k = top_k # 只保持前几个查询结果
        # 静态构建所有引擎
        self.query_engines = {mech["name"]: self.construct_engine(mech) for mech in EIGHT_MECHANISMS}

    def construct_engine(self, mechanism: Dict[str, str]):
        """基于机制动态生成 query_engine"""
        sim_top_k_adjustment=5 # 搜索相似度最匹配的前多少的结果
        return self.index.as_query_engine(
            similarity_top_k=sim_top_k_adjustment,
            response_mode="compact"
        )

    
    def route_and_response(self, question: str):
        """执行路由 + 返回结果"""
        
        keywords_result = route_by_keywords(question)
        # 优化: 关键词命中就不调 LLM (省 5s/次, 200 query 省 1000s = 17 分钟)
        if keywords_result:
            llm_route_res = None
        else:
            llm_route_res = call_llm_router(question, EIGHT_MECHANISMS)

        # 选择正确的机制
        chosen_mechanism_name = keywords_result[0][0] if keywords_result else (llm_route_res or "全机制")

        # 执行相应 query_engine 查询回答并返回结果
        engine = self.query_engines.get(chosen_mechanism_name, self.query_engines.get(EIGHT_MECHANISMS[0]["name"], None))
        response = engine.query(question)

        # 输出
        result_dict = {
            "query": question,
            "routed_mechanism": chosen_mechanism_name,
            "routing_method": ("关键词" if keywords_result else "LLM 兜底"),
            "kw_top_matches": [(m, round(s, 2)) for m, s in keywords_result[:3]] or [],
            "answer": str(response),
        }

        return result_dict
        

EIGHT_MECH_TEST_QUERIES = [
    # 测试 CLAUDE.md 关键词
    'CLAUDE.md 怎么五层记忆自动填充',
    
    # 测试 子智能体关键词
    'mavis 子代理团队规划怎样执行',
    
    # 测试 Skills关键词
    '如何通过 mavis 架构描述技能系统',
    
    # 测试 Hooks 关键词
    '如何阻止危险的 shell hooks 利用 block-dangerous',
  
    # 测试 MCP 关键词
    '怎么注册一个 model context protocol 服务器',
 
    # 测试 Headless关键词
    '怎样利用 max-turns 在headless模式下部署 CI/CD',

    
    # 测试 Agent SDK关键词
    '@tool 是什么，如何使用？',
   
   # 测试 Plugins 关键词
    
]

def test_router():
    """验证查询功能"""
    router = EightMechRouter(top_k=2)
    print("P1.4 全面测试 —— 8机制路由验证")
    for q in EIGHT_MECH_TEST_QUERIES:
        route_res = router.route_and_response(q)
        print(route_res)

if __name__ == "__main__":
    test_router()