"""data/*.csv から、サイトが読む site.json を作る。

使い方: python3 tools/build_site.py <data フォルダ> <出力する site.json>
サイトの表示はすべてこのファイルから作る（版・人物のページは index.html の中で組み立てる）。
"""
import csv
import json
import os
import re
import sys

D, OUT = sys.argv[1], sys.argv[2]


def rows(name):
    return list(csv.DictReader(open(os.path.join(D, name), encoding="utf-8")))


elections = [[e["election_id"], e["house"], int(e["number"]), e["date"], e["kind"], int(e["seats"]), e["source_id"]]
             for e in rows("elections.csv")]
orgs = {o["org_id"]: [o["name"], o["lineage"], o["predecessors"], o["successors"], o["kind"]] for o in rows("orgs.csv")}
districts = {d["district_id"]: d["name"] for d in rows("districts.csv")}
persons = [[p["person_id"], p["name"], p["name_kana"], p["birth_date"], p["death_date"], p["sex"], p["birth_pref"],
            p["jawiki_title"], p["wikidata_qid"], p.get("first_elected", ""), p.get("first_house", ""),
            p.get("prev_job", ""), p.get("kin_checked", "")] for p in rows("persons.csv")]
terms = [[t["term_id"], t["person_id"], t["house"], t["election_id"], t["district_id"], t["route"], t["start_date"],
          t["end_date"], t["end_reason"], t["basis"], t["source_id"], t.get("note", "")] for t in rows("terms.csv")]
affs = [[a["person_id"], a["org_id"], a["start_date"], a["end_date"], a["basis"], a["source_id"], a["note"], a.get("as_of", "")]
        for a in rows("affiliations.csv")]
# 第6回（1898年8月）の憲政党は、当選者表で旧自由党系・旧進歩党系に塗り分けられている（台帳の所属は「憲政党」で、系統は注記）。
# サイトでは議場図・党派の内訳・名簿で二つに分けて見せるため、表示用の党を二つ作って、その回の当選時の所属だけ付け替える
for a in affs:
    m = re.search(r"当選者表では憲政党の(旧自由党系|旧進歩党系)", a[6])
    if m:
        sub = f"{a[1]}-{'j' if m.group(1) == '旧自由党系' else 's'}"
        if sub not in orgs:
            base = orgs[a[1]]
            orgs[sub] = [f"{base[0]}（{m.group(1)}）", base[1], base[2], base[3], base[4]]
        a[1] = sub
sources = {s["source_id"]: [s["title"], s["url"], s["revision_id"], s["accessed"]] for s in rows("sources.csv")}
aliases = [[a["person_id"], a["alias"]] for a in rows("aliases.csv")]
posts = [[r["person_id"], r["kind"], r["post"], r["body"], r["as_of"], r["note"], r["source_id"]] for r in rows("posts.csv")]
kin = [[k["person_id"], k["other_person_id"], k["other_name"], k["relation"], k["category"], k["line"], k["degree"],
        k["other_title"], k["national"], k["source_id"]] for k in rows("kin.csv")]
out = {"built": max(s[3] for s in sources.values()), "elections": elections, "orgs": orgs, "districts": districts,
       "persons": persons, "terms": terms, "affs": affs, "sources": sources, "aliases": aliases, "posts": posts, "kin": kin}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(OUT, os.path.getsize(OUT), "bytes")
