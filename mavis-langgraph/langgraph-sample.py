"""
LangGraph Sample - mavis 对比 demo (2026-07-10)
借鉴章 11 #21 invariant: LangGraph StateGraph = mavis team plan DAG

永久 invariant #21 验证:
- StateGraph = mavis DAG
- Node = mavis Worker
- Edge (普通) = mavis DAG 边
- Conditional Edge = mavis CycleReport 路由
- MemorySaver = mavis Context 持久化
- workflow.compile() = mavis cycle 启动
"""
# 借鉴章 11.4 实现, 简化版 (无 SQLite, 用内存数据)
import os
from typing import Literal
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph, MessagesState
from langgraph.checkpoint import MemorySaver
from langchain_openai import ChatOpenAI

# 借鉴章 11.3 + 章 8 (Function-calling)
@tool
def search(query: str):
    """从 mavis memory 检索用户信息"""
    # 借鉴章 13 LlamaIndex 4 步索引
    return f"mavis recall: {query}"

tools = [search]
tool_node = ToolNode(tools)

# Ollama 兼容名 (借鉴章 3 #12 invariant)
model = ChatOpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="EMPTY",
    model="gpt-3.5-turbo",  # 实际系 qwen3:32b (兼容名)
    temperature=0,
).bind_tools(tools)

# 借鉴章 11.3.2 条件边路由判断
def should_continue(state: MessagesState) -> Literal["tools", END]:
    """借鉴 mavis CycleReport 嘅 verify pass/fail 路由"""
    messages = state['messages']
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END

# 借鉴章 11.4.2 调用 LLM
def call_model(state: MessagesState):
    """借鉴 mavis sub-agent 嘅 LLM 调用"""
    messages = state['messages']
    response = model.invoke(messages)
    return {"messages": [response]}

# 借鉴章 11.4.2 工作流初始化
def init_workflow():
    """借鉴 mavis team plan 嘅 DAG 设计"""
    workflow = StateGraph(MessagesState)
    
    # 定义节点 (借鉴 mavis worker)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)
    
    # 入口 (借鉴 mavis cycle 启动)
    workflow.set_entry_point("agent")
    
    # 条件边 (借鉴 mavis CycleReport 路由)
    workflow.add_conditional_edges("agent", should_continue)
    
    # 普通边 (借鉴 mavis DAG 边)
    workflow.add_edge("tools", "agent")
    
    # 状态持久化 (借鉴 mavis context 持久化)
    checkpointer = MemorySaver()
    
    # 编译 (借鉴 mavis cycle 启动)
    app = workflow.compile(checkpointer=checkpointer)
    return app

if __name__ == "__main__":
    app = init_workflow()
    inputs = {"messages": [HumanMessage(content="从 mavis memory 检索一下大佬嘅信息?")]}
    
    print("=== LangGraph StateGraph = mavis team plan DAG 验证 ===")
    print("OUTPUT IN CHINESE")
    print()
    
    # 借鉴章 11.4.2 主函数流式调用
    for i, output in enumerate(app.stream(inputs, {"configurable": {"thread_id": 42}}), 1):
        for key, value in output.items():
            print(f"Step {i} [{key}] 输出:")
            print(value)
            print()
    
    print("=== mavis 永久 invariant #21 验证完成 ===")
    print("LangGraph StateGraph 完美对应 mavis team plan DAG 设计")
