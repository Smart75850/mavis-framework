#!/usr/bin/env python3
"""Add extra backslash only when \\\\\" is followed by word char (heuristic)"""
import ast
import re

with open('langgraph_crewai_lora.py', 'rb') as f:
    raw = f.read()

# Pattern: 5c 22 followed by alphanumeric (e.g. \\\\\"Bayern)
# Replace 5c 22 with 5c 5c 22 (add one backslash)
# But skip if already preceded by 5c (i.e. already 5c 5c 22)

new_raw = bytearray()
i = 0
changed = 0
while i < len(raw):
    if i + 2 < len(raw) and raw[i] == 0x5c and raw[i+1] == 0x22:
        # Check if next byte is alphanumeric (likely an unescaped key)
        if i + 2 < len(raw) and (raw[i+2] in b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'):
            # Check if already preceded by backslash (5c 5c 22)
            if i > 0 and raw[i-1] == 0x5c:
                # Already has double backslash, skip
                new_raw.append(raw[i])
                new_raw.append(raw[i+1])
                i += 2
            else:
                # Add extra backslash
                new_raw.append(0x5c)  # extra \
                new_raw.append(raw[i])  # \
                new_raw.append(raw[i+1])  # "
                changed += 1
                i += 2
        else:
            new_raw.append(raw[i])
            new_raw.append(raw[i+1])
            i += 2
    else:
        new_raw.append(raw[i])
        i += 1

print(f'Changed {changed} occurrences')

with open('langgraph_crewai_lora.py', 'wb') as f:
    f.write(bytes(new_raw))

# Verify
with open('langgraph_crewai_lora.py', 'r') as f:
    content = f.read()
try:
    ast.parse(content)
    print('FILE OK')
except SyntaxError as e:
    print(f'Error at line {e.lineno}, col {e.offset}: {e.msg}')
