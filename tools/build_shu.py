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
DISTRICT_VERSION = {41: "1994", 42: "1994", 43: "2002", 44: "2002", 45: "2002", 46: "2002", 47: "2013",
                    48: "2017", 49: "2017", 50: "2022", 51: "2022"}
# 同じ名前で別の党があるものは、結成年を付けて分ける
ERA_NAME = {("民主党", 41): "民主党（1996年結成）", **{("民主党", n): "民主党（1998年結成）" for n in range(42, 48)},
            **{("日本維新の会", n): "日本維新の会（2012年結成）" for n in (46, 47)}}
# 選挙記事の表で「諸派」とまとめられた当選者の党派（記事の党派別当選者内訳と凡例の注記による）
PARTY_FIX = {(41, "土肥隆一"): "民主改革連合", (42, "徳田虎雄"): "自由連合", (42, "三村申吾"): "無所属の会",
             (42, "渡部恒三"): "無所属の会", (42, "土屋品子"): "無所属の会", (42, "中田宏"): "無所属の会",
             (42, "粟屋敏信"): "無所属の会", (43, "渡部恒三"): "無所属の会", (43, "徳田虎雄"): "自由連合"}
SUMMARY_ALIAS = {"政党自由連合": "自由連合"}
LINEAGE = {"新進党": "非自民再編系", "民主党（1996年結成）": "非自民再編系", "民主党（1998年結成）": "非自民再編系",
           "新党さきがけ": "非自民再編系", "民主改革連合": "非自民再編系", "自由党": "非自民再編系",
           "無所属の会": "非自民再編系", "日本未来の党": "非自民再編系", "生活の党": "非自民再編系",
           "希望の党": "非自民再編系", "みんなの党": "非自民再編系",
           "保守党": "保守系", "保守新党": "保守系", "国民新党": "保守系",
           "日本維新の会（2012年結成）": "維新系", "維新の党": "維新系", "次世代の党": "維新系",
           "自由連合": "諸派", "新党日本": "諸派", "新党大地": "諸派",
           "自由民主党": "保守系", "立憲民主党": "非自民再編系", "国民民主党": "非自民再編系", "公明党": "中道系",
           "日本維新の会": "維新系", "日本共産党": "共産党", "社会民主党": "社会党系",
           "中道改革連合": "中道改革連合",
           "れいわ新選組": "2019年以降の新党", "参政党": "2019年以降の新党", "日本保守党": "2019年以降の新党",
           "チームみらい": "2019年以降の新党", "減税日本・ゆうこく連合": "2019年以降の新党"}
ORG_NOTE = {"中道改革連合": {"founded": "2026-01-16", "dissolved": "",
                       "_pred": ["立憲民主党", "公明党"]}}
CAND_URL = {44: "https://www.soumu.go.jp/senkyo/senkyo_s/data/shugiin44/pdf/h17sousenkyo_050911_03_13.pdf",
            45: "https://www.soumu.go.jp/main_content/000037488.pdf", 46: "https://www.soumu.go.jp/main_content/000194197.pdf",
            47: "https://www.soumu.go.jp/main_content/000328955.pdf", 48: "https://www.soumu.go.jp/main_content/000516731.xls",
            49: "https://www.soumu.go.jp/main_content/000777792.pdf", 50: "https://www.soumu.go.jp/main_content/000979134.pdf",
            51: "https://www.soumu.go.jp/main_content/001061487.pdf"}
SOUMU_FILES = {45: ("soumu/t45.xls", "https://www.soumu.go.jp/main_content/000037622.xls"),
               46: ("soumu/t46.xls", "https://www.soumu.go.jp/main_content/000194183.xls"),
               47: ("soumu/t47.xls", "https://www.soumu.go.jp/main_content/000328943.xls"),
               48: ("soumu/t48.xls", "https://www.soumu.go.jp/main_content/000516719.xls"),
               49: ("soumu/t49.xls", "https://www.soumu.go.jp/main_content/000776967.xls"),
               50: ("soumu/t50.xls", "https://www.soumu.go.jp/main_content/000979122.xls"),
               51: ("soumu/t51.xlsx", "https://www.soumu.go.jp/main_content/001061475.xlsx")}
TODAY = date.today().isoformat()

winners = {int(k): v for k, v in json.load(open(f"{W}/winners.json")).items()}
for n, rows in winners.items():
    for r in rows:
        r["raw_party"] = r["party"]
        r["party"] = PARTY_FIX.get((n, r["name"]), r["party"])
        r["party"] = ERA_NAME.get((r["party"], n), r["party"])


def read_old(name):
    path = os.path.join(OUT, name)
    return list(csv.DictReader(open(path, encoding="utf-8"))) if os.path.exists(path) else []


class Book:
    """一度振った番号を変えないための帳簿。"""
    def __init__(self, prefix, width, rows, idcol, keyf):
        self.prefix, self.width, self.map = prefix, width, {}
        self.max = 0
        for r in rows:
            self.map[keyf(r)] = r[idcol]
            self.max = max(self.max, int(r[idcol][len(prefix):]))

    def get(self, key):
        if key not in self.map:
            self.max += 1
            self.map[key] = f"{self.prefix}{self.max:0{self.width}d}"
        return self.map[key]


PBOOK = Book("P", 6, read_old("persons.csv"), "person_id", lambda r: r["jawiki_title"])
TBOOK = Book("T", 6, read_old("terms.csv"), "term_id", lambda r: (r["person_id"], r["election_id"], r["start_date"], r["route"]))
OBOOK = Book("O", 4, read_old("orgs.csv"), "org_id", lambda r: r["name"])
SBOOK = Book("S", 6, read_old("sources.csv"), "source_id", lambda r: (r["url"], str(r["revision_id"])))
elec_art = {int(k): v for k, v in json.load(open(f"{W}/elections.json")).items()}
arts = json.load(open(f"{W}/person_articles.json"))
if os.path.exists(f"{W}/person_articles_extra.json"):
    arts.update(json.load(open(f"{W}/person_articles_extra.json")))
kuri = {n: kuriage.extract(elec_art[n]["text"]) for n in elec_art}
nums = sorted(winners)
issues = []

SMD = {n: set(soumu.smd_candidates(os.path.join(W, f"soumu/c{n}.txt"))) for n in nums if n in CAND_URL}

# ---- 出典 ----
sources = []


def add_source(title, url, kind, rev=""):
    sid = SBOOK.get((url, str(rev)))
    sources.append({"source_id": sid, "title": title, "url": url, "accessed": TODAY, "revision_id": rev, "kind": kind})
    return sid


SRC_ELEC = {n: add_source(f"Wikipedia 第{n}回衆議院議員総選挙", "https://ja.wikipedia.org/wiki/" + elec_art[n]["title"],
                          "wikipedia", elec_art[n]["revid"]) for n in nums}
SRC_CAND = {n: add_source(f"総務省 第{n}回衆院選 候補者別得票数（小選挙区）", url, "公的記録")
            for n, url in CAND_URL.items() if n in nums}
SRC_SOUMU = {n: add_source(f"総務省 第{n}回衆院選 届出政党等別男女別新前元別当選人数", SOUMU_FILES[n][1], "公的記録")
             for n in nums if n in SOUMU_FILES}

# ---- 人物 ----
info = {}
for t, rec in arts.items():
    if rec is None:
        issues.append(f"記事が見つからない: {t}")
        continue
    info[t] = person.extract(rec)
    if info[t]["disambiguation"]:
        issues.append(f"曖昧さ回避のページに当たった: {t}")

for _t, _x in list(info.items()):
    info.setdefault(_x["title"], _x)
for _t in list(info):
    info.setdefault(_t.replace("_", " "), info[_t])

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
        pid = PBOOK.get(key)
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
        oid = OBOOK.get(p)
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
            if n not in SMD:
                route, basis = (art_route or "比例"), "art"
                if not art_route:
                    issues.append(f"第{n}回 {r['name']}：比例復活か単独かを記事の選挙歴で確かめられなかった")
            elif names & SMD[n]:
                route = "比例復活"
            elif art_route == "比例復活":
                route, basis = "比例復活", "art"
                issues.append(f"第{n}回 {r['name']}：総務省の小選挙区候補者一覧で名前を拾えず、記事の選挙歴で比例復活とした")
            else:
                route = "比例単独"
            if n in SMD and art_route and art_route != route:
                issues.append(f"第{n}回 {r['name']}：記事の選挙歴（{art_route}）と総務省の候補者一覧（{route}）が食い違う")
        tid = TBOOK.get((p, f"shu-{n:03d}", vote, route))
        terms.append({"term_id": tid, "person_id": p, "house": "衆", "election_id": f"shu-{n:03d}",
                      "district_id": district_id(n, r), "peer_type": "", "route": route, "list_rank": "",
                      "start_date": vote, "end_date": dis_next, "end_reason": "解散" if dis_next else "",
                      "basis": basis, "source_id": SRC_ELEC[n]})
        if r["party"] != "無所属":
            note = "投票日時点の党派（選挙記事の当選者表）"
            if r["party"] == "中道改革連合":
                o = ORIGIN.get((info.get(r["article"]) or {}).get("title", r["article"]))
                note += f"。{o}（立憲民主党と公明党の衆院議員が2026年1月16日に結成した党で、出身政党で分けた）" if o else ""
            if r["raw_party"] != r["party"] and (n, r["name"]) in PARTY_FIX:
                note += f"。記事の当選者表では「{r['raw_party']}」とまとめられている"
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
            terms.append({"term_id": TBOOK.get((pid(k["new_article"]), f"shu-{n:03d}", k["date"], "繰上")),
                          "person_id": pid(k["new_article"]), "house": "衆",
                          "election_id": f"shu-{n:03d}", "district_id": old["district_id"], "peer_type": "",
                          "route": "繰上", "list_rank": "", "start_date": k["date"], "end_date": dis_next,
                          "end_reason": "解散" if dis_next else "", "basis": "doc", "source_id": SRC_ELEC[n]})
issues.append("小選挙区の補欠選挙による異動はまだ入れていない")

# ---- 検証：総務省の党派別人数 ----
import winners as winners_mod
checks = []
for n in nums:
    mine = {}
    for r in winners[n]:
        k = r["party"] if n not in SOUMU_FILES else r["raw_party"]
        k = re.sub(r"（\d{4}年結成）$", "", k)
        mine[k] = mine.get(k, 0) + 1
    if n in SOUMU_FILES:
        off = soumu.party_totals(os.path.join(W, SOUMU_FILES[n][0]))
        basis_name = "総務省"
    else:
        sm = winners_mod.summary_table(elec_art[n]["text"])
        off = {}
        for k, v in sm.items():
            k = SUMMARY_ALIAS.get(k, k)
            off.setdefault(k, {"計": 0, "女": 0})["計"] += v
        basis_name = "記事の党派別当選者内訳"
    diff = []
    for p in sorted(set(off) | set(mine)):
        a, b = off.get(p, {}).get("計", 0), mine.get(p, 0)
        if a != b:
            diff.append(f"{p} 公式{a}・台帳{b}")
    if n in SOUMU_FILES:
        women_off = sum(v.get("女", 0) for v in off.values())
        women_mine = sum(1 for r in winners[n] if P[pid(r["article"])]["sex"] == "f")
        if women_off != women_mine:
            diff.append(f"女性 公式{women_off}・台帳{women_mine}")
    checks.append((n, basis_name, sum(mine.values()), diff))

# ---- 書き出し ----
def write(name, rows, cols):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def header(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return f.readline().strip().split(",")


persons.sort(key=lambda r: r["person_id"])
terms.sort(key=lambda r: r["term_id"])
orgs.sort(key=lambda r: r["org_id"])
sources.sort(key=lambda r: r["source_id"])
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
