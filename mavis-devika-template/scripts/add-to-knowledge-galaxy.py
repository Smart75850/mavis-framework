#!/usr/bin/env python3
"""P1.1 完成: 追加 Devika 9 大 Agent 模板节点到 knowledge-galaxy"""
import json
from datetime import date

GALAXY_PATH = "/Users/apple/workspace/claude-config/knowledge-star/knowledge-galaxy-data.json"
TODAY = "2026-07-10"

with open(GALAXY_PATH) as f:
    data = json.load(f)

# 12 个新节点 (从 223 开始)
new_nodes = [
    # #223 总览
    {
        "id": 223,
        "title": "mavis Devika 9 大 Agent 模板总览",
        "summary": "借鉴高强文书第 5 章 Devika 9 Agent 架构, 沉淀 mavis sub-agent 标准化角色模板",
        "content": "位置: ~/workspace/mavis-devika-template/。不是新建 9 个独立 sub-agent,而是定义 9 个标准化角色模板,创建新 agent 时先看属于 9 个角色的哪个,复用职责描述 + 输入输出契约 + JSON 上下文 schema。文件 12 个 (README + CONVENTIONS + 9 agents + 1 demo), 1834 行。",
        "cat": "implementation",
        "rel": [224, 225, 226, 227, 228, 229, 230, 231, 232, 233],
        "pre": [222, 216, 215],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #224 规划 Agent
    {
        "id": 224,
        "title": "01 规划 Agent (Planner)",
        "summary": "用户指令 -> 分步计划 (DAG), 5-15 分钟粒度",
        "content": "Devika §5.1.2 (1)。输入: user_intent + context (工具/沙盒/项目根)。输出: Plan JSON {objective, steps[{step_number, action, expected_output, depends_on}], estimated_turns}。约束: 每步动词开头, 中文输出 (invariant #14)。mavis 对应: team-architect + mavis-team-v2 planner。",
        "cat": "implementation",
        "rel": [223, 225],
        "pre": [223],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #225 研究 Agent
    {
        "id": 225,
        "title": "02 研究 Agent (Researcher)",
        "summary": "计划 -> 检索 + 排名, 三阶段 (向量 -> 混合 -> rerank)",
        "content": "Devika §5.1.2 (2)。工具: mavis-recall-v2 (主力), web_search (网络), filesystem (本地)。三阶段: 向量粗排 Top 100 -> 混合召回 Top 50 -> Cross-Encoder rerank Top 5。约束: 中文优先, 召回可追溯。mavis 对应: analyst + deep-research skill。",
        "cat": "implementation",
        "rel": [223, 224, 226],
        "pre": [223, 30],  # invariant #30
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #226 编码 Agent
    {
        "id": 226,
        "title": "03 编码 Agent (Coder)",
        "summary": "计划 + 研究 -> 代码, ReAct 6 步 (Thought/Action/Observation/Reflection/Function/Speak)",
        "content": "Devika §5.1.2 (3) + AgentScope ReAct (invariant #19)。输入: plan + research + context。输出: Code JSON {files[], diff, syntax_check, style_check}。工具: filesystem/git/shell MCP + ruff/eslint。约束: 中文 + 代码, syntax + style 双验证。mavis 对应: coder + coder-master。",
        "cat": "implementation",
        "rel": [223, 224, 225, 228],
        "pre": [223, 19],  # invariant #19
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #227 行动 Agent
    {
        "id": 227,
        "title": "04 行动 Agent (Action Router)",
        "summary": "用户后续指令 -> 操作关键字, 路由到对应 Agent",
        "content": "Devika §5.1.2 (4)。关键字映射表: 运行 -> 05-runner, 测试 -> 05-runner (test mode), 部署 -> 05-runner (deploy mode), 修 -> 07-patcher, 新增 -> 06-feature, 报告 -> 08-reporter, clone -> 09-decision, browse -> 09-decision。模型: llama3 (快)。mavis 对应: 暂时无, 待建 action-router。",
        "cat": "implementation",
        "rel": [223, 228, 229, 230, 231, 232],
        "pre": [223],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #228 运行 Agent
    {
        "id": 228,
        "title": "05 运行 Agent (Runner)",
        "summary": "代码 -> 沙盒执行结果, 适配 macOS/Linux/Windows, 流式输出",
        "content": "Devika §5.1.2 (5) + CodeFuse-ChatBot 沙盒。沙盒策略: local (subprocess + timeout) / docker (隔离) / none (纯函数)。强制 timeout 180s。不执行破坏性命令。流式输出 (WebSocket)。工具: shell + playwright + filesystem + mavis-cu。mavis 对应: mavis-cu MCP server。",
        "cat": "implementation",
        "rel": [223, 226, 227, 230],
        "pre": [223],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #229 新特性 Agent
    {
        "id": 229,
        "title": "06 新特性 Agent (Feature Builder)",
        "summary": "新需求 -> 增量代码, 保持现有代码结构 + 风格 + 增量测试",
        "content": "Devika §5.1.2 (6)。与 Coder 区别: 输入多 existing_code, 行为是修改现有项目 (非从零), 测试是增量 (不全量), 必须保持风格一致 (snake_case/camelCase)。约束: 不破坏现有 API, 增量测试 100% 通过。mavis 对应: 复用 coder-master, 待建 feature-builder。",
        "cat": "implementation",
        "rel": [223, 226, 228],
        "pre": [223, 226],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #230 补丁 Agent
    {
        "id": 230,
        "title": "07 补丁 Agent (Patcher)",
        "summary": "错误 -> 修复代码, 嵌套对话 4 轮 (诊断 -> 修复 -> 验证 -> 审核)",
        "content": "Devika §5.1.2 (7) + AutoGen 嵌套对话 (invariant #22) + mavis-verifier-v2。Root cause 分析框架: SyntaxError/ImportError/AttributeError/TypeError/TimeoutError/TestFailure 各有诊断 + 修复策略。max_turns=3 避免无限循环。mavis 对应: lint-master + verifier + mavis-verifier-v2。",
        "cat": "implementation",
        "rel": [223, 226, 228],
        "pre": [223, 22, 30],  # invariant #22, #30
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #231 报告 Agent
    {
        "id": 231,
        "title": "08 报告 Agent (Reporter)",
        "summary": "项目状态 -> 综合报告 (summary/technical/api/full 4 种模板)",
        "content": "Devika §5.1.2 (8)。模板: summary (1-2 页执行总结), technical (技术设计 + 代码改动), api (OpenAPI 文档), full (完整)。输出: Report JSON {summary, sections[], format, export_path}。转换: markdown 转 PDF (pdf skill) / HTML。约束: 中文, 代码块带语言标识, 不泄露 secrets。mavis 对应: scribe + pdf skill + docx skill + beautiful-article。",
        "cat": "implementation",
        "rel": [223, 224, 225, 226, 228, 230],
        "pre": [223],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #232 决策 Agent
    {
        "id": 232,
        "title": "09 决策 Agent (Decision Router)",
        "summary": "特殊指令 -> 函数调用 (git clone / browser / lark / github)",
        "content": "Devika §5.1.2 (9) + Function-calling 6 步 (invariant #18)。特殊指令清单 10 种: git_clone / browser_navigate / browser_screenshot / send_email / create_calendar_event / send_lark_message / github_list_issues / github_create_pr / deploy_netlify / run_sql_query。与 04-action 区别: 复杂参数提取 + 外挂函数库。模型: qwen3:32b (准)。mavis 对应: devil-advocate + lark-tools + mavis-cu。",
        "cat": "implementation",
        "rel": [223, 227],
        "pre": [223, 18],  # invariant #18
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #233 端到端 demo
    {
        "id": 233,
        "title": "Devika 9 Agent 端到端 Demo (recall-v2-bug-fix)",
        "summary": "用 9 大 Agent 修复 recall.py chunk 切分 bug, 5 分钟, 8 轮 LLM 调用",
        "content": "场景: 用户说『帮我看看 recall.py chunk 切分 bug 怎么修』。完整流程: 1) Planner 制订 5 步计划; 2) Researcher 召回 5 条相关文档 (与 3 并行); 3) Runner 重现 bug (ValueError overlap 20 > chunk_size 50/2); 4) Action 路由到 Patcher; 5) Patcher 嵌套对话 4 轮 (诊断 -> 修复 -> 验证 -> 审核); 6) Reporter 输出总结 markdown。触发 7 个 Agent (planner/researcher/coder/action/runner/patcher/reporter), 未触发 2 个 (feature/decision)。",
        "cat": "implementation",
        "rel": [223, 224, 225, 226, 227, 228, 230, 231],
        "pre": [223],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
    # #234 invariant #31
    {
        "id": 234,
        "title": "永久 invariant #31: Devika 9 大 Agent 模板",
        "summary": "借鉴章 5 Devika, 9 大角色标准化模板, mavis sub-agent 体系精华",
        "content": "Type: implementation-pattern. 应用: ~/workspace/mavis-devika-template/. 来源: 高强文书第 5 章 §5.1.2. 9 大 Agent: Planner / Researcher / Coder / Action / Runner / Feature / Patcher / Reporter / Decision. 设计理念: 不是 9 个独立 sub-agent, 而是 9 个标准化角色模板. 与 invariant #9 #21 #22 #30 关系紧密. 触发: 设计新 mavis sub-agent / 编排多 Agent 协作 / 创建工作流 skill.",
        "cat": "invariant",
        "rel": [9, 21, 22, 30, 223],
        "pre": [9, 21, 22, 30],
        "proj": ["mavis"],
        "mastery": 5,
        "vc": 0,
        "lv": TODAY,
        "ca": TODAY,
    },
]

# 追加
data.extend(new_nodes)

# 写回
with open(GALAXY_PATH, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"✅ 追加完成")
print(f"   之前节点数: {len(data) - len(new_nodes)}")
print(f"   新增节点数: {len(new_nodes)}")
print(f"   现在节点数: {len(data)}")
print(f"   新节点 ID 范围: {new_nodes[0]['id']} - {new_nodes[-1]['id']}")