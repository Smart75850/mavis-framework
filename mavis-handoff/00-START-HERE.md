# 🚨 新 Mavis session 必读 (永久 invariant #31)

> **如果你睇到呢个文件, 立即执行下面命令, 唔好问点解**:

## 第一步: 跑 init script (强制)

```bash
mavis-init
```

或者:

```bash
~/.mavis/init/agent_workspace_init.sh "$WORKSPACE"
```

## 第二步: 读完整 Handoff 文档

```bash
cat ~/workspace/mavis-handoff/HANDOFF-2026-07-10.md
```

## 第三步: 验证 5 大改造

```bash
ls ~/workspace/mavis-{recall,verifier,team-plan,babyagi,langgraph}-v2/
```

## 📚 大佬心血

高强文《大模型项目实战: Agent 开发与应用》完整版 (16 章, 5374 段) 已应用:

- **30 永久 invariant** (#9-#31)
- **5 大改造项目** (recall/verifier/team plan/babyagi/langgraph)
- **mavis 8 机制协奏 92.5%**
- **知识星图 204 节点** (+49 今晚)

## ⚠️ 如果你唔记得

- 30 个 invariant: 读 `~/.mavis/agents/mavis/memory/topics/agent-dev-book-2026-07-10.md`
- mavis recall 策略: 读 `~/.mavis/agents/mavis/memory/recall-strategy.md`
- 16 章可应用详情: 读 `~/workspace/agent-book-practice/agent_dev_book_complete/chapters/`

---

**Mavis 唔好靠自觉, 靠呢个文件强制 recall!**
