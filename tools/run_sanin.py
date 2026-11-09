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
out = {}
for n in range(10, 28):
    rows, notes = sanin.extract(d[f"第{n}回参議院議員通常選挙"]["text"], tokutei=TOK.get(n, ()))
    for r in rows:
        r["name"] = re.sub(r"\{\{color\|[^|{}]*\|([^{}]*)\}\}", r"\1", r["name"]).strip()
    out[n] = {"rows": rows, "notes": notes}
json.dump(winners._color_cache, open(cache, "w"), ensure_ascii=False)
json.dump(out, open(os.path.join(W, "sanin_winners.json"), "w"), ensure_ascii=False, indent=0)
for n, v in out.items():
    print(n, dict(collections.Counter(r["kind"] for r in v["rows"])))
