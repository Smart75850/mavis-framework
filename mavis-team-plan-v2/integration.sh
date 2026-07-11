#!/bin/bash
# mavis team plan v2 集成脚本 - 真正集成到 mavis 体系 (2026-07-10)
# 永久 invariant #21: LangGraph StateGraph = mavis team plan DAG

set -euo pipefail

TEAM_PLAN_V2_DIR="$HOME/workspace/mavis-team-plan-v2"
MAVIS_BIN_DIR="$HOME/.mavis/bin"
MAVIS_TEAM_PLAN_V2="$MAVIS_BIN_DIR/mavis-team-v2"

# 创建 mavis team plan v2 binary (跟住 mavis CLI 命名规范)
cat > "$MAVIS_TEAM_PLAN_V2" << 'BINARY_EOF'
#!/bin/bash
# mavis team plan v2 - 借鉴 LangGraph StateGraph (永久 invariant #21)
# 替代 mavis team plan (静态 DAG -> 条件边 + MemorySaver)
exec "$HOME/workspace/mavis-team-plan-v2/team-plan-v2.sh" "$@"
BINARY_EOF
chmod +x "$MAVIS_TEAM_PLAN_V2"

# 添加 alias 到 .zshrc (唔覆盖 mavis-team, 用 v2 后缀区分)
if ! grep -q "alias mavis-team-v2" ~/.zshrc; then
    echo "" >> ~/.zshrc
    echo "# mavis team plan v2 (借鉴 LangGraph, 2026-07-10)" >> ~/.zshrc
    echo "alias mavis-team-v2='$MAVIS_TEAM_PLAN_V2'" >> ~/.zshrc
    echo "已添加 alias mavis-team-v2"
fi

# 添加到 mavis cron (每日 rebuild 索引, 借鉴 #30)
CRON_LINE="0 3 * * * /Users/apple/.mavis/bin/mavis-recall-v2-rebuild 2>/dev/null || true"
if ! crontab -l 2>/dev/null | grep -q "mavis-recall-v2-rebuild"; then
    (crontab -l 2>/dev/null; echo "# mavis recall v2 每日 rebuild 索引 (永久 invariant #30, 2026-07-10)"; echo "$CRON_LINE") | crontab -
    echo "已添加 mavis recall v2 rebuild cron (每日 03:00)"
fi

echo ""
echo "=== mavis team plan v2 集成完成 ==="
echo "用法: mavis-team-v2 '你的目标' [max_turns]"
echo "对比 mavis-team: 静态 DAG -> 条件边 + MemorySaver + state 持久化"
echo "永久 invariant #21: LangGraph StateGraph = mavis team plan DAG ✅"
