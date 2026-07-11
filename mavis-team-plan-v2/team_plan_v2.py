#!/usr/bin/env python3
"""
mavis team plan v3 - 借鉴 CrewAI 4 组件 (2026-07-11)
永久 invariant #21: LangGraph StateGraph = mavis team plan DAG
永久 invariant #35: CrewAI 4 组件 (Role/Goal/Backstory/Tools) = mavis Agent 模板

来源: 高强文书第 14 章 §5.2.2 (基于 CrewAI 的多角色 Agent 应用开发)

CrewAI 4 组件 -> mavis 映射:
- Agent (Role + Goal + Backstory + Tools) -> mavis worker
- Task (description + expected_output + agent) -> mavis 单步任务
- Crew (Agents + Tasks + Process) -> mavis team
- Process (sequential/hierarchical) -> mavis cycle_report 路由

用法: python team_plan_v2.py "<objective>" [max_turns]
"""
# 导入 sys 模块, 用于读取命令行传入的目标参数 (objective) 和最大轮次 (max_turns)
import sys
# 导入 json 模块, 用于序列化与反序列化状态文件 (mavis-state.json, cycle-report.json)
import json
# 导入 os 模块, 用于读取环境变量 (如 LLM 配置) 及获取进程 ID (作为 thread_id)
import os
# 导入 urllib.request 子模块, 用于构造 HTTP POST 请求, 调用 Ollama 兼容的 LLM 接口
import urllib.request
# 导入 urllib.error 子模块, 用于捕获 HTTP 请求过程中可能出现的网络异常 (如超时、URL 错误)
import urllib.error
# 导入 time 模块, 用于在 LLM 调用失败后进行重试等待 (sleep), 防止连续失败
import time
# 从 dataclasses 模块导入 dataclass 装饰器和 field 函数, 用于声明带默认值字段的结构化数据类
from dataclasses import dataclass, field
# 从 datetime 模块导入 datetime 类, 用于生成状态文件的创建时间戳 (ISO 格式)
from datetime import datetime
# 从 pathlib 模块导入 Path 类, 用于以面向对象方式处理文件系统路径 (跨平台兼容)
from pathlib import Path
# 从 typing 模块导入类型提示工具, 用于标注变量、参数和返回值的类型, 增强代码可读性
from typing import List, Dict, Any, Optional, Callable

# === 永久 invariant #12: Ollama 兼容名 + P1.2 改造: 14B 优先 ===
# 定义 LLM 服务的基地址 (OpenAI 兼容端点), 默认指向本地 Ollama 服务的 11434 端口
LLM_BASE = "http://127.0.0.1:11434/v1"
# 定义 LLM 模型链: 从环境变量读取 (MAVIS_LLM_MODELS), 默认为 "qwen2.5:14b,gpt-3.5-turbo"
# 用逗号分割成列表后, 在调用失败时按顺序 fallback 到下一个模型, 实现高可用
LLM_MODELS_CHAIN = os.environ.get("MAVIS_LLM_MODELS", "qwen2.5:14b,gpt-3.5-turbo").split(",")
# 定义每个模型的重试次数: 从环境变量读取 (MAVIS_LLM_RETRY), 默认每个模型重试 2 次
LLM_RETRY_PER_MODEL = int(os.environ.get("MAVIS_LLM_RETRY", "2"))
# 定义 LLM 请求的超时时间 (秒): 从环境变量读取 (MAVIS_LLM_TIMEOUT), 默认 45 秒
LLM_TIMEOUT = int(os.environ.get("MAVIS_LLM_TIMEOUT", "45"))
# 定义重试之间的等待时间 (秒): 从环境变量读取 (MAVIS_LLM_RETRY_SLEEP), 默认等待 2 秒后重试
LLM_RETRY_SLEEP = int(os.environ.get("MAVIS_LLM_RETRY_SLEEP", "2"))

# === 路径配置 ===
# 定义计划目录路径: 用户主目录下的 ~/workspace/mavis-team-plan-v2/
# 用于统一存放 plan 的状态文件和周期报告文件, 保证可复现
PLAN_DIR = Path.home() / "workspace" / "mavis-team-plan-v2"
# 定义状态文件完整路径: 持久化 team plan 状态 (objective, agents, tasks, crew_output, node_history 等)
STATE_FILE = PLAN_DIR / "mavis-state.json"
# 定义周期报告文件完整路径: 记录每个 cycle (周期) 的执行情况, 作为 cycle_report 路由的输入
CYCLE_REPORT = PLAN_DIR / "cycle-report.json"
# 创建计划目录 (递归创建父目录), 如已存在则不报错, 确保状态文件可写
PLAN_DIR.mkdir(parents=True, exist_ok=True)


# === LLM 工具 (同 mavis-devika-runtime) ===

def call_llm(system: str, user: str, timeout: Optional[int] = None) -> str:
    """调用 Ollama (OpenAI 兼容 API), 支持 retry + 多模型 fallback 链
    
    参数:
        system: 系统提示词 (system prompt), 用于定义 LLM 的角色与行为约束
        user: 用户消息 (user prompt), 即用户的具体问题或任务描述
        timeout: 本次请求的超时时间 (秒), 若为 None 则使用全局默认 LLM_TIMEOUT
    
    返回:
        LLM 返回的文本内容; 若所有模型重试均失败, 返回带 [LLM_FALLBACK_FAILED] 前缀的错误说明
    """
    # 若调用方未指定超时, 则回退到全局默认超时配置 LLM_TIMEOUT
    if timeout is None:
        timeout = LLM_TIMEOUT
    # last_error 用于保存最后一次失败的错误信息, 在所有尝试都失败时回传给上层
    last_error = None
    # 外层循环: 依次遍历模型链中的每个模型, 失败时自动 fallback 到下一个
    for model in LLM_MODELS_CHAIN:
        # 去除模型名前后可能存在的空白字符 (例如 " qwen2.5:14b " 可能多出空格)
        model = model.strip()
        # 内层循环: 对当前选中的模型进行多次重试, 次数由 LLM_RETRY_PER_MODEL 决定
        for attempt in range(1, LLM_RETRY_PER_MODEL + 1):
            try:
                # 构造符合 OpenAI Chat Completions API 格式的请求体 payload
                payload = {
                    "model": model,                                 # 指定要调用的模型名
                    "messages": [
                        {"role": "system", "content": system},      # 系统消息: 定义角色和行为
                        {"role": "user", "content": user}            # 用户消息: 具体问题或任务
                    ]
                }
                # 构造 HTTP POST 请求对象: 目标是 LLM_BASE + /chat/completions 端点
                req = urllib.request.Request(
                    f"{LLM_BASE}/chat/completions",
                    # 请求体: 将 payload 序列化为 JSON 字符串并编码为 UTF-8 字节流
                    data=json.dumps(payload).encode("utf-8"),
                    # 请求头: 声明 body 类型为 JSON
                    headers={"Content-Type": "application/json"},
                    # 请求方法显式设为 POST (urllib 默认 GET, 必须指定)
                    method="POST"
                )
                # 使用 urlopen 发送请求并设置超时, with 语句保证响应对象被正确关闭
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    # 读取 HTTP 响应的字节内容并解析为 JSON 字典
                    data = json.loads(resp.read())
                    # 按 OpenAI 响应格式提取模型输出文本 (choices[0].message.content)
                    content = data["choices"][0]["message"]["content"]
                    # 成功拿到响应, 直接返回内容给调用方
                    return content
            # 捕获网络相关异常: 超时、URL 错误、连接中断等
            except (TimeoutError, urllib.error.URLError, ConnectionError) as e:
                # 记录本次失败信息, 截取异常描述的前 200 字符以避免日志过长
                last_error = f"[{model} attempt {attempt}] {type(e).__name__}: {str(e)[:200]}"
                # 若尚未达到最大重试次数, 则等待一段时间再试, 避免立即重试造成连续失败
                if attempt < LLM_RETRY_PER_MODEL:
                    time.sleep(LLM_RETRY_SLEEP)
                # 进入下一次重试
                continue
            # 捕获其他未知异常 (如 JSON 解析错误、键不存在等非网络问题)
            except Exception as e:
                # 记录失败信息; 这种错误通常与当前模型实现相关, 直接跳出当前模型重试, 试下一个模型
                last_error = f"[{model}] {type(e).__name__}: {str(e)[:200]}"
                break
    # 模型链中所有模型、所有重试均失败, 返回带错误前缀的占位符, 告知上层 LLM 调用失败
    return f"[LLM_FALLBACK_FAILED] {last_error}"


# === CrewAI 4 组件 (借鉴第 14 章 §5.2.2) ===

@dataclass
class Agent:
    """CrewAI Agent 4 组件: Role + Goal + Backstory + Tools
    
    数据类: 对应 CrewAI 4 中的 Agent 概念, 4 个核心要素:
    - Role     (角色): Agent 的身份定位
    - Goal     (目标): Agent 要达成的具体目标
    - Backstory(背景): Agent 的专业背景与能力描述 (用于引导 LLM 更好地扮演角色)
    - Tools    (工具): Agent 可以调用的函数列表
    
    在 mavis 中, Agent 映射为 worker (具体执行任务的角色单元)。
    """
    # 角色名 (例如 "系统分析师"), 用于标识 Agent 的身份, 也是 build_system_prompt 的关键输入
    role: str
    # 目标 (例如 "进行需求分析"), 描述 Agent 要完成的核心任务
    goal: str
    # 背景知识 (例如 "在专业企业工作..."), 用上下文激发 LLM 的角色扮演深度
    backstory: str
    # 可用工具列表: 类型为可调用对象列表; 使用 default_factory=list 避免可变默认值共享陷阱
    tools: List[Callable] = field(default_factory=list)
    # 是否允许委派任务给其他 Agent: CrewAI 4 的特性; 默认 False, 即不参与委派
    allow_delegation: bool = False
    # 是否输出详细日志: 用于调试时观察 Agent 内部决策; 默认 False
    verbose: bool = False

    def build_system_prompt(self) -> str:
        """借鉴第 14 章: 由 role + goal + backstory 拼接成 LLM 的系统提示词
        
        返回:
            拼装好的中文系统提示词字符串, 将作为 LLM 调用时的 system message
        """
        # 若允许委派, 则追加一段说明; 否则留空, 避免干扰 LLM 行为
        delegation_note = "你可以委派任务给其他 Agent。" if self.allow_delegation else ""
        # 用 f-string 拼接角色、目标、背景与委派说明, 形成完整的 system prompt
        return f"""你是{self.role}。

🎯 目标: {self.goal}

📚 背景: {self.backstory}

{delegation_note}
"""


@dataclass
class Task:
    """CrewAI Task: description + expected_output + agent
    
    任务类: 表示 CrewAI 中的单个任务, 包含任务描述、期望输出与负责 Agent。
    支持通过 context_from 字段表达任务间的依赖, 由 Process 在编排时串联上下文。
    """
    # 任务描述: 详细说明该任务要做什么
    description: str
    # 期望输出: 描述任务最终输出应满足的格式与内容要求 (用于引导 LLM 输出)
    expected_output: str
    # 负责该任务的 Agent: 引用一个 Agent 实例, 决定调用时使用哪个角色提示词
    agent: Agent
    # 上游任务: Process 编排时, 当前任务的 context 来自上游任务的输出; 默认为 None 即无依赖
    context_from: Optional['Task'] = None
    # 任务输出结果: 任务执行后由 Process 填充, 初始为空字符串
    output: str = ""


class Process:
    """CrewAI Process: 顺序/层次 编排
    
    流程编排类: 负责按指定模式 (sequential / hierarchical) 依次执行一组 Task。
    负责将上游任务输出作为下游任务的 context, 串成完整的协作链路。
    """
    def __init__(self, tasks: List[Task], mode: str = "sequential"):
        # 缓存所有要执行的任务列表
        self.tasks = tasks
        # 编排模式: "sequential" 顺序执行, "hierarchical" 层次执行; 默认顺序
        self.mode = mode

    def run(self) -> List[Task]:
        """执行所有任务, 上游任务的输出自动作为下游任务的 context
        
        返回:
            执行完成的任务列表 (每个 task 的 output 字段已被填充)
        """
        # 顺序遍历 self.tasks, 按列表顺序逐个执行
        for i, task in enumerate(self.tasks):
            # 打印当前任务的执行进度, 取 description 前 60 字符避免刷屏
            print(f"\n📌 Task {i+1}/{len(self.tasks)}: {task.description[:60]}...")

            # 准备 context: 若存在上游任务且其输出非空, 则把上游输出包裹进本任务的描述
            if task.context_from and task.context_from.output:
                # 构造带上下文的任务描述: 先展示上游任务描述与输出, 再引出本任务
                task_with_context = f"""上游任务 ({task.context_from.description[:30]}) 的输出:
{task.context_from.output}

---

本任务 ({task.description}):"""
            else:
                # 没有上游依赖, 直接使用本任务的原始描述
                task_with_context = task.description

            # 构造用户消息: 把任务描述与期望输出拼接, 引导 LLM 按期望格式产出
            user_msg = f"""任务: {task_with_context}

期望输出: {task.expected_output}

请完成这个任务。"""
            # 调用 LLM: 使用负责 Agent 的 system prompt 与刚构造的 user_msg
            # LLM 返回内容会写回 task.output, 实现任务的"完成"
            task.output = call_llm(task.agent.build_system_prompt(), user_msg)
            # 打印结果摘要 (前 150 字符), 便于观察每个 Agent 的输出概况
            print(f"   Agent ({task.agent.role}) 输出 ({len(task.output)} 字符): {task.output[:150]}...")

        # 全部任务执行完毕, 返回 self.tasks (此时每个 task.output 已被填充)
        return self.tasks


class Crew:
    """CrewAI Crew: Agents + Tasks + Process
    
    团队类: 把多个 Agent 与多个 Task 组装成协作团队, 由 Process 负责编排与执行。
    在 mavis 中, Crew 映射为 team (团队), 是 team_plan 的核心调度单位。
    """
    def __init__(self, agents: List[Agent], tasks: List[Task], process_mode: str = "sequential"):
        # 缓存团队成员: 所有 Agent (角色) 列表
        self.agents = agents
        # 缓存团队任务: 所有 Task (任务) 列表
        self.tasks = tasks
        # 创建 Process 实例, 用于编排任务执行顺序; 默认 sequential
        self.process = Process(tasks, mode=process_mode)

    def kickoff(self) -> List[Task]:
        """启动 Crew, 调用 Process 执行全部任务
        
        返回:
            已执行完毕的任务列表
        """
        # 打印启动横幅: 显示 agent 数 / task 数 / 编排模式, 方便观察本次 kickoff 规模
        print(f"\n🚀 Crew kickoff: {len(self.agents)} agents, {len(self.tasks)} tasks, mode={self.process.mode}")
        # 委托给 Process.run 执行所有任务并返回
        return self.process.run()


# === 主流程 (mavis crew v3) ===

def init_state(objective: str, max_turns: int) -> dict:
    """初始化状态文件, 写入初始状态信息
    
    参数:
        objective: 用户的目标 (任务描述)
        max_turns: team plan 的最大循环轮次
    
    返回:
        初始化好的状态字典 (同时也已持久化到 STATE_FILE)
    """
    # 构造初始 state: 包含目标/时间/线程 id/最大轮次/版本以及空集合占位
    state = {
        "objective": objective,                              # 用户的目标
        "created_at": datetime.now().isoformat(),            # 创建时间, 用 ISO 格式便于跨语言解析
        "thread_id": os.getpid(),                            # 用进程 ID 作为 thread_id, 区分并发实例
        "max_turns": max_turns,                              # team plan 允许的最大循环轮次
        "version": "v3 (CrewAI 4 组件)",                     # 版本标识, 后续演进做兼容判定
        "agents": [],                                        # Agent 列表占位 (稍后由 build_default_crew 填充)
        "tasks": [],                                         # Task 列表占位
        "crew_output": [],                                   # 历次 Crew 执行的输出汇总
        "node_history": []                                   # LangGraph 节点历史, 用于 invariant #21 的可观测性
    }
    # 把 state 序列化为格式化的 JSON, ensure_ascii=False 以保留中文; indent=2 让文件可读
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    # 同时把内存中的 state 返回, 供后续 run_crew 直接复用
    return state


def update_state(state: dict):
    """把当前内存中的 state 字典覆盖写入 STATE_FILE (持久化)
    
    参数:
        state: 当前内存里维护的状态字典
    """
    # 用格式化的 JSON 覆盖原 state 文件, ensure_ascii=False 保留中文, indent=2 便于 diff
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_default_crew(objective: str) -> Crew:
    """构建默认的 3 角色 Crew (借鉴第 14 章: 系统分析师 / 设计师 / 审核员)
    
    参数:
        objective: 用户的原始目标, 会作为 Analyst Task 的输入
    
    返回:
        组装好的 Crew 实例: 3 个 Agent + 3 个串行 Task
    """
    # 1. 系统分析师 (Analyst): 负责对用户目标进行需求分析, 并允许委派任务
    analyst = Agent(
        role="系统分析师",                                                        # 角色: 系统分析师
        goal="按照用户提出的任务, 进行需求分析, 撰写系统需求报告",                # 目标: 出系统需求报告
        backstory="""你在一家专业设计企业工作。
你的专长在于掌握各种专业系统分析的原则。
你具有需求分析、任务分解等技能。""",                                        # 背景: 专业企业, 强调分析能力
        allow_delegation=True,                                                   # 允许把子任务委派给其他 Agent
    )

    # 2. 系统设计师 (Designer): 根据需求报告给出可落地的设计方案
    designer = Agent(
        role="系统设计师",                                                        # 角色: 系统设计师
        goal="按照系统分析师的需求报告, 撰写详细的设计方案 (含技术选型 + 模块设计 + 实施步骤)",  # 目标: 输出设计方案
        backstory="""你在一家专业设计企业工作。
你的专长在于掌握各种专业系统的设计原则。
你具有系统模块设计、技术选型、公式推导等技能。""",                            # 背景: 专业设计背景
        allow_delegation=False,                                                  # 不允许委派 (Designer 自己出方案)
    )

    # 3. 质量审核员 (Reviewer): 对设计方案做最终评审
    reviewer = Agent(
        role="质量审核员",                                                        # 角色: 质量审核员
        goal="审核设计师的方案, 评估可行性 + 完整性 + 风险, 给出改进建议",        # 目标: 出审核与改进建议
        backstory="""你是资深技术专家, 有 10 年架构经验。
你的专长是发现方案中的潜在问题和改进点。""",                                  # 背景: 10 年架构经验
        allow_delegation=False,                                                  # 不允许委派 (Reviewer 自己闭环评审)
    )

    # 3 个 Task 串行组成工作流: Analyst -> Designer -> Reviewer
    # Task 1: 分析师输出系统需求报告 (没有上游)
    analyst_task = Task(
        description=f"分析用户目标: {objective}",                                 # 任务描述: 把 objective 作为分析对象
        expected_output="一份系统需求报告 (含功能需求 + 非功能需求 + 约束条件)",   # 期望输出: 需求报告结构
        agent=analyst,                                                            # 负责人: 系统分析师
    )
    # Task 2: 设计师根据需求报告设计方案 (上游 = analyst_task)
    designer_task = Task(
        description="根据系统需求报告, 撰写详细设计方案",                          # 任务描述: 基于需求做设计
        expected_output="一份技术设计方案 (含架构 + 模块 + 实施步骤 + 风险)",     # 期望输出: 设计方案结构
        agent=designer,                                                           # 负责人: 系统设计师
        context_from=analyst_task,                                                # 依赖: 分析师的需求报告
    )
    # Task 3: 审核员对方案做评审 (上游 = designer_task)
    reviewer_task = Task(
        description="审核技术方案, 给出最终评估",                                  # 任务描述: 审核设计方案
        expected_output="一份审核报告 (含总体评价 + 改进建议 + 评分 1-10)",         # 期望输出: 审核报告 + 量化评分
        agent=reviewer,                                                           # 负责人: 质量审核员
        context_from=designer_task,                                               # 依赖: 设计师的方案
    )

    # 把 3 个 Agent 和 3 个串行 Task 组装成 Crew, 默认顺序执行
    return Crew(
        agents=[analyst, designer, reviewer],
        tasks=[analyst_task, designer_task, reviewer_task],
        process_mode="sequential"                                                 # 顺序编排: Analyst -> Designer -> Reviewer
    )


def run_crew(objective: str, max_turns: int = 3):
    """主入口: 初始化状态 -> 构造默认 Crew -> 跑 -> 把结果落盘
    
    参数:
        objective: 用户的目标 (任务描述)
        max_turns: team plan 的最大循环轮次 (默认 3)
    """
    # 打印分隔线和标题, 让 CLI 输出有清晰的视觉分块
    print("=" * 60)
    print("mavis team plan v3 - 借鉴 CrewAI 4 组件")
    # 强调永久 invariant #21, 标记本流程遵守 LangGraph StateGraph 的 DAG 约束
    print("永久 invariant #21: LangGraph StateGraph")
    # 强调永久 invariant #35, 标记 CrewAI 4 组件到 mavis Agent 模板的等价映射
    print("永久 invariant #35: CrewAI 4 组件 (Role/Goal/Backstory/Tools) = mavis Agent 模板")
    print(f"📌 Objective: {objective}")                                            # 打印用户原始目标
    print(f"📌 max_turns: {max_turns}")                                             # 打印最大轮次
    print("=" * 60)

    # 1) 初始化状态文件, 拿到初始 state
    state = init_state(objective, max_turns)

    # 2) 用默认 3 角色模板构建 Crew
    crew = build_default_crew(objective)

    # 3) 把 Crew 中各个 Agent 的关键字段写回 state (持久化), 便于后续 cycle_report 复盘
    state["agents"] = [
        {
            "role": a.role,                          # Agent 角色名
            "goal": a.goal,                          # Agent 目标
            "allow_delegation": a.allow_delegation,  # 是否允许委派
        }
        for a in crew.agents                         # 遍历 crew.agents 依次展开
    ]
    # 把 Crew 中各个 Task 的字段写回 state (持久化), 表达本轮的 DAG 形状
    state["tasks"] = [
        {
            "description": t.description,                       # Task 描述
            "expected_output": t.expected_output,               # Task 期望输出
            "agent_role": t.agent.role,                         # Task 负责人 (用角色名表达)
            "context_from_idx": (
                crew.tasks.index(t.context_from)                # 上游 task 在 crew.tasks 中的下标
                if t.context_from is not None else None          # 无依赖则为 None
            ),
        }
        for t in crew.tasks                                     # 遍历每个任务
    ]
    # 立即落盘, 这样中断也能保留本轮的 DAG 快照
    update_state(state)

    # 4) 启动 Crew: 真正依次调用 3 个 Agent, 写入每个 Task 的 output
    tasks = crew.kickoff()

    # 5) 收集 Crew 的输出, 并写回到 state["crew_output"], 作为后续 cycle_report 的输入
    state["crew_output"] = [
        {
            "task_idx": i,                  # 任务在 crew.tasks 中的下标
            "agent_role": t.agent.role,     # 负责 Agent 角色名
            "description": t.description,   # 任务描述 (用于回溯)
            "output": t.output,             # Agent 实际输出
            "output_len": len(t.output),    # 输出长度, 便于做异常监控
        }
        for i, t in enumerate(tasks)        # 遍历执行后的任务列表
    ]
    # 追加一条节点历史, 实现 invariant #21 要求的状态图可追溯性
    state["node_history"].append({
        "node": "crew_kickoff",             # 节点名: Crew 启动
        "ts": datetime.now().isoformat(),   # 执行时间戳
        "task_count": len(tasks),           # 本次执行的任务数
        "total_chars": sum(len(t.output) for t in tasks),  # 所有输出总字符数
    })
    # 再落一次盘, 保留本轮完整 crew_output 与 node_history
    update_state(state)

    # 6) 生成一份简单的 cycle_report, 落到 CYCLE_REPORT, 供 cycle_report 路由消费
    cycle_report = {
        "cycle": 1,                                               # 第几个 cycle (此处固定 1)
        "objective": objective,                                   # 用户目标, 用于匹配后续 cycle
        "max_turns": max_turns,                                   # 最大轮次
        "agents": state["agents"],                                # Agent 列表 (与 state 一致)
        "crew_output": state["crew_output"],                      # Crew 输出快照
        "summary": tasks[-1].output[:500] if tasks else "",       # 取最后一个任务的输出前 500 字作为摘要
        "ts": datetime.now().isoformat(),                         # 报告生成时间
    }
    # 把 cycle_report 写入 CYCLE_REPORT, ensure_ascii=False 保留中文
    CYCLE_REPORT.write_text(
        json.dumps(cycle_report, ensure_ascii=False, indent=2),    # 序列化
        encoding="utf-8"                                          # 显式 UTF-8
    )

    # 7) CLI 友好输出: 把每个 Task 的执行结果快速呈现给用户
    print("\n" + "=" * 60)
    print("📊 Crew 执行结果")
    print("=" * 60)
    for i, t in enumerate(tasks):                         # 依次遍历每个已完成任务
        # 用 3 字段展示: 序号 / 角色 / 任务摘要 / 输出前 200 字
        print(f"\n[Task {i+1}] {t.agent.role} - {t.description[:40]}")
        print(f"   输出 ({len(t.output)} 字符): {t.output[:200]}...")
    # 给出下一步提示, 引导用户复盘或继续迭代
    print(f"\n✅ 状态已写入: {STATE_FILE}")
    print(f"✅ 周期报告已写入: {CYCLE_REPORT}")


# === CLI 入口 ===
if __name__ == "__main__":
    # 解析命令行参数: 第 1 个位置参数为目标 (objective), 第 2 个为可选的最大轮次
    # 若命令行参数不足, 给出用法提示并直接退出
    if len(sys.argv) < 2:
        print("用法: python team_plan_v2.py \"<objective>\" [max_turns]")   # 用法提示
        sys.exit(1)                                                          # 非 0 退出码表示参数错误
    # 取出 objective 参数 (允许其中包含空格)
    objective_arg = sys.argv[1]
    # 取出可选的 max_turns, 默认为 3; 若用户提供则转 int, 失败回退 3
    try:
        max_turns_arg = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    except ValueError:
        # 用户传了非数字, 友好退化到默认 3 而不让脚本崩溃
        max_turns_arg = 3
    # 把解析结果交给主入口 run_crew
    run_crew(objective_arg, max_turns_arg)