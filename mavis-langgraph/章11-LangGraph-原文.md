# 第11章 基于 LangGraph 的工作流 Agent 应用开发

**段落范围**: 3939 - 4158 (220 段)

---

11.1 开发要点

☐应用场景：开发Agent应用，使其通过工作流配置，查询本地数据库完成用户设定的任务。

☐大语言模型：GLM-4-9B-Chat，通过GLM-4专用服务程序装载和提供API服务。

☐应用部署方式：Agent应用与LLM服务采用同机部署或异机部署。

☐应用访问方式：控制台操作。

11.2 案例场景

大语言模型基于统计和概率来生成文本，在训练过程中，通过大量的语言数据

学习词语之间的关系和上下文，但并不直接记忆具体的事实或信息，因此其推理输出是基于概率做出的最佳猜测，而不是精确的信息。

Agent模拟人类的智能，通过ReAct等思考框架，经提示词与大语言模型配合完成人类提出的任务，所以Agent应用与传统软件的区别在于Agent应用的不确定性，一定程度上可将其看成一种“黑盒”。因此，Agent开发过程中遇到较多的问题是对程序流程梳理困难。LangGraph采取的是预先定义流程图的方式，固定Agent应用运行中各个组件的依赖关系和流程走向，将一些不透明的、难以理解的跳转、循环，以开发者容易理解的流程图定义方式表示出来。程序运行过程也依流程执行，避免程序运行路径的不确定性。

本章例子是一个RAG应用，用户输入的问题以消息方式进入工作流中，按工作流中定义的入口、节点、判断和循环进行流转。在运行过程中会调用LLM生成工具用到的入参。Agent通过工具查询数据库，得到的结果再由LLM进行总结。

11.3 关键原理

11.3.1 基本概念

图是一种数据结构，由节点和边组成：节点表示实体或对象，在LangGraph中，节点表示Agent或工具；边表示节点之间的关系，如按顺序执行或根据条件判断消息是否从一个节点流转到另一个节点。LangGraph将Agent工作流建模成图的表示方式，使用消息状态、节点和边三个关键组件来定义Agent的行为。

（1）状态图（StateGraph）

状态图是图的一种特殊形式，通过消息状态（MessagesState）保存消息在流程中的不同状态。状态图中的每个节点代表计算的一个步骤，整个状态图维护一个状态。这个状态随着计算的进行而不断传递和更新。

（2）节点（Node）

节点是LangGraph的基本执行单元，每个节点代表一个特定的功能或计算步骤，如处理输入、做出决策或调用外部工具。

（3）边（Edge）

边用于连接图中的节点，定义计算的流程控制。LangGraph支持条件边，允许根据图的当前状态动态决定下一个执行的节点。LangGraph中的普通边在工作流中按顺序执行。

（4）编译（Compile）

图的编译与高级计算机语言的编译的概念相同：编译过程是对图的结构进行一些基本校验，比如检查有无孤立节点等；编译的结果是一种名为“LangChain Runnable”的可执行单元，可调用它的invoke或stream方法运行。

11.3.2 工作流定义

LangGraph的工作流使用状态图实现，其配置过程与绘制图形化的流程图相似。图11-1是用传统流程图的方式来表现状态图定义的结果。

图11-1 状态图工作示意图

按本章案例的业务逻辑，定义一个LangGraph状态图，进行以下操作。

（1）定义节点

本例中用到两个节点，一个是Agent，在消息流转到此节点时会调用LLM推理生成Function-calling类型的文本或普通文本；另一个是工具调用，消息流转到此节点时会从SQLite数据库查询数据。

（2）设置工作流入口

定义工作流的人口点为Agent节点，这样用户的输入消息进入工作流后，会首

ΘLangChain开发框架中的可执行单元。可以类比为Windows里的可执行文件、Android系统的APK等。

先流转到Agent节点。

（3）添加条件边

条件边是一种路由，根据消息的内容判断工作流的走向，在本例中，条件边被定义成在Agent执行时判断下一步的操作。如果Agent调用LLM返回的消息中包含Function-calling相关内容，则流程转向工具调用。如果返回的是普通消息，则中止工作流，将消息反馈给用户。

（4）添加普通边

普通边中的节点，会在工作流中按顺序执行。按本例普通边的设定，调用完工具后，会将消息又流回Agent。这样就形成一个循环，循环的退出条件是LLM推理的结果中不含Function-calling。其中不含Function-calling的原因有两种：一是用户的输入问题未命中工具函数；二是LLM的返回结果是对上一次循环中的“用户输入＋工具调用结果”的总结，这意味着LLM“主动”要求结束循环。

11.4 实现过程

11.4.1 环境安装

1．建立虚拟环境

＃创建虚拟环境

conda create -n langgraph python=3.10 -y

＃激活虚拟环境

conda activate langgraph

＃安装依赖库langgraph

pip install langgraph==0.1.6\

-i https://pypi.mirrors.ustc.edu.cn/simple

＃安装依赖库httpx

pip install httpx==0.27.0\

-i https://pypi.mirrors.ustc.edu.cn/simple

＃安装依赖库langchain-openai

pip install langchain-openai==0.1.17\

-i https://pypi.mirrors.ustc.edu.cn/simple

2．大语言模型服务安装配置

vLLM启动的大语言模型API服务对包含tools节点的OpenAI兼容接口调用支持存在问题，本章使用2.2.3节的方法开启GLM-4-9B-Chat模型服务。如果采用Ollama 开启OpenAI兼容接口服务，程序运行虽不报错，但LangGraph框架无法使用大模

型的Function-calling特性。这样消息进入工作流入口，由LLM推理的结果中不包含Function-calling，导致消息进入工作流的条件边时，直接中止工作流。从用户端看到的是工作流只执行了一步，也就是大模型直接回答了用户的问题，没有执行后续的工具调用环节。

11.4.2 源代码

名为langgraph-sample.py的样例程序，包括依赖库导入、数据库访问、工具定义、条件边路由判断、调用LLM、工作流初始化和主函数几个部分。

1．依赖库导入

本样例依赖库较多，我们在表11-1中详细解释其用途。

表11-1 langgraph-sample 依赖库

源码如下：

import os

import sqlite3

from typing import Literal

from langchain_core.messages import HumanMessage

from langchain_core.tools import tool

from langgraph.prebuilt import ToolNode

from langgraph.graph import END, StateGraph, MessagesState

from langgraph.checkpoint import MemorySaver

from langchain_openai import ChatopenAI

2．数据库访问

下面通过从数据库查询数据的过程来讲解LangGraph中工具获取外部资源的能力。访问SQLite数据库的方法已包含在Python的内置库中，在Python代码中可以方便地建库、建表和操作数据。在本例中我们建一个名为test.db的数据库，在库里建一张users表，并插入两条测试数据。

def init_db() :

nn初始化数据库信息nnn

if not os.path.exists('test.db'):

conn = sqlite3.connect('test.db')

c= conn.cursor()

c.execute('''create table users

(id int primary key not null,

name varchar not null,

mail varchar not null);)

c.execute("insert into users (id, name, mail) " +

"values (1, 'John', 'john@test.com')")

c.execute("insert into users (id, name, mail) " +

"values (2, 'Tom', 'tom@test.com')")

conn.commit()

conn.close()

def query_from_db(sql: str):

n11使用SQL语句从数据库查询信息

conn = sqlite3.connect('test.db')

c= conn.cursor()

c.execute(sql)

rows = c.fetchall()

conn.close()

return rows

3．工具定义

工具函数通过“＠tool”注解代替冗长的JSON格式的声明。由于Agent调用LLM 返回的Function-calling文本解析后，函数的参数已被LLM推理生成为带有where条件的SQL®语句，所以工具实现部分比较简单，直接调用query_from_db方法传入SQL，得到的结果是从users表中查出的用户记录。工具函数search，作为tools的一部分，被ToolNode类定义成工具节点。tools与大语言模型调用接口类配合，形成模型类，供后续的方法用来调用LLM。需要特别注意的是，这个“”从数据库查

使用JSON声明工具的方法见本书8.4.2节的工具定义。

Structured Query Language，结构化查询语言，是一种数据库查询和程序设计语言，用于查询、更新和管理关系数据库。

询用户信息＂”不是一般的注释，“＠tool”会把这个注释解析为工具声明中的方法功能说明，这是要传递给大语言模型的。

@tool

def search(query: str):

nnn从数据库查询用户信息

return str(query_from_db(query))

tools = [search]

toolnode=ToolNode(tools)

api_key="EMPTY", temperature=0).bind_tools(tools)

4．条件边路由判断

should_continue是一个逻辑分支判断函数，是Agent执行的后置动作。消息状态中的消息包含整个工作流程的历史消息。通过消息状态中的消息内容，可以判断最后一条消息中是否包含Function-calling相关内容，决定工作流的下一步走向。

def should_continue(state: MessagesState) -> Literal["tools", END]:

定义继续条件

messages = state['messages']

last_message = messages[-1]

＃如果LLM命中了tool call，则路由到tools节点

if last_message.tool_calls:

return "tools"

＃否则将LLM的返回内容回复给用户，结束对话

return END

5．调用LLM

经ChatOpenAI封装的model变量是简单易用的，它会从消息状态中取出所有消息列表，一起传给LLM，同步等待LLM返回后将结果返回给调用者。

def call_model(state: MessagesState):

1Agent调用LLM的方法

messages = state['messages']

response = model.invoke(messages)

return {"messages": [response])

6．工作流初始化

工作流初始化以状态图管理消息状态和控制流程。定义Agent和tools两个节点，其中Agent节点的执行方法是调用LLM,tools节点的执行方法是调用工具函数。

工作流的入口被设定为Agent节点，这也就意味着用户输入的消息进入工作流后，首先会被组织成提示词用于Agent调用LLM。如果提示词的内容经LLM进行语义理解，能够命中工具，则会返回Function-calling相关的内容。这个命中的过程依赖于提示词与工具的相关性、大语言模型的Function-calling特性和推理能力。

条件边的分支判断动作发生在Agent调用之后，should_continue方法执行了具体的流程路由工作，Function-calling消息会流转到工具调用，普通消息意味着工作流的中止。普通边的定义规定了工具调用之后要再次回到Agent节点，这就使得工作流形成闭环，直到下次Agent调用LLM返回不含Function-calling的消息时，条件边路由的判断又会起作用，将消息引到工作流的出口，工作流的生命周期结束，用户也得到了问题的最终答案。

状态图中的消息状态保持，需要MemorySaver的参与。工作流的定义要经过编译，检查配置的正确性，然后生成LangChain Runnable可执行单元。至此，工作流准备就绪。

def init_workflow() :

＃创建状态图以管理消息状态和流程控制

workflow = StateGraph(MessagesState)

＃定义将循环运行的两个节点

workflow.add_node("agent", call model)

workflow.add_node("tools", tool_node)

＃定义工作流的入口点为agent节点

workflow.set_entry_point("agent")

＃添加条件边，当agent被调用时判断是否继续流转

workflow.add_conditional_edges(

"agent",

should_continue,

)

＃添加两个普通边，tools被调用完后，继续调用agent

workflow.add_edge("tools", 'agent!)

＃初始化内存以在状态图运行过程中保持状态

checkpointer = MemorySaver()

＃将工作流编译成一个可执行的App

app = workflow.compile(checkpointer=checkpointer)

return app

7．主函数

主函数中，首先检测数据库是否存在；不存在则新建一个，然后初始化工作流得到一个可执行的单元；这个名为app的执行单元，在接收到用户的输入后，进行

流式（stream）调用，将工作流执行过程的细节显示出来。

if name==

app=∈itworkflow()

[HumanMessage(

cottent="从数据库查询一下id=1的用户信息？”）]｝

i=0

for output in app.stream(

inputs,

: {"thread_id": 42}}):

for key, value in output.items() :

i=i+1

｛key}＇输出："）

print(value)

11.4.3 运行

运行以下命令，观察执行结果，工作流的执行过程如图11-2所示。

＃激活虚拟环境

conda activate langgraph

＃运行程序

python langgraph-sample.py

图11-2 LangGraph的Agent工作流应用运行情况

由图11-2可知，基于LangGraph的Agent应用，通过工作流管理，将LLM调用、Function-calling过程、工具的执行、流程的分支判断、LLM总结等过程按顺序完整地展现出来，消息流转清晰可见，流程控制的设定与执行过程完全一致。这对于读者学习Agent，特别是学习包含工具调用的Agent大有帮助。

第12 章

基于AutoGen的辅助编程Agent应用开发

AutoGen是由微软、宾夕法尼亚州立大学和华盛顿大学合作研究创建的一个开源智体编程框架，用于构建AI智体，并促进多个智体之间的协作以解决用户提出的任务。AutoGen的开发初衷是简化智体的开发和研究，就像PyTorch之于深度学习所起的作用。AutoGen提供了一些开发智体所必需的功能，例如：能够彼此交互的智体、对各种大语言模型和工具的支持、人机交互的自主工作流程以及对多智体对话模式的支持等。

多智体对话框架，是AutoGen的核心功能，通过多个角色的智体，实现专业问题的解决、检索增强对话、成组对话决策、多智体编码、动态分组对话和棋类游戏制作等。在AutoGen的文档中包含有大量的例程和讲解。而在实际应用中，这些例程往往依赖于OpenAI等大语言模型的服务能力和精心准备的运行环境，通常情况下也没有图形界面可供选择，实践起来有一定困难。本章通过AutoGen嵌套对话（Nested Chats）流程，与部署于本地的大语言模型配合，再辅以Gradio组件开发的用户UI，构建一个软件辅助开发应用，使读者可以掌握AutoGen多智体交互的开发方法和理念。

