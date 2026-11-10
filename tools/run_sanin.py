"""参院選の記事（src.json）から当選者を取り出して sanin_winners.json に書く。

使い方: PYTHONPATH=tools python3 tools/run_sanin.py <参院の作業フォルダ>
"""
import collections
import json
import os
import re
import sys

import sanin
import winners

W = sys.argv[1]
cache = os.path.join(W, "color_cache.json")
if os.path.exists(cache):
    winners._color_cache.update(json.load(open(cache)))
d = json.load(open(os.path.join(W, "src.json")))
# 特定枠の注記が名前参照（{{Efn2|name=tokutei}}）になっていて拾えない回
TOK = {25: ("舩後靖彦", "木村英子")}
# 凡例に載っていない党の色（第6回：共産党の野坂参三氏〈東京の補欠〉と全国区の参議院同志会）
FIX = {6: {"f66": "日本共産党", "89e": "参議院同志会"}}
out = {}
# 記事の表の書き損じ（第3回の大阪：行を分けるはずのところが「|」になっていて、亀田得治氏が読めない）
TEXT_FIX = {3: [("[[中山福蔵]]|cff:[[亀田得治]]", "[[中山福蔵]]\ncff:[[亀田得治]]")]}
for n in range(1, 28):
    text = d[f"第{n}回参議院議員通常選挙"]["text"]
    for a_, b_ in TEXT_FIX.get(n, []):
        assert a_ in text, a_
        text = text.replace(a_, b_)
    rows, notes = sanin.extract(text, tokutei=TOK.get(n, ()), fix=FIX.get(n))
    if n == 1:
        # 第1回は地方区の表の形が違う（上段が任期6年、下段が任期3年）。全国区は51位以下が任期3年
        import sanin1947
        rows = sanin1947.chiho(text) + [dict(r, short=r.get("order", 0) > 50) for r in rows if r["kind"] == "全国区"]
        # 繰上当選の表：16位の膳桂之助氏の当選辞退で、101位の国井淳一氏が繰上（任期3年）
        rows.append({"kind": "全国区", "party": "無所属", "article": "国井淳一", "name": "国井淳一", "short": True,
                     "tokutei": False, "note": "", "order": 101, "party_note": ""})
    for r in rows:
        r["name"] = re.sub(r"\{\{color\|[^|{}]*\|([^{}]*)\}\}", r"\1", r["name"]).strip()
    out[n] = {"rows": rows, "notes": notes}
json.dump(winners._color_cache, open(cache, "w"), ensure_ascii=False)
json.dump(out, open(os.path.join(W, "sanin_winners.json"), "w"), ensure_ascii=False, indent=0)
for n, v in out.items():
    print(n, dict(collections.Counter(r["kind"] for r in v["rows"])))
