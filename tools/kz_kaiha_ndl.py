"""会派の記載がない貴族院議員の院内会派を、帝国議会会議録検索システムの発言者情報から引いて affiliations.csv に足す。

使い方: PYTHONPATH=tools python3 tools/kz_kaiha_ndl.py data <作業フォルダ>

- 対象：各版の投票日（第1回は1890年11月29日）に在職していて、会派の行が一つもない貴族院議員（皇族議員を除く）。
  本人の記事から会派が読めた人（kz_kaiha.py）は、記事の会派を使い、ここでは足さない。
- 帝国議会会議録検索システムの発言単位出力 API（https://teikokugikai-i.ndl.go.jp/api/emp/speech）で、
  貴族院での本人の発言を名前で引き（最大100件）、発言者情報の「所属会派」（speakerGroup）を読む。
  利用の条件（使い方ガイドの「APIを利用する」「利用条件・免責事項」）に従い、多重リクエストはせず、
  取り終えてから4秒あけて次を送る。結果は作業フォルダの kz_kaiha_ndl.json にため、続きから取れる。
- 発言者情報の所属会派は、発言の日の所属ではなく、人ごとに一つの値（近衛文麿氏は火曜会の結成〈1927年〉より前の
  発言でも「火曜会」）。台帳では本人の記事の会派と同じく「所属の時期は確かめていない」として扱い、
  投票日にあった会派だけを入れる（kizokuin.KAIHA_SPANS）。
- 台帳に同じ名前の人が二人以上いるとき（吉田茂氏は内務官僚と首相の二人が貴族院議員）は、発言者情報の在任期間
  （officeTerm「大正5年10月1日～昭和20年12月16日」）がその人の在職と重なる発言だけを使い、二人の在職が重なれば使わない。
  よみが二つ以上ある（別人が混じっている）ときも使わない。
- 所属会派の値が二つ以上あるとき（入力の揺れ）は、いちばん多いものが8割以上なら採る。
- 「各派に属しない議員」「無所属」と書かれた人は、会派の行を作らない（一覧に出すだけ）。
- その日に貴族院議長だった人は入れない。根拠は doc、出典は帝国議会会議録検索システム。すでにある行は変えない。
"""
import collections
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import kizokuin

D, W = sys.argv[1], sys.argv[2]
os.makedirs(W, exist_ok=True)
API = "https://teikokugikai-i.ndl.go.jp/api/emp/speech"
UA = "kokkai-soran/0.1 (https://github.com/s2202-3099/kokkai-soran)"
ERA = {"明治": 1867, "大正": 1911, "昭和": 1925}
SRC_URL = "https://teikokugikai-i.ndl.go.jp/"


def rd(name):
    with open(os.path.join(D, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get(params):
    url = API + "?" + urllib.parse.urlencode({**params, "recordPacking": "json"})
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            data = json.load(urllib.request.urlopen(req, timeout=120))
            time.sleep(4)
            return data
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(30 * (attempt + 1))
    raise RuntimeError("帝国議会会議録検索システムから取れなかった: " + url)


persons = {r["person_id"]: r for r in rd("persons.csv")}
same_name_ids = collections.defaultdict(list)
for r in persons.values():
    same_name_ids[r["name"]].append(r["person_id"])
same_name = {k: len(v) for k, v in same_name_ids.items()}


def wdate(s):
    """「大正6年12月1日」→ 1917-12-01（月・日がなければ年の初め）。"""
    m = re.match(r"(明治|大正|昭和)(\d+|元)年(?:(\d+)月)?(?:(\d+)日)?", s.strip())
    if not m:
        return None
    y = ERA[m.group(1)] + (1 if m.group(2) == "元" else int(m.group(2)))
    return f"{y}-{int(m.group(3) or 1):02d}-{int(m.group(4) or 1):02d}"


def term_span(s):
    a, _, b = (s or "").partition("～")
    return wdate(a) or "0000", wdate(b) or "9999"


def overlap(x, y):
    return x[0] <= y[1] and y[0] <= x[1]
orgs = rd("orgs.csv")
oid = {r["name"]: r["org_id"] for r in orgs if r["lineage"] == "貴族院の会派"}
KZ_REF = {"1890-07-01": "1890-11-29"}   # build.py と同じ
days = [KZ_REF.get(r["date"], r["date"]) for r in rd("elections.csv") if r["house"] == "衆" and r["date"] < "1947-05-03"]
terms = [r for r in rd("terms.csv") if r["house"] == "貴"]
with open(os.path.join(D, "affiliations.csv"), encoding="utf-8") as f:
    rdr = csv.DictReader(f)
    cols = rdr.fieldnames
    affs = list(rdr)
has_kaiha = {r["person_id"] for r in affs if r["org_id"] in set(oid.values())}
speaker = {(r["person_id"], KZ_REF.get(r["as_of"], r["as_of"])) for r in rd("posts.csv")
           if r["kind"] == "貴族院の役職" and r["post"] == "議長"}


def in_office(t, day):
    s, e = t["start_date"], t["end_date"]
    return (s if len(s) >= 10 else s + "-99") <= day and e >= day[:len(e)]


need = collections.defaultdict(set)
spans = collections.defaultdict(list)
for t in terms:
    p = t["person_id"]
    if t["peer_type"] == "皇族議員" or p in has_kaiha:
        continue
    for day in days:
        if in_office(t, day):
            need[p].add(day)
for t in terms:
    spans[t["person_id"]].append((t["start_date"] or "0000", t["end_date"] or "9999"))
need = {p: v for p, v in need.items() if v}
print("会派の行が一つもない在職者", len(need), flush=True)

cache_path = os.path.join(W, "kz_kaiha_ndl.json")
cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
for i, p in enumerate(sorted(need)):
    name = persons[p]["name"]
    if name in cache:
        continue
    d = get({"speaker": name, "nameOfHouse": "貴族院", "maximumRecords": "100"})
    cache[name] = {"n": d.get("numberOfRecords", 0),
                   "recs": [[r["speaker"], r.get("speakerYomi"), r.get("speakerGroup"), r.get("speakerElection"), r.get("officeTerm"), r["date"]]
                            for r in d.get("speechRecord", []) if r["speaker"] != "会議録情報"]}
    if i % 20 == 0:
        print("発言者", i + 1, "/", len(need), flush=True)
        json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)

# 発言者情報から会派を決める
result = collections.Counter()
listed = collections.defaultdict(list)
choice = {}
for p in sorted(need):
    name = persons[p]["name"]
    recs = cache.get(name, {}).get("recs", [])
    if not recs:
        result["発言が見つからない"] += 1
        continue
    if same_name[name] > 1:
        # 台帳に同じ名前の人が二人以上いる：発言者情報の在任期間が、この人の在職と重なる発言だけを使う
        ok = [r for r in recs if r[4] and any(overlap(term_span(r[4]), sp) for sp in spans[p])]
        others = [q for q in same_name_ids[name] if q != p]
        if any(r[4] and any(overlap(term_span(r[4]), sp) for q in others for sp in spans.get(q, [])) for r in ok):
            ok = []   # 二人の在職が重なっていて分けられない
    else:
        ok = recs
    # よみが二つ以上あれば別人が混じっている（よみの入っていない発言は数えない）
    if not ok or len({r[1] for r in ok if r[1]}) > 1:
        result["同じ名前の発言者が分けられない"] += 1
        listed["分けられない"].append(name)
        continue
    groups = collections.Counter(r[2] for r in ok if r[2])
    if not groups:
        result["所属会派の記載なし"] += 1
        continue
    g, c = groups.most_common(1)[0]
    if c < 0.8 * sum(groups.values()):
        result["所属会派が揺れている"] += 1
        listed["揺れ"].append((name, dict(groups)))
        continue
    if g not in oid:
        result["会派でない値（" + g + "）"] += 1
        listed["会派でない値"].append((name, g))
        continue
    choice[p] = g
    result["会派が分かった"] += 1

new_rows = []
skipped = collections.Counter()
for p, g in sorted(choice.items()):
    for day in sorted(need[p]):
        if (p, day) in speaker:
            skipped["議長"] += 1
            continue
        if not kizokuin.kaiha_alive(g, day):
            skipped["その日に会派がない"] += 1
            continue
        new_rows.append({"person_id": p, "org_id": oid[g], "start_date": "", "end_date": "", "as_of": day, "role": "",
                         "basis": "doc", "source_id": "",
                         "note": "投票日の会派；帝国議会会議録検索システムの発言者情報の所属会派（人ごとに一つの値で、所属の時期は確かめていない）"})

# 出典（帝国議会会議録検索システム）を sources.csv に足す
with open(os.path.join(D, "sources.csv"), encoding="utf-8") as f:
    srdr = csv.DictReader(f)
    scols = srdr.fieldnames
    sources = list(srdr)
src = next((r for r in sources if r.get("url") == SRC_URL), None)
if not src:
    n = max(int(r["source_id"][1:]) for r in sources) + 1
    src = {c: "" for c in scols}
    src.update({"source_id": f"S{n:06d}", "url": SRC_URL})
    src.update({"title": "帝国議会会議録検索システム（発言者の所属会派）", "kind": "公的記録",
                "accessed": time.strftime("%Y-%m-%d")})
    sources.append(src)
    with open(os.path.join(D, "sources.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=scols)
        w.writeheader()
        w.writerows(sources)
for r in new_rows:
    r["source_id"] = src["source_id"]

with open(os.path.join(D, "affiliations.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(affs + new_rows)
json.dump({"result": result, "listed": listed, "choice": {persons[p]["name"]: g for p, g in choice.items()}},
          open(os.path.join(W, "kz_kaiha_ndl_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(dict(result))
print("足した行", len(new_rows), "人", len({r["person_id"] for r in new_rows}), "入れなかった", dict(skipped))
print("会派別", dict(collections.Counter(choice.values())))
