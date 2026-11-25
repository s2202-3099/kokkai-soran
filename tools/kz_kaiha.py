"""会派の記載がない貴族院議員の記事を取り直し、院内会派を読んで affiliations.csv に足す。

使い方: PYTHONPATH=tools python3 tools/kz_kaiha.py data <作業フォルダ>

build.py は貴族院の会派を run_kizokuin.py が作業フォルダに書いた kizokuin.json から入れる。この道具は、
作業フォルダがなくても、台帳（data/*.csv）だけから同じ決まりで会派を足すためのもの。
- 対象：各版の投票日（第1回は最初の帝国議会の開会日）に在職していて、会派の行がない貴族院議員。
- 本人の記事をいま取り直し（記事は作業フォルダの kz_kaiha_arts.json にためる）、kizokuin.kaiha_read で読む。
- 投票日にあった会派のうち、記事で先に読めたものを入れる（build.py と同じ）。根拠は art、出典は本人の記事。
- 情報欄で、その会派の後に「無所属」と書かれている人（「（研究会→）（無所属→）」）は、いつ離れたか分からないので入れない。
- 情報欄に会派が「（研究会→）木曜会」のように並んでいて、その日に両方の会派があったときは、どちらか決まらないので入れない。
- その日に貴族院議長だった人は入れない（議長は在任中は会派を離れるのが慣例）。
- すでにある行は変えない。
"""
import collections
import csv
import json
import os
import sys

import kizokuin
import wiki

D, W = sys.argv[1], sys.argv[2]
os.makedirs(W, exist_ok=True)


def rd(name):
    with open(os.path.join(D, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


persons = {r["person_id"]: r for r in rd("persons.csv")}
orgs = rd("orgs.csv")
oid = {r["name"]: r["org_id"] for r in orgs if r["kind"] == "院内会派" and r["lineage"] == "貴族院の会派"}
kaiha_ids = set(oid.values())
KZ_REF = {"1890-07-01": "1890-11-29"}   # build.py と同じ
days = [KZ_REF.get(r["date"], r["date"]) for r in rd("elections.csv") if r["house"] == "衆" and r["date"] < "1947-05-03"]
terms = [r for r in rd("terms.csv") if r["house"] == "貴"]
with open(os.path.join(D, "affiliations.csv"), encoding="utf-8") as f:
    rdr = csv.DictReader(f)
    cols = rdr.fieldnames
    affs = list(rdr)
have = {(r["person_id"], r["as_of"]) for r in affs if r["org_id"] in kaiha_ids}
speaker = {(r["person_id"], KZ_REF.get(r["as_of"], r["as_of"])) for r in rd("posts.csv") if r["kind"] == "貴族院の役職" and r["post"] == "議長"}


def in_office(t, day):
    s, e = t["start_date"], t["end_date"]
    return (s if len(s) >= 10 else s + "-99") <= day and e >= day[:len(e)]   # build.py と同じ


need = collections.defaultdict(set)   # 人 → 会派の行がない投票日
src = {}
for t in terms:
    for day in days:
        if in_office(t, day) and (t["person_id"], day) not in have and t["peer_type"] != "皇族議員":
            need[t["person_id"]].add(day)
            src[t["person_id"]] = t["source_id"]
print("会派の行がない在職（人）", len(need), "（人・投票日）", sum(len(v) for v in need.values()))

# 記事を取る（50件ずつ。転送先の記事名は元の記事名に戻す）
cache_path = os.path.join(W, "kz_kaiha_arts.json")
arts = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
todo = sorted({persons[p]["jawiki_title"] for p in need if persons[p]["jawiki_title"]} - set(arts))
for i in range(0, len(todo), 50):
    batch = todo[i:i + 50]
    r = wiki.call({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                   "titles": "|".join(batch), "redirects": "1"})
    back = {}
    for k in ("normalized", "redirects"):
        for x in r["query"].get(k, []):
            back[x["to"]] = back.get(x["from"], x["from"])
    for pg in r["query"]["pages"]:
        c = pg.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("content", "")
        arts[back.get(pg["title"], pg["title"])] = c
    print("記事", min(i + 50, len(todo)), "/", len(todo), flush=True)
    json.dump(arts, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)

added = collections.Counter()
by_place = collections.Counter()
skipped = collections.Counter()
new_rows = []
for p in sorted(need):
    text = arts.get(persons[p]["jawiki_title"], "")
    found = kizokuin.kaiha_read(text) if text else []
    if not found:
        continue
    names = [k for k, _ in found]
    for day in sorted(need[p]):
        if (p, day) in speaker:
            skipped["議長"] += 1
            continue
        alive = [(k, w) for k, w in found if kizokuin.kaiha_alive(k, day)]
        if not alive:
            continue
        k, where = alive[0]
        if where == "情報欄・後に無所属":
            skipped["後に無所属"] += 1
            continue
        if where.startswith("情報欄") and len([x for x in alive if x[1].startswith("情報欄")]) > 1:
            skipped["情報欄に移った先の会派もあり、その日の会派が決まらない"] += 1   # 「（研究会→）木曜会」の1898〜1912年
            continue
        others = [x for x in names if x != k]
        new_rows.append({"person_id": p, "org_id": oid[k], "start_date": "", "end_date": "", "as_of": day, "role": "",
                         "basis": "art", "source_id": src[p],
                         "note": ("投票日の会派；本人の記事に書かれた所属会派（所属の時期は確かめていない）" if where == "本文" else
                                  "投票日の会派；本人の記事の情報欄に書かれた所属会派（所属の時期は確かめていない）")
                         + (f"。記事にはほかに {'・'.join(others)}" if others else "")})
        added[day] += 1
        by_place[where] += 1

with open(os.path.join(D, "affiliations.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(affs + new_rows)
print("足した行", len(new_rows), "人", len({r["person_id"] for r in new_rows}), dict(by_place), "入れなかった", dict(skipped))
for day in days:
    if added[day]:
        print(" ", day, added[day])
