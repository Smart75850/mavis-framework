#!/usr/bin/env python3
"""
P8.1.1 扩充 70 → 200+ 条足球 alpaca (永久 invariant #98 准备)
实战: 复用 P6.1 (#87) 模式, 130 条 M3 自动生成
- 重点: 覆盖 P7 揭露嘅 0 命中率 query 类型 (C 朗 / 凯恩 / 五大联赛细节)
- 实战时间: 5-10 分钟
"""
import sys
import os
import json
import time
import re
from pathlib import Path
from datetime import datetime

for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'ALL_PROXY']:
    os.environ[k] = ''

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE.parent / "mavis-crewai-v7"))
from mavis_m3_provider import call_llm_m3


# 130 个新 prompts (重点覆盖 P7 0 命中率类型)
P8_PROMPTS = [
    # 沙特联赛 / Al Nassr (P7 Q5 0 命中率)
    "请写 1 条足球 alpaca 数据, 关于 C 罗在 Al Nassr 2024 年嘅入球数",
    "请写 1 条足球 alpaca 数据, 关于沙特联赛 2024 年嘅冠军争夺",
    "请写 1 条足球 alpaca 数据, 关于 C 罗喺 Al Nassr 嘅助攻数据",
    "请写 1 条足球 alpaca 数据, 关于 Al Nassr 嘅教练战术",
    "请写 1 条足球 alpaca 数据, 关于沙特联赛嘅外援政策",
    # 凯恩拜仁 (P7 Q3 0 命中率)
    "请写 1 条足球 alpaca 数据, 关于凯恩 2024-25 喺拜仁嘅场均入球",
    "请写 1 条足球 alpaca 数据, 关于凯恩喺拜仁嘅欧冠表现",
    "请写 1 条足球 alpaca 数据, 关于凯恩喺拜仁嘅助攻数据",
    "请写 1 条足球 alpaca 数据, 关于凯恩喺拜仁嘅 xG 数据",
    "请写 1 条足球 alpaca 数据, 关于凯恩加盟拜仁嘅转会费",
    # 5 大联赛争冠 (P7 Q4 0 命中率)
    "请写 1 条足球 alpaca 数据, 关于 2024-25 英超争冠冠亚军分差",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 西甲争冠冠亚军分差",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 德甲争冠冠亚军分差",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 意甲争冠冠亚军分差",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 法甲争冠冠亚军分差",
    # 英超射手榜 (P7 Q2 0 命中率)
    "请写 1 条足球 alpaca 数据, 关于 2024-25 英超金靴竞争",
    "请写 1 条足球 alpaca 数据, 关于 Haaland 喺曼城嘅场均 xG",
    "请写 1 条足球 alpaca 数据, 关于 Salah 喺利物浦嘅场均入球",
    "请写 1 条足球 alpaca 数据, 关于 Saka 喺阿森纳嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Palmer 喺车路士嘅入球数据",
    # 曼联利物浦 (P7 Q1 1/3 命中率)
    "请写 1 条足球 alpaca 数据, 关于曼联同利物浦 2024-25 季对战",
    "请写 1 条足球 alpaca 数据, 关于利物浦 2018-2024 对曼联战绩",
    "请写 1 条足球 alpaca 数据, 关于曼联喺英超 2024-25 排名",
    "请写 1 条足球 alpaca 数据, 关于利物浦 2024-25 欧冠表现",
    "请写 1 条足球 alpaca 数据, 关于曼联主帅战术变化",
    # 球员数据
    "请写 1 条足球 alpaca 数据, 关于 Mbappe 喺皇马嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Bellingham 喺皇马嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Vinicius 喺皇马嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Rodri 喺曼城嘅防守数据",
    "请写 1 条足球 alpaca 数据, 关于 De Bruyne 喺曼城嘅助攻数据",
    "请写 1 条足球 alpaca 数据, 关于 Wirtz 喺勒沃库森嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Musiala 喺拜仁嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Yamal 喺巴萨嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Lewandowski 喺巴萨嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Pedri 喺巴萨嘅助攻数据",
    "请写 1 条足球 alpaca 数据, 关于 Barella 喺国米嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Thuram 喺国米嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Vlahovic 喺尤文嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Kvara 喺巴黎嘅入球数据",
    "请写 1 条足球 alpaca 数据, 关于 Dembele 喺巴黎嘅入球数据",
    # 球队战术
    "请写 1 条足球 alpaca 数据, 关于曼城 4-3-3 阵型细节",
    "请写 1 条足球 alpaca 数据, 关于皇马 4-3-3 阵型",
    "请写 1 条足球 alpaca 数据, 关于阿森纳 4-3-3 阵型",
    "请写 1 条足球 alpaca 数据, 关于利物浦 4-3-3 阵型",
    "请写 1 条足球 alpaca 数据, 关于拜仁 4-2-3-1 阵型",
    "请写 1 条足球 alpaca 数据, 关于国米 3-5-2 阵型",
    "请写 1 条足球 alpaca 数据, 关于巴萨 4-3-3 阵型",
    "请写 1 条足球 alpaca 数据, 关于马竞 5-3-2 阵型",
    "请写 1 条足球 alpaca 数据, 关于尤文 3-5-2 阵型",
    "请写 1 条足球 alpaca 数据, 关于巴黎 4-3-3 阵型",
    # 比赛 + 经典
    "请写 1 条足球 alpaca 数据, 关于 2024 欧冠决赛细节",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 欧冠 8 强",
    "请写 1 条足球 alpaca 数据, 关于欧冠 2024-25 射手榜",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 欧霸杯决赛",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 世冠杯",
    "请写 1 条足球 alpaca 数据, 关于 2024 欧洲杯最佳球员",
    "请写 1 条足球 alpaca 数据, 关于 2024 欧洲杯金靴",
    "请写 1 条足球 alpaca 数据, 关于 2024 美洲杯冠军",
    "请写 1 条足球 alpaca 数据, 关于 2024 奥运男足冠军",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 国家德比细节",
    # 转会
    "请写 1 条足球 alpaca 数据, 关于 2024 夏窗标王",
    "请写 1 条足球 alpaca 数据, 关于 2025 冬窗标王",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员身价榜",
    "请写 1 条足球 alpaca 数据, 关于姆巴佩转会皇马细节",
    "请写 1 条足球 alpaca 数据, 关于凯恩转会拜仁细节",
    "请写 1 条足球 alpaca 数据, 关于 Bellingham 加盟皇马",
    "请写 1 条足球 alpaca 数据, 关于 Rice 加盟阿森纳",
    "请写 1 条足球 alpaca 数据, 关于 Haaland 喺曼城嘅合同",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员续约动态",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员自由身动态",
    # 数据 + xG
    "请写 1 条足球 alpaca 数据, 关于 xG 概念解释",
    "请写 1 条足球 alpaca 数据, 关于 xA (预期助攻) 概念",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员 xG 排行",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员 xA 排行",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球队 xG 排行",
    "请写 1 条足球 alpaca 数据, 关于点球 xG 概念",
    "请写 1 条足球 alpaca 数据, 关于定位球 xG 占比",
    "请写 1 条足球 alpaca 数据, 关于反击 xG 占比",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员跑动距离排行",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员冲刺速度排行",
    # 教练
    "请写 1 条足球 alpaca 数据, 关于 Guardiola 2024-25 战术调整",
    "请写 1 条足球 alpaca 数据, 关于 Ancelotti 2024-25 战术",
    "请写 1 条足球 alpaca 数据, 关于 Arteta 2024-25 战术",
    "请写 1 条足球 alpaca 数据, 关于 Klopp 离队后利物浦主帅",
    "请写 1 条足球 alpaca 数据, 关于 Slot 利物浦新主帅战术",
    "请写 1 条足球 alpaca 数据, 关于 Alonso 勒沃库森主帅战术",
    "请写 1 条足球 alpaca 数据, 关于 Inzaghi 国米主帅战术",
    "请写 1 条足球 alpaca 数据, 关于 Simeone 马竞主帅战术",
    "请写 1 条足球 alpaca 数据, 关于 Luis Enrique 巴黎主帅战术",
    "请写 1 条足球 alpaca 数据, 关于 Flick 巴萨主帅战术",
    # 球队对比
    "请写 1 条足球 alpaca 数据, 关于曼城同阿森纳 2024-25 对战",
    "请写 1 条足球 alpaca 数据, 关于皇马同巴萨 2024-25 战绩",
    "请写 1 条足球 alpaca 数据, 关于拜仁同多特 2024-25 战绩",
    "请写 1 条足球 alpaca 数据, 关于国米同尤文 2024-25 战绩",
    "请写 1 条足球 alpaca 数据, 关于巴黎同马赛 2024-25 战绩",
    # 青训
    "请写 1 条足球 alpaca 数据, 关于 La Masia 巴萨青训",
    "请写 1 条足球 alpaca 数据, 关于皇马青训新星",
    "请写 1 条足球 alpaca 数据, 关于曼城青训新星",
    "请写 1 条足球 alpaca 数据, 关于拜仁青训新星",
    "请写 1 条足球 alpaca 数据, 关于多特蒙德青训传统",
    # 门将
    "请写 1 条足球 alpaca 数据, 关于 Donnarumma 喺曼城嘅扑救",
    "请写 1 条足球 alpaca 数据, 关于 Oblak 喺马竞嘅扑救",
    "请写 1 条足球 alpaca 数据, 关于 Neuer 喺拜仁嘅扑救",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 五大联赛门将排行",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 门将零封场次",
    # 角球 + 定位球
    "请写 1 条足球 alpaca 数据, 关于 2024-25 角球进球排行",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 任意球进球排行",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 点球进球排行",
    "请写 1 条足球 alpaca 数据, 关于某球队定位球战术细节",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球队角球数排行",
    # 文化 + 球迷
    "请写 1 条足球 alpaca 数据, 关于英超球迷文化",
    "请写 1 条足球 alpaca 数据, 关于西甲球迷文化",
    "请写 1 条足球 alpaca 数据, 关于德甲球迷文化",
    "请写 1 条足球 alpaca 数据, 关于意甲球迷文化",
    "请写 1 条足球 alpaca 数据, 关于法甲球迷文化",
    # 数据源
    "请写 1 条足球 alpaca 数据, 关于 Opta 足球数据源",
    "请写 1 条足球 alpaca 数据, 关于 StatsBomb 足球数据",
    "请写 1 条足球 alpaca 数据, 关于 FBref 足球数据",
    "请写 1 条足球 alpaca 数据, 关于 Sofascore 足球数据",
    "请写 1 条足球 alpaca 数据, 关于 WhoScored 足球数据",
    # 财务 + 商业
    "请写 1 条足球 alpaca 数据, 关于 2024 欧洲俱乐部营收",
    "请写 1 条足球 alpaca 数据, 关于 2024 转播费排行",
    "请写 1 条足球 alpaca 数据, 关于 2024 球衣赞助排行",
    "请写 1 条足球 alpaca 数据, 关于 2024 球员薪资排行",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球衣销售排行",
    # 伤病 + 复出
    "请写 1 条足球 alpaca 数据, 关于 2024-25 ACL 受伤统计",
    "请写 1 条足球 alpaca 数据, 关于某关键球员伤停对球队影响",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 复出球员表现",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员黄红牌统计",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 球员停赛影响",
    # 国际赛事
    "请写 1 条足球 alpaca 数据, 关于 2026 世界杯预选赛",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 欧冠抽签",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 欧冠奖金分配",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 欧霸奖金分配",
    "请写 1 条足球 alpaca 数据, 关于 2024-25 欧冠改制影响",
    # 战术细节
    "请写 1 条足球 alpaca 数据, 关于压迫式防守战术",
    "请写 1 条足球 alpaca 数据, 关于低位防守战术",
    "请写 1 条足球 alpaca 数据, 关于控球战术 vs 反击战术",
    "请写 1 条足球 alpaca 数据, 关于边路传中战术",
    "请写 1 条足球 alpaca 数据, 关于肋部渗透战术",
    # 数据 + 战术混合
    "请写 1 条足球 alpaca 数据, 关于高位压迫 2024-25 数据",
    "请写 1 条足球 alpaca 数据, 关于低位防守 2024-25 数据",
    "请写 1 条足球 alpaca 数据, 关于控球率 2024-25 数据",
    "请写 1 条足球 alpaca 数据, 关于反击进球 2024-25 数据",
    "请写 1 条足球 alpaca 数据, 关于定位球进球 2024-25 数据",
]


def m3_generate(prompt: str) -> dict:
    """M3 生成 1 条 alpaca (永久 invariant #51 + #87)"""
    system = (
        "你是一个足球数据专家。\n"
        "用 alpaca 格式生成 1 条足球数据, 包含 instruction + input + output 3 字段。\n"
        "instruction 50 字内, input 30 字内, output 80-150 字, 必须有具体数字。\n"
        "**只返 JSON**, 唔好返其他内容。格式: {\"instruction\": \"...\", \"input\": \"...\", \"output\": \"...\"}"
    )
    raw = call_llm_m3(system=system, user=prompt, max_tokens=200, temperature=0.5, use_fallback=True)
    m = re.search(r"\{[\s\S]*?\"output\"[\s\S]*?\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


def main():
    print("=" * 70)
    print("P8.1.1 扩充 100 → 200+ 条足球 alpaca (永久 invariant #98 准备)")
    print("=" * 70)
    print()

    # 读现有 99 条
    existing_path = BASE / "football_alpaca_100plus_train.jsonl"
    existing_data = []
    if existing_path.exists():
        with open(existing_path) as f:
            for line in f:
                existing_data.append(json.loads(line))
        print(f"现有 train: {len(existing_data)} 条")

    dev_path = BASE / "football_alpaca_100plus_dev.jsonl"
    if dev_path.exists():
        with open(dev_path) as f:
            for line in f:
                existing_data.append(json.loads(line))
        print(f"现有 dev: 总 {len(existing_data)} 条")

    # 130 个 prompts
    print(f"目标生成: {len(P8_PROMPTS)} 条 (覆盖 P7 0 命中率 query 类型)")
    print()

    new_data = []
    start = time.time()
    failed = 0
    for i, prompt in enumerate(P8_PROMPTS, 1):
        result = m3_generate(prompt)
        if result and result.get("instruction") and result.get("output"):
            new_data.append(result)
            if i % 20 == 0:
                elapsed = time.time() - start
                print(f"  [{i}/{len(P8_PROMPTS)}] {len(new_data)} 成功, 失败 {failed}, 耗时 {elapsed:.0f}s")
        else:
            failed += 1
            if i % 30 == 0:
                print(f"  [{i}/{len(P8_PROMPTS)}] {len(new_data)} 成功, 失败 {failed}")

    elapsed = time.time() - start
    print()
    print(f"M3 生成完成: {len(new_data)} 成功, {failed} 失败, 耗时 {elapsed:.0f}s")
    print()

    # 合并: 99 (existing) + 130 (new) = 229, split 70/30
    all_data = existing_data + new_data
    total = len(all_data)
    print(f"总数据: {total} 条")

    import random
    random.seed(42)
    random.shuffle(all_data)
    split = int(total * 0.7)
    train_data = all_data[:split]
    dev_data = all_data[split:]
    print(f"Train: {len(train_data)}, Dev: {len(dev_data)}")

    # 写 200+ 文件
    train_path_200 = BASE / "football_alpaca_200plus_train.jsonl"
    dev_path_200 = BASE / "football_alpaca_200plus_dev.jsonl"

    with open(train_path_200, "w", encoding="utf-8") as f:
        for ex in train_data:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    with open(dev_path_200, "w", encoding="utf-8") as f:
        for ex in dev_data:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print()
    print(f"训练: {train_path_200} ({len(train_data)} 条)")
    print(f"验证: {dev_path_200} ({len(dev_data)} 条)")

    # 写报告
    report = {
        "test_at": datetime.now().isoformat(),
        "test_name": "P8.1.1 扩充 99 → 200+ 条足球 alpaca",
        "existing_count": len(existing_data),
        "new_generated": len(new_data),
        "new_failed": failed,
        "total": total,
        "train_count": len(train_data),
        "dev_count": len(dev_data),
        "elapsed_s": round(elapsed, 1),
        "train_path": str(train_path_200),
        "dev_path": str(dev_path_200),
    }
    report_path = BASE / "expand_200_results.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report_path}")


if __name__ == "__main__":
    main()
