"""並立制の衆院選の当選者から、台帳の各表（CSV）を作る。

使い方: python build_shu.py <作業フォルダ> <data フォルダ>
作業フォルダには winners.json（winners.extract の結果）、elections.json（選挙記事）、
person_articles.json（当選者の記事）、soumu/ の総務省の表が入っている前提。
"""
import csv
import json
import os
import re
import sys
from datetime import date

import kuriage
import person
import soumu

W, OUT = sys.argv[1], sys.argv[2]
ELECTIONS = {  # 回次: (解散日, 投票日, 定数)
    41: ("1996-09-27", "1996-10-20", 500), 42: ("2000-06-02", "2000-06-25", 480),
    43: ("2003-10-10", "2003-11-09", 480), 44: ("2005-08-08", "2005-09-11", 480),
    45: ("2009-07-21", "2009-08-30", 480), 46: ("2012-11-16", "2012-12-16", 480),
    47: ("2014-11-21", "2014-12-14", 475), 48: ("2017-09-28", "2017-10-22", 465),
    49: ("2021-10-14", "2021-10-31", 465), 50: ("2024-10-09", "2024-10-27", 465),
    51: ("2026-01-23", "2026-02-08", 465),
}
DISTRICT_VERSION = {48: "2017", 49: "2017", 50: "2022", 51: "2022"}
LINEAGE = {"自由民主党": "保守系", "立憲民主党": "非自民再編系", "国民民主党": "非自民再編系", "公明党": "中道系",
           "日本維新の会": "維新系", "日本共産党": "共産党", "社会民主党": "社会党系",
           "中道改革連合": "中道改革連合",
           "れいわ新選組": "2019年以降の新党", "参政党": "2019年以降の新党", "日本保守党": "2019年以降の新党",
           "チームみらい": "2019年以降の新党", "減税日本・ゆうこく連合": "2019年以降の新党"}
ORG_NOTE = {"中道改革連合": {"founded": "2026-01-16", "dissolved": "",
                       "_pred": ["立憲民主党", "公明党"]}}
SOUMU_FILES = {49: ("soumu/t49.xls", "https://www.soumu.go.jp/main_content/000776967.xls"),
               50: ("soumu/t50.xls", "https://www.soumu.go.jp/main_content/000979122.xls"),
               51: ("soumu/t51.xlsx", "https://www.soumu.go.jp/main_content/001061475.xlsx")}
TODAY = date.today().isoformat()

winners = {int(k): v for k, v in json.load(open(f"{W}/winners.json")).items()}
elec_art = {int(k): v for k, v in json.load(open(f"{W}/elections.json")).items()}
arts = json.load(open(f"{W}/person_articles.json"))
if os.path.exists(f"{W}/person_articles_extra.json"):
    arts.update(json.load(open(f"{W}/person_articles_extra.json")))
kuri = {n: kuriage.extract(elec_art[n]["text"]) for n in elec_art}
nums = sorted(winners)
issues = []

SMD = {n: set(soumu.smd_candidates(os.path.join(W, f"soumu/c{n}.txt"))) for n in nums}

# ---- 出典 ----
sources = []


def add_source(title, url, kind, rev=""):
    sid = f"S{len(sources) + 1:06d}"
    sources.append({"source_id": sid, "title": title, "url": url, "accessed": TODAY, "revision_id": rev, "kind": kind})
    return sid


SRC_ELEC = {n: add_source(f"Wikipedia 第{n}回衆議院議員総選挙", "https://ja.wikipedia.org/wiki/" + elec_art[n]["title"],
                          "wikipedia", elec_art[n]["revid"]) for n in nums}
SRC_CAND = {n: add_source(f"総務省 第{n}回衆院選 候補者別得票数（小選挙区）", url, "公的記録")
            for n, url in {49: "https://www.soumu.go.jp/main_content/000777792.pdf",
                           50: "https://www.soumu.go.jp/main_content/000979134.pdf",
                           51: "https://www.soumu.go.jp/main_content/001061487.pdf"}.items() if n in nums}
SRC_SOUMU = {n: add_source(f"総務省 第{n}回衆院選 届出政党等別男女別新前元別当選人数", SOUMU_FILES[n][1], "公的記録")
             for n in nums}

# ---- 人物 ----
info = {}
for t, rec in arts.items():
    if rec is None:
        issues.append(f"記事が見つからない: {t}")
        continue
    info[t] = person.extract(rec)
    if info[t]["disambiguation"]:
        issues.append(f"曖昧さ回避のページに当たった: {t}")

persons, pid_of, aliases = [], {}, []
def ensure_person(article, shown):
        rec = info.get(article)
        key = rec["title"] if rec else article
        base = re.sub(r" \(.*\)$", "", key)
        if shown and shown != base and not any(a["alias"] == shown and a["_key"] == key for a in aliases):
            aliases.append({"_key": key, "alias": shown, "kind": "表記ゆれ", "valid_from": "", "valid_to": "",
                            "source_id": ""})
        if key in pid_of:
            return
        pid = f"P{len(persons) + 1:06d}"
        pid_of[key] = pid
        src = add_source(f"Wikipedia {key}", "https://ja.wikipedia.org/wiki/" + key, "wikipedia",
                         rec["revid"] if rec else "")
        persons.append({"person_id": pid, "name": base,
                        "name_kana": rec["kana"] if rec else "", "birth_date": rec["birth"] if rec else "",
                        "death_date": "", "birth_pref": rec["birth_pref"] if rec else "", "sex": rec["sex"] if rec else "",
                        "jawiki_title": key, "jawiki_pageid": rec["pageid"] if rec else "",
                        "wikidata_qid": rec["qid"] if rec else "", "note": "", "_src": src})


for n in nums:
    for r in winners[n]:
        ensure_person(r["article"], r["name"])
    for k in kuri[n]:
        if k["new_article"]:
            ensure_person(k["new_article"], k["new_name"])
P = {p["person_id"]: p for p in persons}
for a in aliases:
    a["person_id"] = pid_of[a["_key"]]


def pid(article):
    rec = info.get(article)
    return pid_of[rec["title"] if rec else article]


# ---- 団体（政党） ----
orgs, oid_of = [], {}
for n in nums:
    for r in winners[n]:
        p = r["party"]
        if p == "無所属" or p in oid_of:
            continue
        oid = f"O{len(orgs) + 1:04d}"
        oid_of[p] = oid
        orgs.append({"org_id": oid, "name": p, "kind": "政党", "lineage": LINEAGE.get(p, ""), "founded": "",
                     "dissolved": "", "predecessors": "", "successors": "", "source_id": SRC_ELEC[n]})
        if p not in LINEAGE:
            issues.append(f"系譜を決めていない政党: {p}")
        if p in ORG_NOTE:
            orgs[-1].update({k: v for k, v in ORG_NOTE[p].items() if not k.startswith("_")})
for o in orgs:
    pred = ORG_NOTE.get(o["name"], {}).get("_pred", [])
    o["predecessors"] = ";".join(oid_of[x] for x in pred if x in oid_of)
    for x in pred:
        if x in oid_of:
            q = next(z for z in orgs if z["org_id"] == oid_of[x])
            q["successors"] = ";".join(filter(None, [q["successors"], o["org_id"]]))
for o in orgs:
    if o["name"] == "中道改革連合":
        o["source_id"] = add_source("Wikipedia 中道改革連合", "https://ja.wikipedia.org/wiki/中道改革連合", "wikipedia",
                                    "111551771")
ORIGIN = json.load(open(f"{W}/chudo_origin.json")) if os.path.exists(f"{W}/chudo_origin.json") else {}

# ---- 選挙・選挙区 ----
elections, districts, dist_seen = [], [], set()
for n, (dis, vote, seats) in ELECTIONS.items():
    elections.append({"election_id": f"shu-{n:03d}", "house": "衆", "number": n, "date": vote, "kind": "総選挙",
                      "system": "並立制", "seats": seats, "source_id": SRC_ELEC.get(n, "")})


def district_id(n, r):
    v = DISTRICT_VERSION[n]
    if r["kind"] == "小選挙区":
        did = f"shu-smd-{r['pref']}{r['district']}-{v}"
        name, system, pref = f"{r['pref']}{r['district']}区", "小選挙区", r["pref"]
    else:
        did = f"shu-pr-{r['block']}-{v}"
        name, system, pref = f"比例{r['block']}ブロック", "比例代表", ""
    if did not in dist_seen:
        dist_seen.add(did)
        districts.append({"district_id": did, "house": "衆", "name": name, "system": system, "valid_from": v,
                          "valid_to": "", "pref": pref, "seats": 1 if system == "小選挙区" else "",
                          "source_id": SRC_ELEC[n]})
    return did


# ---- 在職・所属 ----
terms, affs = [], []
for n in nums:
    dis_next = ELECTIONS.get(n + 1, ("", "", 0))[0]
    vote = ELECTIONS[n][1]
    for r in winners[n]:
        p = pid(r["article"])
        rec = info.get(r["article"])
        route, basis = r["kind"], "doc"
        if r["kind"] == "比例":
            er = (rec or {}).get("elections", {}).get(n)
            art_route = None
            if er and er[0] in ("比当", "比") and er[1] and not er[1].startswith("比例"):
                art_route = "比例復活"
            elif er and (er[1].startswith("比例") or not er[1]):
                art_route = "比例単独"
            names = {soumu.norm(r["name"]), soumu.norm(P[p]["name"])}
            if names & SMD[n]:
                route = "比例復活"
            elif art_route == "比例復活":
                route, basis = "比例復活", "art"
                issues.append(f"第{n}回 {r['name']}：総務省の小選挙区候補者一覧で名前を拾えず、記事の選挙歴で比例復活とした")
            else:
                route = "比例単独"
            if art_route and art_route != route:
                issues.append(f"第{n}回 {r['name']}：記事の選挙歴（{art_route}）と総務省の候補者一覧（{route}）が食い違う")
        tid = f"T{len(terms) + 1:06d}"
        terms.append({"term_id": tid, "person_id": p, "house": "衆", "election_id": f"shu-{n:03d}",
                      "district_id": district_id(n, r), "peer_type": "", "route": route, "list_rank": "",
                      "start_date": vote, "end_date": dis_next, "end_reason": "解散" if dis_next else "",
                      "basis": basis, "source_id": SRC_ELEC[n]})
        if r["party"] != "無所属":
            note = "投票日時点の党派（選挙記事の当選者表）"
            if r["party"] == "中道改革連合":
                o = ORIGIN.get((info.get(r["article"]) or {}).get("title", r["article"]))
                note += f"。{o}（立憲民主党と公明党の衆院議員が2026年1月16日に結成した党で、出身政党で分けた）" if o else ""
            if n == 50 and r["name"] == "河村たかし":
                note += "。総務省の集計では本人届出（政党等所属）"
            affs.append({"person_id": p, "org_id": oid_of[r["party"]], "start_date": vote, "end_date": "",
                         "role": "", "basis": "doc", "source_id": SRC_ELEC[n], "note": note})
        b = P[p]["birth_date"]
        if b:
            by, bm, bd = map(int, b.split("-"))
            vy, vm, vd = map(int, vote.split("-"))
            age = vy - by - ((vm, vd) < (bm, bd))
            if age < 25:
                issues.append(f"第{n}回 {r['name']}：投票日に{age}歳（被選挙権の年齢未満）")

# ---- 任期中の欠員と繰上当選 ----
for n in nums:
    dis_next = ELECTIONS.get(n + 1, ("", "", 0))[0]
    for k in kuri[n]:
        old = None
        for t in terms:
            if t["election_id"] != f"shu-{n:03d}":
                continue
            pp = P[t["person_id"]]
            if (k["old_article"] and pp["jawiki_title"] == (info.get(k["old_article"]) or {}).get("title", k["old_article"])) \
                    or pp["name"] == re.sub(r" \(.*\)$", "", k["old_name"] or ""):
                old = t
        if not old:
            issues.append(f"第{n}回の欠員 {k['old_name']} を当選者の中に見つけられない")
            continue
        old["end_date"], old["end_reason"] = k["date"], k["reason"]
        if k["new_article"]:
            terms.append({"term_id": f"T{len(terms) + 1:06d}", "person_id": pid(k["new_article"]), "house": "衆",
                          "election_id": f"shu-{n:03d}", "district_id": old["district_id"], "peer_type": "",
                          "route": "繰上", "list_rank": "", "start_date": k["date"], "end_date": dis_next,
                          "end_reason": "解散" if dis_next else "", "basis": "doc", "source_id": SRC_ELEC[n]})
issues.append("小選挙区の補欠選挙による異動はまだ入れていない")

# ---- 検証：総務省の党派別人数 ----
checks = []
for n in nums:
    off = soumu.party_totals(os.path.join(W, SOUMU_FILES[n][0]))
    mine = {}
    for r in winners[n]:
        mine[r["party"]] = mine.get(r["party"], 0) + 1
    diff = []
    for p in sorted(set(off) | set(mine)):
        a, b = off.get(p, {}).get("計", 0), mine.get(p, 0)
        if a != b:
            diff.append(f"{p} 公式{a}・台帳{b}")
    women_off = sum(v.get("女", 0) for v in off.values())
    women_mine = sum(1 for r in winners[n] if P[pid(r["article"])]["sex"] == "f")
    if women_off != women_mine:
        diff.append(f"女性 公式{women_off}・台帳{women_mine}")
    checks.append((n, sum(mine.values()), diff))

# ---- 書き出し ----
def write(name, rows, cols):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def header(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return f.readline().strip().split(",")


for name, rows in [("aliases.csv", aliases), ("persons.csv", persons), ("orgs.csv", orgs), ("elections.csv", elections),
                   ("districts.csv", districts), ("terms.csv", terms), ("affiliations.csv", affs),
                   ("sources.csv", sources)]:
    write(name, rows, header(name))

missing_birth = [p["name"] for p in persons if not p["birth_date"]]
missing_kana = [p["name"] for p in persons if not p["name_kana"]]
report = {"persons": len(persons), "terms": len(terms), "affiliations": len(affs), "orgs": len(orgs),
          "sources": len(sources), "checks": checks, "missing_birth": missing_birth, "missing_kana": missing_kana,
          "issues": issues,
          "routes": {n: {k: sum(1 for t in terms if t["election_id"] == f"shu-{n:03d}" and t["route"] == k)
                         for k in ("小選挙区", "比例復活", "比例単独", "比例")} for n in nums}}
json.dump(report, open(os.path.join(W, "report.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in report.items() if k not in ("missing_kana",)}, ensure_ascii=False, indent=1)[:4000])
