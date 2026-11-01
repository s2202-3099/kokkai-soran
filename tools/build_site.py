"""data/*.csv から、サイトが読む site.json を作る。

使い方: python3 tools/build_site.py <data フォルダ> <出力する site.json>
サイトの表示はすべてこのファイルから作る（版・人物のページは index.html の中で組み立てる）。
"""
import csv
import json
import os
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
            p.get("prev_job", "")] for p in rows("persons.csv")]
terms = [[t["term_id"], t["person_id"], t["house"], t["election_id"], t["district_id"], t["route"], t["start_date"],
          t["end_date"], t["end_reason"], t["basis"], t["source_id"], t.get("note", "")] for t in rows("terms.csv")]
affs = [[a["person_id"], a["org_id"], a["start_date"], a["end_date"], a["basis"], a["source_id"], a["note"], a.get("as_of", "")]
        for a in rows("affiliations.csv")]
sources = {s["source_id"]: [s["title"], s["url"], s["revision_id"], s["accessed"]] for s in rows("sources.csv")}
aliases = [[a["person_id"], a["alias"]] for a in rows("aliases.csv")]
out = {"built": max(s[3] for s in sources.values()), "elections": elections, "orgs": orgs, "districts": districts,
       "persons": persons, "terms": terms, "affs": affs, "sources": sources, "aliases": aliases}
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print(OUT, os.path.getsize(OUT), "bytes")
