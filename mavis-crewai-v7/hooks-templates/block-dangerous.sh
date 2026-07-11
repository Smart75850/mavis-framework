#!/bin/bash
# block-dangerous.sh — Claude Code PreToolUse Hook
# 拦截危险 Bash 命令 (危险模式 / 受保护路径)
# 适用：第 5 章 §5.6.1 危险命令拦截
#
# 安装：
#   chmod +x block-dangerous.sh
#   cp block-dangerous.sh /path/to/project/.claude/hooks/
#   编辑 .claude/settings.json 加 matcher: "Bash" 引用此脚本 (见 security-guards.md)
#
# 测试：
#   echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | ./block-dangerous.sh
#   echo "exit=$?"  # 应该输出 exit=2 (阻止)
#
# 设计原则：
#   退出码 0 = 允许 (allow)
#   退出码 2 = 有意阻止 (deny, stderr 含错误原因)
#   其他退出码 = 脚本异常 (不阻止, 系统使用 stderr 当 debug 信息)
#   调试信息 → stderr (stdout 必须保留 JSON 决策结果)

set -e

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || true)

# Debug info (stderr, 不污染 stdout JSON)
echo "DEBUG: block-dangerous.sh 收到命令: $COMMAND" >&2

# 提取命令主干 (去前导空格)
COMMAND=$(echo "$COMMAND" | sed 's/^[[:space:]]*//')

# === 危险命令模式列表 (10 类) ===
# 覆盖第 5 章 §5.6.1 全部 + 大佬高频踩坑场景
DANGEROUS_PATTERNS=(
  # 1. 强制删除 (rm-rf 带根路径 / 系统路径)
  'rm\s+-[rf]{1,2}.*?\s+(/|/\*|/etc|/usr|/var|/boot|/home|/root|/System|/Library)(\s|$|;)'
  # 2. Git 强制推送 / 危险 reset
  'git\s+push\s+.*?--force'
  'git\s+push\s+-f\b'
  'git\s+reset\s+--hard\b'
  'git\s+clean\s+-[df]{1,3}.*?\s+\.\s*$'
  # 3. 数据库毁灭
  'DROP\s+DATABASE'
  'DROP\s+TABLE'
  'TRUNCATE\s+TABLE'
  # 4. Fork 炸弹
  ':\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:'
  # 5. 危险 chmod
  'chmod\s+-R\s+777\s+/'
  # 6. 危险管道执行 (远程脚本)
  'curl\b.*?\s*\|\s*(ba)?sh'
  'wget\b.*?\s*\|\s*(ba)?sh'
  # 7. mkfs / dd 危险
  'mkfs\b.*?(/dev/|/dev/sd|/dev/nvme)'
  'dd\b.*?of=/dev/(sd|nvme|hd)'
  # 8. 危险重定向写入系统文件
  '>\s*/etc/(passwd|shadow|hosts|fstab|sudoers)'
  '>\s*/boot/'
  # 9. Mac 特定 (系统级)
  'sudo\s+rm\s+-rf\s+/(?:\s|$|;)'
  'diskutil\s+(eraseDisk|partitionDisk)'
  # 10. 历史覆盖 (commit --amend on pushed)
  'git\s+commit\s+--amend\b.*?\b(already\s*pushed|after\s*push|origin/main|origin/master)'
)

# === 受保护路径前缀 (绝对路径) ===
PROTECTED_PATH_PREFIXES=(
  "/etc"
  "/usr"
  "/var"
  "/boot"
  "/System"
  "/Library"  # macOS 系统级
  "/private/etc"
)

# === 检查 1: 命令是否匹配危险模式 ===
for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -Eq "$pattern"; then
    echo "BLOCKED: 危险命令模式: $pattern" >&2
    # 允许 dry-run / safe-run 命令 (避免误拦)
    if echo "$COMMAND" | grep -qE '\b(--dry-run|-n\b|safe-)'; then
      echo "DEBUG: 检测到 dry-run 参数, 放行" >&2
      echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
      exit 0
    fi
    # 阻止 + 输出 JSON
    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "拦截危险命令模式: '$pattern'。如果这是必要的, 请先加入 dry-run 参数或拆分更精确的命令。"
  }
}
EOF
    exit 2
  fi
done

# === 检查 2: 受保护路径前缀 ===
for prefix in "${PROTECTED_PATH_PREFIXES[@]}"; do
  if echo "$COMMAND" | grep -Eq "(rm|dd|mv|cp|chmod|chown|tar|zip|rsync)\b.*?\b${prefix}"; then
    echo "BLOCKED: 受保护路径前缀: $prefix" >&2
    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "受保护的路径前缀: '$prefix' (系统级目录, 不允许 Claude 自动操作)。如需修改, 请手动执行。"
  }
}
EOF
    exit 2
  fi
done

# === 检查 3: 阻止 git commit 含敏感文件 (联合 protect-files.sh) ===
# 这一段由 protect-files.sh 独立负责, block-dangerous.sh 不重复

# === 全部检查通过 → allow ===
echo "DEBUG: 命令通过所有检查" >&2
echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
exit 0
