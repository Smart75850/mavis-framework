#!/usr/bin/env python3
"""Add extra backslash to fix escaping in langgraph_crewai_lora.py"""
import ast

with open('langgraph_crewai_lora.py', 'rb') as f:
    raw = f.read()

# We have 5c 5c 22 (3 bytes: \ \ ")
# Want 5c 5c 5c 22 (4 bytes: \ \ \ ")
# Replace each occurrence

# Build new content
new_parts = []
i = 0
while i < len(raw):
    if i + 2 < len(raw) and raw[i] == 0x5c and raw[i+1] == 0x5c and raw[i+2] == 0x22:
        # Found 5c 5c 22, replace with 5c 5c 5c 22
        new_parts.append(b'\x5c\x5c\x5c\x22')
        i += 3
    else:
        new_parts.append(bytes([raw[i]]))
        i += 1

new_raw = b''.join(new_parts)

count_changed = sum(1 for i in range(len(raw)) if i + 2 < len(raw) and raw[i] == 0x5c and raw[i+1] == 0x5c and raw[i+2] == 0x22)
print(f'Changed {count_changed} occurrences')

with open('langgraph_crewai_lora.py', 'wb') as f:
    f.write(new_raw)

# Verify
with open('langgraph_crewai_lora.py', 'r') as f:
    content = f.read()
try:
    ast.parse(content)
    print('FILE OK')
except SyntaxError as e:
    print(f'Error at line {e.lineno}, col {e.offset}: {e.msg}')
