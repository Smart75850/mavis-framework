#!/usr/bin/env python3
"""Fix backslash-quote issue in langgraph_crewai_lora.py"""
import ast

with open('langgraph_crewai_lora.py', 'rb') as f:
    raw = f.read()

# 3 bytes: 2 backslashes + 1 quote
old = b'\x5c\x5c\x22'
# 2 bytes: 1 backslash + 1 quote
new = b'\x5c\x22'

count = raw.count(old)
print(f'Count of 3-byte seq (2 backslash + quote): {count}')

if count > 0:
    raw = raw.replace(old, new)
    with open('langgraph_crewai_lora.py', 'wb') as f:
        f.write(raw)
    print('Replaced!')

# Verify
with open('langgraph_crewai_lora.py', 'r') as f:
    content = f.read()
try:
    ast.parse(content)
    print('FILE OK')
except SyntaxError as e:
    print(f'Error at line {e.lineno}, col {e.offset}: {e.msg}')
