"""
mavis verifier v2 - 借鉴 AutoGen 嵌套对话 (章 12 #22 invariant)
永久 invariant #22: AutoGen 嵌套对话 = mavis verifier 反思

参考章 12.3 嵌套对话工作流程:
- user_proxy (mavis root) -> programmer (生成代码) -> reviewer (审核) -> 反馈给 programmer
- max_turns=2 默认 (6 轮对话)
- register_nested_chats (trigger=programmer, recipient=reviewer)
"""
import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate  # langchain 1.0+ 路径

# Ollama 兼容名 (永久 invariant #12)
llm = ChatOpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="EMPTY",
    model="gpt-3.5-turbo",  # qwen3:32b 兼容名 (永久 invariant #12)
    temperature=0.3,  # 降低温度, verify 需要稳定
    timeout=300,  # 5 分钟 timeout (qwen3:32b 嵌套对话需要时间)
)

class MavisProgrammer:
    """借鉴 AutoGen 章 12 嘅 programmer 角色"""
    def __init__(self):
        self.system_message = """你是一个优秀的人工智能编程助手 (mavis-programmer)。
能够编写 Python 程序或编写 JSON 格式的文件。
OUTPUT IN CHINESE。"""
        self.last_output = None
    
    def generate(self, task: str) -> str:
        """借鉴章 12 嘅 programmer 写作"""
        prompt = f"{self.system_message}\n\n任务: {task}"
        response = llm.invoke(prompt).content
        self.last_output = response
        return response

class MavisReviewer:
    """借鉴 AutoGen 章 12 嘅 reviewer 角色"""
    def __init__(self):
        self.system_message = """你是一个软件审核人员 (mavis-reviewer)。
能够阅读 Python 代码和 JSON 结构的文件。
你的任务是发现代码的问题和检查 JSON 的结构是否合规。
OUTPUT IN CHINESE。"""
    
    def review(self, code: str) -> dict:
        """借鉴章 12 嘅 reviewer 审核"""
        prompt = f"{self.system_message}\n\n请审核以下内容:\n{code}\n\n返回 JSON: {{\"approved\": true/false, \"issues\": [...], \"suggestions\": [...]}}"
        response = llm.invoke(prompt).content
        try:
            # 提取 JSON
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except:
            pass
        return {"approved": False, "issues": ["JSON 解析失败"], "suggestions": [response]}

class MavisVerifierV2:
    """借鉴 AutoGen register_nested_chats 模式"""
    def __init__(self, max_turns: int = 2):
        self.programmer = MavisProgrammer()
        self.reviewer = MavisReviewer()
        self.max_turns = max_turns
        self.history = []
    
    def verify(self, task: str) -> dict:
        """借鉴章 12 嵌套对话 6 轮循环"""
        print(f"\n=== mavis verifier v2 启动 ===")
        print(f"OUTPUT IN CHINESE")
        print(f"任务: {task}")
        print()
        
        current_task = task
        for turn in range(1, self.max_turns + 1):
            print(f"--- Turn {turn} ---")
            
            # 1. Programmer 生成 (借鉴章 12 user_proxy to programmer)
            print(f"[programmer] 生成中...")
            code = self.programmer.generate(current_task)
            print(f"[programmer] 输出: {code[:150]}...")
            
            # 2. Reviewer 审核 (借鉴章 12 programmer to reviewer, 触发审核)
            print(f"[reviewer] 审核中...")
            review_result = self.reviewer.review(code)
            print(f"[reviewer] 结果: approved={review_result.get('approved')}")
            if review_result.get('issues'):
                for issue in review_result.get('issues', [])[:3]:
                    print(f"  - 问题: {issue}")
            
            # 3. 记录历史
            self.history.append({
                "turn": turn,
                "code": code[:500],
                "review": review_result
            })
            
            # 4. 决定是否终止
            if review_result.get('approved', False):
                print(f"[verifier] Turn {turn} 已 approved, 终止")
                break
            
            # 5. 反馈给 programmer (借鉴章 12 reviewer to user_proxy to programmer)
            # 处理 issues 字段 (可能系 str 或者 dict list)
            issues_list = review_result.get('issues', [])
            issues_str = []
            for issue in issues_list:
                if isinstance(issue, dict):
                    # 提取 description 或拼成 str
                    issues_str.append(issue.get('description', str(issue)))
                else:
                    issues_str.append(str(issue))
            issues = "; ".join(issues_str)
            current_task = f"{task}\n\n审核反馈 (请改进): {issues}"
            print(f"[verifier] 反馈给 programmer: {current_task[:100]}...")
            print()
        
        return {
            "approved": self.history[-1]['review'].get('approved', False),
            "history": self.history,
            "final_code": self.programmer.last_output
        }

if __name__ == "__main__":
    # 测试: 大佬嘅真实场景
    import sys
    max_turns = int(sys.argv[2]) if len(sys.argv) > 2 else 1  # 默认 1 turn (节省时间)
    verifier = MavisVerifierV2(max_turns=max_turns)
    task = sys.argv[1] if len(sys.argv) > 1 else "编写一个 Python 函数, 计算斐波那契数列第 n 项"
    result = verifier.verify(task=task)
    print(f"\n=== 最终结果 ===")
    print(f"approved: {result['approved']}")
    print(f"总轮次: {len(result['history'])}")
