#!/bin/bash
# mavis verifier v2 集成脚本 - 真正替换 mavis verifier (2026-07-10)
# 永久 invariant #22: AutoGen 嵌套对话 = mavis verifier 反思

set -euo pipefail

VERIFIER_V2_DIR="$HOME/workspace/mavis-verifier-v2"
MAVIS_VERIFIER_DIR="$HOME/.mavis/agents/mavis"

# 创建 mavis verifier v2 wrapper
cat > "$MAVIS_VERIFIER_DIR/verifier-v2.sh" << 'WRAPPER_EOF'
#!/bin/bash
# mavis verifier v2 wrapper - 调用 AutoGPT-style 嵌套对话 (章 12 #22)
exec "$HOME/workspace/mavis-verifier-v2/verifier.py" "$@"
WRAPPER_EOF
chmod +x "$MAVIS_VERIFIER_DIR/verifier-v2.sh"

# 添加到 mavis PATH
if [[ ":$PATH:" != *":$MAVIS_VERIFIER_DIR:"* ]]; then
    echo "export PATH=\"$MAVIS_VERIFIER_DIR:\$PATH\"" >> ~/.zshrc
    echo "已添加 $MAVIS_VERIFIER_DIR 到 PATH"
fi

# 创建 alias
if ! grep -q "alias mavis-verify-v2" ~/.zshrc; then
    echo "alias mavis-verify-v2='python $VERIFIER_V2_DIR/verifier.py'" >> ~/.zshrc
    echo "已添加 alias mavis-verify-v2"
fi

echo ""
echo "=== mavis verifier v2 集成完成 ==="
echo "用法: mavis-verify-v2 '你的任务'"
echo "永久 invariant #22: AutoGen 嵌套对话 = mavis verifier 反思 ✅"
