"""CI helper: 验证 crewai_v7.py 嘅 8 机制 router import 存在"""
import ast
tree = ast.parse(open('crewai_v7.py').read())
found = False
for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        if node.module and 'router' in node.module:
            print(f"✅ 8 机制 router import 存在: {node.module}")
            found = True
            break
    elif isinstance(node, ast.Import):
        for n in node.names:
            if 'router' in n.name:
                print(f"✅ 8 机制 router import 存在: {n.name}")
                found = True
                break
if not found:
    print("❌ 8 机制 router import 缺失")
    import sys
    sys.exit(1)
