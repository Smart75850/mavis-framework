"""
mavis BabyAGI-style 任务 Agent (2026-07-10)
借鉴章 4 BabyAGI 6 步循环 (#29 invariant)

永久 invariant #29:
1. 选取未完成任务
2. 执行当前任务 (LLM 推理)
3. 保存执行结果 (向量数据库)
4. 创建新任务 (LLM 分解)
5. 重排任务优先级 (LLM 排序)
6. 保存任务列表
"""
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate  # langchain 1.0+ 路径

# Ollama 兼容名 (借鉴章 3 #12 invariant)
llm = ChatOpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="EMPTY",
    model="gpt-3.5-turbo",  # 兼容名, 实际系 qwen3:32b
    temperature=0.9
)

class MavisBabyAGI:
    def __init__(self, objective: str):
        self.objective = objective
        self.tasks = [{"task_id": 1, "task_name": "Develop a task list"}]
        self.task_id_counter = 1
    
    def cycle(self):
        """借鉴 BabyAGI 6 步循环 (#29)"""
        if not self.tasks:
            return None
        
        # 1. 选取未完成任务
        task = self.tasks.pop(0)
        print(f"[1/6] 选取任务 #{task['task_id']}: {task['task_name']}")
        
        # 2. 执行当前任务 (LLM 推理)
        execution_prompt = f"OUTPUT IN CHINESE. 根据以下目标执行任务: {self.objective}\n任务: {task['task_name']}"
        result = llm.invoke(execution_prompt).content
        print(f"[2/6] 执行结果: {result[:100]}...")
        
        # 3. 保存执行结果 (向量数据库 - 简化版用 list)
        # 借鉴章 13 LlamaIndex #23: 装载 -> 切分 -> 向量化 -> 存储
        if not hasattr(self, 'completed_tasks'):
            self.completed_tasks = []
        self.completed_tasks.append({"task": task, "result": result})
        print(f"[3/6] 已保存 {len(self.completed_tasks)} 条执行结果")
        
        # 4. 创建新任务 (LLM 分解)
        creation_prompt = f"OUTPUT IN CHINESE. 基于目标 {self.objective} 和当前结果 {result}, 创建 1-3 个新子任务。每行格式: '#.任务名'。"
        new_tasks_text = llm.invoke(creation_prompt).content
        new_tasks = self._parse_tasks(new_tasks_text)
        print(f"[4/6] 创建 {len(new_tasks)} 个新任务")
        
        # 5. 重排任务优先级
        all_tasks = self.tasks + new_tasks
        priority_prompt = f"OUTPUT IN CHINESE. 按优先级从高到低排序这些任务: {[t['task_name'] for t in all_tasks]}。返回编号列表。"
        prioritized_text = llm.invoke(priority_prompt).content
        self.tasks = self._parse_tasks(prioritized_text, existing=all_tasks)
        print(f"[5/6] 优先级已重排, 当前队列: {[t['task_name'] for t in self.tasks]}")
        
        # 6. 保存任务列表
        print(f"[6/6] 当前任务列表: {self.tasks}")
        return result
    
    def _parse_tasks(self, text, existing=None):
        """解析 LLM 返回嘅任务列表"""
        tasks = []
        for line in text.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('#.')):
                # 去除编号
                task_name = line.lstrip('0123456789. #').strip()
                if task_name:
                    self.task_id_counter += 1
                    tasks.append({"task_id": self.task_id_counter, "task_name": task_name})
        return tasks
    
    def run(self, max_cycles=5):
        """主循环"""
        print(f"=== mavis BabyAGI 启动 ===")
        print(f"目标: {self.objective}")
        print(f"OUTPUT IN CHINESE")
        print()
        for i in range(max_cycles):
            print(f"=== Cycle {i+1} ===")
            result = self.cycle()
            if result is None:
                print("=== 任务列表为空, 终止 ===")
                break
            print()
        print(f"=== 完成 {len(self.completed_tasks)} 个任务 ===")

if __name__ == "__main__":
    # 测试: 用大佬嘅真实场景
    agent = MavisBabyAGI(
        objective="为大佬设计一个 mavis 2.0 plugin 自动安装 CLI 工具, 支持 Ollama/vLLM/GLM-4 三种 LLM 服务选择"
    )
    agent.run(max_cycles=3)
