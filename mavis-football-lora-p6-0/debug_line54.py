#!/usr/bin/env python3
"""Debug line 54 actual bytes"""
with open('langgraph_crewai_lora.py', 'rb') as f:
    raw = f.read()
lines = raw.split(b'\n')
line = lines[53]
print('Line 54 length:', len(line))
# Col 139 (1-indexed) = byte 138 (0-indexed)
# 5 chars around
print('Bytes 135-145:', line[135:145].hex())
print('Bytes 135-145 repr:', repr(line[135:145]))
print('Byte 138:', hex(line[138]))
print('Byte 139:', hex(line[139]))
