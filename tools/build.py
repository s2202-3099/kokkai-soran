"""並立制の衆院選の当選者と、その投票日に在職していた参院議員から、台帳の各表（CSV）を作る。

使い方: python build.py <衆院の作業フォルダ> <参院の作業フォルダ> <data フォルダ>
衆院の作業フォルダには winners.json（winners.extract の結果）、elections.json（選挙記事）、
person_articles.json（当選者の記事）、soumu/ の総務省の表が入っている前提。
参院の作業フォルダには src.json（通常選挙の記事）、sanin_winners.json（sanin.extract の結果）、
person_articles_san.json（参院議員の記事）が入っている前提。
"""
import csv
import json
import os
import re
import sys
from datetime import date

import hosen
import kuriage
import person
import soumu

W, W2, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
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
           "チームみらい": "2019年以降の新党", "減税日本・ゆうこく連合": "2019年以降の新党",
           "民進党": "非自民再編系",
           # 参院の当選者から加わった党（1992〜2025年）
           "日本社会党": "社会党系", "民社党": "中道系", "日本新党": "非自民再編系",
           "おおさか維新の会": "維新系", "生活の党と山本太郎となかまたち": "非自民再編系",
           "たちあがれ日本": "保守系", "新党改革": "保守系",
           "スポーツ平和党": "諸派", "第二院クラブ": "諸派", "護憲・ヒロシマの会": "諸派", "沖縄社会大衆党": "諸派",
           "平和・市民": "諸派", "NHKから国民を守る党": "諸派", "NHK党": "諸派",
           "明日の日本をひらく兵庫の会": "諸派", "あいち改革推進協議会": "諸派", "アイ・ラブ沖縄！かがやく県民の会": "諸派", "結集ひろしま": "諸派"}
ORG_NOTE = {"中道改革連合": {"founded": "2026-01-16", "dissolved": "",
                       "_pred": ["立憲民主党", "公明党"]},
            # 党名の変更は、名前ごとに別の行にして前身・後身でつなぐ
            "社会民主党": {"_pred": ["日本社会党"]}, "日本維新の会": {"_pred": ["おおさか維新の会"]},
            "生活の党と山本太郎となかまたち": {"_pred": ["生活の党"]}, "NHK党": {"_pred": ["NHKから国民を守る党"]},
            "民主党（1998年結成）": {"_pred": ["民主党（1996年結成）"]}}
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
class TermBook(Book):
    """在職の番号は（人物・選挙・経路・その中の何番目か）で引く。始まりの日を直しても番号が変わらないように。"""
    def __init__(self, rows):
        rows = sorted(rows, key=lambda r: (r["person_id"], r["election_id"], r["route"], r["start_date"], r["term_id"]))
        seen = {}
        for r in rows:
            k = (r["person_id"], r["election_id"], r["route"])
            seen[k] = seen.get(k, 0) + 1
            r["_k"] = k + (seen[k],)
        super().__init__("T", 6, rows, "term_id", lambda r: r["_k"])
        self.used = {}

    def next(self, person_id, election_id, route):
        k = (person_id, election_id, route)
        self.used[k] = self.used.get(k, 0) + 1
        return self.get(k + (self.used[k],))


TBOOK = TermBook(read_old("terms.csv"))
OBOOK = Book("O", 4, read_old("orgs.csv"), "org_id", lambda r: r["name"])
SBOOK = Book("S", 6, read_old("sources.csv"), "source_id", lambda r: (r["url"], str(r["revision_id"])))
elec_art = {int(k): v for k, v in json.load(open(f"{W}/elections.json")).items()}
arts = json.load(open(f"{W}/person_articles.json"))
if os.path.exists(f"{W}/person_articles_extra.json"):
    arts.update(json.load(open(f"{W}/person_articles_extra.json")))
arts.update(json.load(open(f"{W2}/person_articles_san.json")))
kuri = {n: kuriage.extract(elec_art[n]["text"]) for n in elec_art}
hos = {n: hosen.extract(elec_art[n]["text"]) for n in elec_art}


def by_party(name, day):
    """補選の表の党派名を、台帳の政党名にそろえる（同名の党は日付で分ける）。"""
    import winners as _w
    name = _w.canon(name)[0] if name else "無所属"
    if name == "民主党":
        return "民主党（1996年結成）" if day < "1998-04-27" else "民主党（1998年結成）"
    if name == "諸派" and day == "1996-03-24":
        return "無所属"  # 岐阜県補選の大野つや子。記事の表では諸派だが、本人の記事では自社さ推薦の無所属
    if name == "日本維新の会" and day < "2014-09-21":
        return "日本維新の会（2012年結成）"
    return name


for n in hos:
    for h in hos[n]:
        if h["kind"] != "未実施":
            h["party"] = by_party(h["winner_party"], h["date"])

# ---- 参院の通常選挙（第16〜27回）----
# 回次: (投票日, 任期の始まり, 任期の終わり, 改選定数)。
# 任期は前の同じ組の任期が満了した翌日から6年。投票日が満了より後なら投票日から始まる。
SAN = {16: ("1992-07-26", "1992-07-26", "1998-07-25", 126), 17: ("1995-07-23", "1995-07-23", "2001-07-22", 126),
       18: ("1998-07-12", "1998-07-26", "2004-07-25", 126), 19: ("2001-07-29", "2001-07-29", "2007-07-28", 121),
       20: ("2004-07-11", "2004-07-26", "2010-07-25", 121), 21: ("2007-07-29", "2007-07-29", "2013-07-28", 121),
       22: ("2010-07-11", "2010-07-26", "2016-07-25", 121), 23: ("2013-07-21", "2013-07-29", "2019-07-28", 121),
       24: ("2016-07-10", "2016-07-26", "2022-07-25", 121), 25: ("2019-07-21", "2019-07-29", "2025-07-28", 124),
       26: ("2022-07-10", "2022-07-26", "2028-07-25", 124), 27: ("2025-07-20", "2025-07-29", "2031-07-28", 124)}
# 合併選挙で選ばれた任期3年の議員は、もう一方の組の任期の終わりまで
SAN_OTHER_END = {16: "1995-07-22", 26: "2025-07-28", 27: "2028-07-25"}
# 選挙記事の当選者表で「諸派」とまとめられた当選者（記事の党派別当選者内訳による）
SAN_PARTY_FIX = {(16, "栗原君子"): "護憲・ヒロシマの会", (16, "島袋宗康"): "沖縄社会大衆党",
                 (17, "田英夫"): "平和・市民", (23, "糸数慶子"): "沖縄社会大衆党"}
# 選挙記事の補欠選挙の表に載っていない、補選のないまま任期満了まで続いた欠員。
# 台帳の在職と議員の記事の情報欄（参議院議員の退任日）を突き合わせて見つけ、本人の記事の本文で理由を確かめたもの。
# (組の回次, 記事名, 欠員の日, 理由, 注記)
SAN_EXTRA_VACANCY = [
    (16, "森田健作", "1998-03-17", "退職", "衆議院東京4区補欠選挙の立候補による自動失職"),
    (17, "岩瀬良三", "2001-03-07", "退任", "記事の情報欄の退任日による。理由は記事の本文に書かれていない"),
    (17, "水野誠一", "2001-07-10", "辞職", "静岡県知事選挙立候補のため"),
    (18, "森山裕", "2004-04-13", "辞職", "衆議院鹿児島5区補欠選挙立候補のため"),
    (18, "井上吉夫", "2003-10-24", "死去", ""),
    (19, "荒井正吾", "2007-03-09", "辞職", "奈良県知事選挙立候補のため"),
    (20, "若林正俊", "2010-04-02", "辞職", "本会議での投票ボタンの押し間違い（代理投票）の責任をとって"),
    (21, "藤井孝男", "2012-12-04", "退職", "第46回衆院選の立候補による自動失職"),
    (23, "鴻池祥肇", "2018-12-25", "死去", ""),
    (23, "渡辺美知太郎", "2019-04-12", "辞職", "那須塩原市長選挙立候補のため。みんなの党の比例名簿は解党で取り下げられており繰上当選なし"),
    (23, "島田三郎", "2019-05-08", "死去", ""),
    (23, "山本一太", "2019-07-04", "退職", "群馬県知事選挙の立候補による自動失職"),
    (25, "島村大", "2023-08-30", "死去", ""),
    (25, "音喜多駿", "2024-10-15", "退職", "第50回衆院選の立候補による自動失職"),
    (26, "山本太郎", "2026-01-21", "辞職", ""),
]
san_src = json.load(open(f"{W2}/src.json"))
san_art = {n: san_src[f"第{n}回参議院議員通常選挙"] for n in SAN}
san_win = {int(k): v["rows"] for k, v in json.load(open(f"{W2}/sanin_winners.json")).items()}
# 選挙記事の当選者表の誤り：第22回（2010年）の栃木県選挙区は、落選した簗瀬進氏が当選者の欄に入っている。
# 同じ記事の「落選」の一覧と「初当選」の一覧、当選者の記事では上野通子氏（自由民主党）が当選。
SAN_WINNER_FIX = {(22, "簗瀬進"): {"article": "上野通子", "name": "上野通子", "party": "自由民主党",
                                  "fixnote": "選挙記事の当選者表では簗瀬進（民主党）となっているが、同じ記事の落選者一覧と初当選者一覧に従った"}}
for n, rows in san_win.items():
    for r in rows:
        r.update(SAN_WINNER_FIX.get((n, r["name"]), {}))
        r["raw_party"] = r["party"]
        p_ = SAN_PARTY_FIX.get((n, r["name"]), r["party"])
        r["party"] = by_party(p_, SAN[n][0]) if p_ != "無所属" else p_
san_kuri = {n: kuriage.extract(san_art[n]["text"]) for n in SAN}
san_hos = {n: hosen.extract(san_art[n]["text"]) for n in SAN}
for n in san_hos:
    for h in san_hos[n]:
        if h["kind"] != "未実施":
            h["party"] = by_party(h["winner_party"], h["date"])
nums = sorted(winners)
issues = []

SMD = {n: set(soumu.smd_candidates(os.path.join(W, f"soumu/c{n}.txt"))) for n in nums if n in CAND_URL}

# ---- 出典 ----
sources = []


OLD_ACCESSED = {r["source_id"]: r["accessed"] for r in read_old("sources.csv")}


def add_source(title, url, kind, rev=""):
    sid = SBOOK.get((url, str(rev)))
    # 取得日は、その版を初めて記録した日のまま残す（作り直すたびに変えない）
    sources.append({"source_id": sid, "title": title, "url": url, "accessed": OLD_ACCESSED.get(sid, TODAY),
                    "revision_id": rev, "kind": kind})
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
    for h in hos[n]:
        if h["winner_article"]:
            ensure_person(h["winner_article"], h["winner_name"])
for n in SAN:
    for r in san_win[n]:
        ensure_person(r["article"], r["name"])
    for k in san_kuri[n]:
        if k["new_article"]:
            ensure_person(k["new_article"], k["new_name"])
    for h in san_hos[n]:
        if h["winner_article"]:
            ensure_person(h["winner_article"], h["winner_name"])
P = {p["person_id"]: p for p in persons}
for a in aliases:
    a["person_id"] = pid_of[a["_key"]]


def pid(article):
    rec = info.get(article)
    return pid_of[rec["title"] if rec else article]


# ---- 団体（政党） ----
orgs, oid_of = [], {}
SRC_SAN = {n: add_source(f"Wikipedia 第{n}回参議院議員通常選挙", "https://ja.wikipedia.org/wiki/" + san_art[n]["title"],
                         "wikipedia", san_art[n]["revid"]) for n in SAN}
party_rows = [(SRC_ELEC[n], r) for n in nums for r in winners[n] + [h for h in hos[n] if h["kind"] != "未実施"]]
party_rows += [(SRC_SAN[n], r) for n in SAN for r in san_win[n] + [h for h in san_hos[n] if h["kind"] != "未実施"]]
for src_, r in party_rows:
        p = r["party"]
        if p == "無所属" or p in oid_of:
            continue
        oid = OBOOK.get(p)
        oid_of[p] = oid
        orgs.append({"org_id": oid, "name": p, "kind": "政党", "lineage": LINEAGE.get(p, ""), "founded": "",
                     "dissolved": "", "predecessors": "", "successors": "", "source_id": src_})
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


for n, (vote, t0, t1, seats) in SAN.items():
    elections.append({"election_id": f"san-{n:03d}", "house": "参", "number": n, "date": vote, "kind": "通常選挙",
                      "system": "選挙区・比例代表", "seats": seats, "source_id": SRC_SAN[n]})


def san_district_id(pref, n):
    import winners as _w
    if pref is None:
        did, name, system, pref_, frm, to = "san-pr", "比例区", "比例代表", "", "1983", ""
    elif "・" in pref:
        did, name, system, pref_, frm, to = f"san-dist-{pref}", "・".join(_w.PREF_FULL[x] for x in pref.split("・")) + "選挙区", \
            "選挙区", "", "2016", ""
    else:
        did, name, system, pref_, frm = f"san-dist-{pref}", _w.PREF_FULL[pref] + "選挙区", "選挙区", _w.PREF_FULL[pref], "1947"
        to = "2016" if pref in ("鳥取", "島根", "徳島", "高知") else ""
    if did not in dist_seen:
        dist_seen.add(did)
        districts.append({"district_id": did, "house": "参", "name": name, "system": system, "valid_from": frm,
                          "valid_to": to, "pref": pref_, "seats": "", "source_id": SRC_SAN[n]})
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
        tid = TBOOK.next(p, f"shu-{n:03d}", route)
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
def add_list_party(old, new_pid, start, src):
    """繰上当選者の所属：名簿の政党（欠員になった議員の当選時の党派）。"""
    vote = next(e["date"] for e in elections if e["election_id"] == old["election_id"])
    a = next((x for x in affs if x["person_id"] == old["person_id"] and x["start_date"] in (old["start_date"], vote)), None)
    if a:
        affs.append({"person_id": new_pid, "org_id": a["org_id"], "start_date": start, "end_date": "", "role": "",
                     "basis": "doc", "source_id": src,
                     "note": f"繰上当選（{start}）。名簿の政党として、欠員になった議員の当選時の党派を入れた"})


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
            terms.append({"term_id": TBOOK.next(pid(k["new_article"]), f"shu-{n:03d}", "繰上"),
                          "person_id": pid(k["new_article"]), "house": "衆",
                          "election_id": f"shu-{n:03d}", "district_id": old["district_id"], "peer_type": "",
                          "route": "繰上", "list_rank": "", "start_date": k["seated"] or k["date"], "end_date": dis_next,
                          "end_reason": "解散" if dis_next else "", "basis": "doc", "source_id": SRC_ELEC[n]})
            add_list_party(old, pid(k["new_article"]), k["seated"] or k["date"], SRC_ELEC[n])

# ---- 小選挙区の補欠選挙・再選挙と、補選のないまま残った欠員 ----
by_count = {}
for n in nums:
    dis_next = ELECTIONS.get(n + 1, ("", "", 0))[0]
    for h in sorted(hos[n], key=lambda x: x["vacated_date"]):
        want = (info.get(h["old_article"]) or {}).get("title", h["old_article"]) if h["old_article"] else None
        cands = [t for t in terms if t["election_id"] == f"shu-{n:03d}" and t["start_date"] <= h["vacated_date"]
                 and (not t["end_date"] or t["end_date"] >= h["vacated_date"])
                 and (P[t["person_id"]]["jawiki_title"] == want
                      or P[t["person_id"]]["name"] == re.sub(r" \(.*\)$", "", h["old_name"] or ""))]
        if not cands:
            issues.append(f"第{n}回の補選 {h['district']}：欠員 {h['old_name']} の在職を見つけられない")
            continue
        old = max(cands, key=lambda t: t["start_date"])
        if not old["route"] in ("小選挙区", "補選"):
            issues.append(f"第{n}回の補選 {h['district']}：欠員 {h['old_name']} は{old['route']}の議員")
        old["end_date"], old["end_reason"] = h["vacated_date"], h["reason"]
        if h["kind"] == "未実施":
            old["note"] = "補欠選挙は行われず、欠員のまま解散・任期満了"
            by_count.setdefault(n, {}).setdefault("未実施", 0)
            by_count[n]["未実施"] += 1
            continue
        if not h["winner_article"]:
            issues.append(f"第{n}回の補選 {h['district']}：当選者の記事名がない（{h['winner_name']}）")
            continue
        np_ = pid(h["winner_article"])
        terms.append({"term_id": TBOOK.next(np_, f"shu-{n:03d}", "補選"), "person_id": np_, "house": "衆",
                      "election_id": f"shu-{n:03d}", "district_id": old["district_id"], "peer_type": "",
                      "route": "補選", "list_rank": "", "start_date": h["date"], "end_date": dis_next,
                      "end_reason": "解散" if dis_next else "", "basis": "doc", "source_id": SRC_ELEC[n]})
        if h["party"] != "無所属":
            affs.append({"person_id": np_, "org_id": oid_of[h["party"]], "start_date": h["date"], "end_date": "",
                         "role": "", "basis": "doc", "source_id": SRC_ELEC[n],
                         "note": f"補欠選挙（{h['date']}）の当選時の党派（選挙記事の補欠選挙の表）"})
        by_count.setdefault(n, {}).setdefault(h["kind"], 0)
        by_count[n][h["kind"]] += 1

# ---- 参院：通常選挙の当選者 ----
san_count = {}
for n, (vote, t0, t1, seats) in SAN.items():
    for r in san_win[n]:
        p = pid(r["article"])
        if r["kind"] == "選挙区":
            route = "合併選挙" if r["short"] else "選挙区"
            dist = san_district_id(r["pref"], n)
        else:
            route = "比例（特定枠）" if r["tokutei"] else "比例"
            dist = san_district_id(None, n)
        start = vote if r["short"] else t0
        end = SAN_OTHER_END[n] if r["short"] else t1
        note = "；".join(filter(None, ["合併選挙で選ばれた任期3年の議員" if r["short"] else "", r.get("fixnote", "")]))
        terms.append({"term_id": TBOOK.next(p, f"san-{n:03d}", route), "person_id": p, "house": "参",
                      "election_id": f"san-{n:03d}", "district_id": dist, "peer_type": "", "route": route,
                      "list_rank": "", "start_date": start, "end_date": end, "end_reason": "任期満了",
                      "basis": "doc", "source_id": SRC_SAN[n], "note": note})
        san_count[(n, route)] = san_count.get((n, route), 0) + 1
        if r["party"] != "無所属":
            note = "投票日時点の党派（選挙記事の当選者表）"
            if r["raw_party"] != r["party"] and (n, r["name"]) in SAN_PARTY_FIX:
                note += f"。記事の当選者表では「{r['raw_party']}」とまとめられている"
            if r.get("fixnote"):
                note += "。" + r["fixnote"]
            affs.append({"person_id": p, "org_id": oid_of[r["party"]], "start_date": vote, "end_date": "",
                         "role": "", "basis": "doc", "source_id": SRC_SAN[n], "note": note})


def san_find(n, article, name, day):
    """第n回の組で、day に在職していた人の在職を探す（繰上・補選で入った人も含む）。"""
    want = (info.get(article) or {}).get("title", article) if article else None
    base = re.sub(r" \(.*\)$", "", name or "")
    c = [t for t in terms if t["election_id"] == f"san-{n:03d}" and t["start_date"] <= day
         and (not t["end_date"] or t["end_date"] >= day)
         and (P[t["person_id"]]["jawiki_title"] == want or (base and P[t["person_id"]]["name"] == base))]
    return max(c, key=lambda t: t["start_date"]) if c else None


# 比例区の繰上当選・選挙区の補欠選挙などを、日付の順に当てる
san_events = [("繰", n, k["date"], k) for n in SAN for k in san_kuri[n]] + \
             [("補", n, h["vacated_date"], h) for n in SAN for h in san_hos[n]] + \
             [("欠", n, d_, {"article": a_, "reason": r_, "note": nt_}) for n, a_, d_, r_, nt_ in SAN_EXTRA_VACANCY]
san_events.sort(key=lambda e: e[2])
by_count_san = {}
for typ, n, day, ev in san_events:
    end = SAN[n][2]
    if typ == "欠":
        old = san_find(n, ev["article"], ev["article"], day)
        if not old:
            issues.append(f"参院第{n}回の組：欠員 {ev['article']}（{day}）の在職を見つけられない")
            continue
        old["end_date"], old["end_reason"], old["basis"] = day, ev["reason"], "art"
        old["note"] = "；".join(filter(None, [ev["note"], "選挙記事の補欠選挙の表になく、本人の記事で確かめた欠員。補欠選挙・繰上当選はなし"]))
        old["source_id"] = P[old["person_id"]]["_src"]
        continue
    if typ == "繰":
        old = san_find(n, ev["old_article"], ev["old_name"], day)
        if not old:
            issues.append(f"参院第{n}回の組：欠員 {ev['old_name']}（{day}）の在職を見つけられない")
            continue
        old["end_date"], old["end_reason"] = day, ev["reason"]
        if not ev["new_article"]:
            old["note"] = "名簿に繰り上げる人がおらず、欠員のまま任期満了"
            continue
        np_ = pid(ev["new_article"])
        start = ev["seated"] or day
        terms.append({"term_id": TBOOK.next(np_, f"san-{n:03d}", "繰上"), "person_id": np_, "house": "参",
                      "election_id": f"san-{n:03d}", "district_id": old["district_id"], "peer_type": "",
                      "route": "繰上", "list_rank": "", "start_date": start, "end_date": end, "end_reason": "任期満了",
                      "basis": "doc", "source_id": SRC_SAN[n], "note": ""})
        add_list_party(old, np_, start, SRC_SAN[n])
        continue
    old = san_find(n, ev["old_article"], ev["old_name"], day)
    if not old:
        issues.append(f"参院第{n}回の組：{ev['district']}の欠員 {ev['old_name']}（{day}）の在職を見つけられない")
        continue
    old["end_date"], old["end_reason"] = day, ev["reason"]
    by_count_san.setdefault(n, {}).setdefault(ev["kind"], 0)
    by_count_san[n][ev["kind"]] += 1
    if ev["kind"] == "未実施":
        old["note"] = "補欠選挙は行われず、欠員のまま任期満了"
        continue
    if ev["kind"] == "合併選挙":
        # 当選者は次の通常選挙の当選者表に「任期3年」として入っている
        continue
    if not ev["winner_article"]:
        issues.append(f"参院第{n}回の組：{ev['district']}の補選の当選者に記事名がない（{ev['winner_name']}）")
        continue
    np_ = pid(ev["winner_article"])
    route = {"補欠選挙": "補選", "再選挙": "再選挙", "繰上当選": "繰上"}.get(ev["kind"], ev["kind"])
    terms.append({"term_id": TBOOK.next(np_, f"san-{n:03d}", route), "person_id": np_, "house": "参",
                  "election_id": f"san-{n:03d}", "district_id": old["district_id"], "peer_type": "",
                  "route": route, "list_rank": "", "start_date": ev["date"], "end_date": end, "end_reason": "任期満了",
                  "basis": "doc", "source_id": SRC_SAN[n],
                  "note": "選挙区の次点からの繰上当選（投票日から3か月以内の欠員）" if route == "繰上" else ""})
    if ev["party"] != "無所属":
        affs.append({"person_id": np_, "org_id": oid_of[ev["party"]], "start_date": ev["date"], "end_date": "",
                     "role": "", "basis": "doc", "source_id": SRC_SAN[n],
                     "note": f"{ev['kind']}（{ev['date']}）の当選時の党派（選挙記事の補欠選挙の表）"})

# ---- 検証：衆院の投票日ごとの参院の在職者数 ----
san_snap = []
for n, (dis, D, _) in ELECTIONS.items():
    groups = [m for m, v in SAN.items() if v[1] <= D <= v[2]]
    seats = sum(SAN[m][3] for m in groups)
    inoff = [t for t in terms if t["house"] == "参" and t["start_date"] <= D and t["end_date"] >= D]
    ended = [t for t in terms if t["house"] == "参" and int(t["election_id"][4:]) in groups
             and t["end_date"] < D and t["end_date"] < SAN[int(t["election_id"][4:])][2]
             and not (t["route"] == "合併選挙" and t["end_reason"] == "任期満了")]
    refill = [t for t in terms if t["house"] == "参" and t["route"] in ("繰上", "補選", "再選挙")
              and int(t["election_id"][4:]) in groups and t["start_date"] <= D]
    refill += [t for t in terms if t["house"] == "参" and t["route"] == "合併選挙" and t["start_date"] <= D <= t["end_date"]]
    vac = len(ended) - len(refill)
    san_snap.append({"shu": n, "date": D, "groups": groups, "seats": seats, "in_office": len(inoff), "vacant": vac,
                     "ok": len(inoff) + vac == seats})

# ---- 検証：参院議員の記事の情報欄（参議院議員の退任日）と台帳の在職の終わり ----
tenure_check = []
by_person = {}
for t in terms:
    if t["house"] == "参":
        by_person.setdefault(t["person_id"], []).append(t)
for p_, ts in by_person.items():
    rec = info.get(P[p_]["jawiki_title"])
    if not rec or not rec.get("san_tenure"):
        continue
    ends = [e for _, e in rec["san_tenure"] if e and e != "現職" and len(e) == 10]
    for t in ts:
        if t["end_reason"] != "任期満了":
            continue
        for e in ends:
            if t["start_date"] < e < t["end_date"]:
                # 情報欄では任期の途中で退任しているのに、台帳では任期満了まで在職になっている
                cont = any(s_ and s_ > e and s_ <= t["end_date"] and len(s_) == 10 and
                           (date.fromisoformat(s_) - date.fromisoformat(e)).days <= 3
                           for s_, _ in rec["san_tenure"])
                if not cont:
                    tenure_check.append({"person": P[p_]["name"], "term": t["term_id"], "election": t["election_id"],
                                         "ledger_end": t["end_date"], "infobox_end": e})

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

# ---- 人物：初当選の年と前職（本人の記事から） ----
FIRST_RANGE = {"shu-041", "san-016", "san-017"}  # 台帳でいちばん古い回。ここが最初の在職でも、それより前の当選がありうる
for p_ in persons:
    rec = info.get(p_["jawiki_title"]) or {}
    ts = sorted((t for t in terms if t["person_id"] == p_["person_id"]), key=lambda t: t["start_date"])
    led = (int(ts[0]["start_date"][:4]), ts[0]["house"], "台帳") if ts else None
    f = rec.get("first")
    if f and led and led[0] < f[0]:
        issues.append(f"初当選の年：{p_['name']} は記事では{f[0]}年だが、台帳に{led[0]}年の在職がある")
        f = led
    if not f and led and ts[0]["election_id"] not in FIRST_RANGE:
        f = led
    p_["first_elected"], p_["first_house"], p_["first_basis"] = (str(f[0]), f[1], {"選挙歴": "art", "情報欄": "art", "台帳": "doc"}[f[2]]) if f else ("", "", "")
    p_["prev_job"] = rec.get("prev_job", "")

# ---- 派閥：自民党版（2009年・2026年）の分類を取り込む ----
# 自民党議員 派閥別名簿（jimin-rekishi の2009年版、jimin-meibo の2026年版）のデータ。
# どちらもその時点での所属だけが分かっているので、期間ではなく as_of（その日の所属）として入れる。
FACTION_ORG = {
    "清和政策研究会": "清和会系", "平成研究会": "平成研系", "宏池会": "宏池会系", "志帥会": "志帥会系",
    "近未来政治研究会": "近未来系", "為公会": "為公会系", "志公会": "為公会系", "番町政策研究所": "番町研系",
    "新しい波": "志帥会系", "菅グループ": "無派閥グループ", "石破グループ": "無派閥グループ", "有隣会": "無派閥グループ",
    "無派閥": "無派閥"}
LDP_NAME = {"浅田真澄美": "浅田ますみ"}  # 自民党版の表記 → 台帳の表記（同じ人）
FACTION_PRED = {"志公会": ["為公会"], "志帥会": ["新しい波"]}
LDP_SETS = [
    ("ldp_2009.json", "2009-08-30", "自民党衆院議員 派閥別名簿 2009", "https://s2202-3099.github.io/jimin-rekishi/2009/",
     {"清和会": "清和政策研究会", "平成研": "平成研究会", "宏池会": "宏池会", "近未来": "近未来政治研究会", "為公会": "為公会",
      "志帥会": "志帥会", "番町研": "番町政策研究所", "二階G": "新しい波", "無派閥": "無派閥"},
     {"doc": "doc", "art": "art", "est": "est", "none": "none"}, {}),
    ("ldp_2026.json", "2026-10-15", "自民党議員 派閥別名簿（2026年10月15日現在）", "https://s2202-3099.github.io/jimin-meibo/",
     {"麻生派": "志公会", "安倍派": "清和政策研究会", "茂木派": "平成研究会", "岸田派": "宏池会", "二階派": "志帥会",
      "森山派": "近未来政治研究会", "菅G": "菅グループ", "石破G": "石破グループ", "谷垣G": "有隣会", "無派閥": "無派閥"},
     {"member": "doc", "old": "doc", "left": "doc", "est": "est", "none": "doc"},
     {"old": "旧派閥（2024年の解散時に所属）", "left": "解散前に退会", "est": "推定", "member": "所属", "none": ""}),
]
faction_count = {}
ldp_resolved = {}   # fname -> {自民党版の名前: person_id}
jimin26 = {}        # person_id -> (派閥, 区分, 注記)：2026年版の分類（解散時の所属を含む）
ldp_src = {}
for fname, as_of, title, url, gmap, bmap, kmap in LDP_SETS:
    path = os.path.join(W2, fname)
    if not os.path.exists(path):
        continue
    dat = json.load(open(path))
    src_ = add_source(title, url, "刊行資料")
    ldp_src[fname] = src_
    labels = {g[0]: g[1] for g in dat.get("groups", [])}
    if fname == "ldp_2026.json":
        labels = {"麻生派": "麻生派（志公会）", "安倍派": "旧安倍派（清和会）", "茂木派": "旧茂木派（平成研究会）",
                  "岸田派": "旧岸田派（宏池会）", "二階派": "旧二階派（志帥会）", "森山派": "旧森山派（近未来政治研究会）",
                  "菅G": "旧菅グループ", "石破G": "旧石破グループ", "谷垣G": "旧谷垣グループ（有隣会）", "無派閥": "無派閥"}
    # その日に在職していた人の中で名前を引く（同姓同名を避ける）
    vdate = "2009-08-30" if fname == "ldp_2009.json" else "2026-02-08"
    cand = {}
    for t in terms:
        if any(t["start_date"] <= d_ and (not t["end_date"] or t["end_date"] >= d_) for d_ in (vdate, as_of)):
            pp = P[t["person_id"]]
            for nm in {pp["name"], soumu.norm(pp["name"])} | {a["alias"] for a in aliases if a.get("_key") == pp["jawiki_title"]}:
                cand.setdefault((t["house"], nm), set()).add(pp["person_id"])
    for r in dat["rows"]:
        nm = LDP_NAME.get(r["n"], r["n"])
        ids = cand.get((r["h"], nm)) or cand.get((r["h"], soumu.norm(nm))) or set()
        if len(ids) != 1:
            issues.append(f"派閥の取り込み（{fname}）：{r['n']} を台帳で一人に決められない（{len(ids)}人）")
            continue
        ldp_resolved.setdefault(fname, {})[r["n"]] = next(iter(ids))
        if fname == "ldp_2026.json":
            jimin26[next(iter(ids))] = (gmap[r["g"]], r.get("k", ""), r.get("w", ""))
        org_name = gmap[r["g"]]
        if org_name not in oid_of:
            oid = OBOOK.get(org_name)
            oid_of[org_name] = oid
            orgs.append({"org_id": oid, "name": org_name, "kind": "派閥" if "グループ" not in org_name and org_name != "有隣会" else "グループ",
                         "lineage": FACTION_ORG[org_name], "founded": "", "dissolved": "", "predecessors": "",
                         "successors": "", "source_id": src_})
        kind = kmap.get(r.get("k"), "")
        note = "；".join(filter(None, [f"【{labels.get(r['g'], r['g'])}】", kind, r.get("w", "")]))
        affs.append({"person_id": next(iter(ids)), "org_id": oid_of[org_name], "start_date": "", "end_date": "",
                     "as_of": as_of, "role": "", "basis": bmap.get(r.get("k"), "doc"), "source_id": src_, "note": note})
        faction_count[fname] = faction_count.get(fname, 0) + 1
# ---- 役職と親族：自民党版（2009年・2026年）から ----
# 役職は「その日に就いていた」ことだけを as_of で持つ（就任日・退任日はまだ調べていない）。
POST_ASOF = {"ldp_2009.json": {"内閣": "2009-08-30", "副大臣": "2009-08-30", "政務官": "2009-08-30",
                               "党執行部": "2009-08-30", "党執行部後": "2009-09-29"},
             "ldp_2026.json": {"内閣": "2026-10-15", "副大臣": "2026-09-18", "政務官": "2026-09-18",
                               "党執行部": "2026-09-16", "党幹部": "2026-10-15", "衆院": "2026-10-05", "参院": "2026-10-21"}}
POST_BODY = {"ldp_2009.json": {"内閣": "麻生内閣", "副大臣": "麻生内閣", "政務官": "麻生内閣",
                              "党執行部": "自由民主党（麻生総裁）", "党執行部後": "自由民主党（谷垣総裁）"},
             "ldp_2026.json": {"内閣": "第2次高市改造内閣", "副大臣": "第2次高市改造内閣", "政務官": "第2次高市改造内閣",
                              "党執行部": "自由民主党（高市総裁）", "党幹部": "自由民主党（高市総裁）",
                              "衆院": "衆議院", "参院": "参議院"}}
POST_KIND = {"内閣": "閣僚", "副大臣": "副大臣", "政務官": "大臣政務官", "党執行部": "党執行部", "党執行部後": "党執行部",
             "党幹部": "党の幹部", "衆院": "衆議院の役職", "参院": "参議院の役職"}
by_name = {}
for p_ in persons:
    for nm in {p_["name"], soumu.norm(p_["name"])}:
        by_name.setdefault(nm, set()).add(p_["person_id"])
for a in aliases:
    for nm in {a["alias"], soumu.norm(a["alias"])}:
        by_name.setdefault(nm, set()).add(a.get("person_id") or pid_of.get(a["_key"]))


def unique_person(name):
    ids = by_name.get(name) or by_name.get(soumu.norm(name)) or set()
    return next(iter(ids)) if len(ids) == 1 else None


posts, kin, kin_checked, post_unmatched = [], {}, {}, []
for fname, *_ in LDP_SETS:
    path = os.path.join(W2, fname)
    if not os.path.exists(path):
        continue
    dat, res, src_ = json.load(open(path)), ldp_resolved.get(fname, {}), ldp_src[fname]
    for key, title, items in dat["posts"]:
        body = POST_BODY[fname][key]
        for role, name, note, _inr in items:
            pid_ = res.get(name) or unique_person(LDP_NAME.get(name, name))
            if not pid_:
                post_unmatched.append(f"{name}（{role}）")
                continue
            post = role
            if key == "副大臣" and not role.endswith("副大臣"):
                base, paren = re.match(r"([^（]*)(（.*）)?", role).groups()
                post = base + "副大臣" + (paren or "")
            if key == "政務官" and not role.endswith("政務官"):
                base, paren = re.match(r"([^（]*)(（.*）)?", role).groups()
                post = base + "大臣政務官" + (paren or "")
            posts.append({"person_id": pid_, "kind": POST_KIND[key], "post": post, "body": body, "start_date": "",
                          "end_date": "", "as_of": POST_ASOF[fname][key], "source_id": src_, "note": note})
    for name, ks in dat["kin"].items():
        pid_ = res.get(name)
        if not pid_:
            continue
        for k in ks:
            other = unique_person(k["o"]) if k.get("nat") else None
            kin[(pid_, k["o"])] = {"person_id": pid_, "other_person_id": other or "", "other_name": k["o"],
                                   "relation": k["rel"], "category": k["cat"], "line": k.get("line", ""),
                                   "degree": k.get("deg") if k.get("deg") is not None else "", "other_title": k.get("t", ""),
                                   "national": "1" if k.get("nat") else "", "source_id": src_}
    as_of = "2009-08-30" if fname == "ldp_2009.json" else "2026-10-15"
    for name, st in dat.get("kinstatus", {}).items():
        if st == "checked" and res.get(name):
            kin_checked[res[name]] = max(kin_checked.get(res[name], ""), as_of)
# ---- 選挙時の内閣（各版の投票日に在任していた閣僚・副大臣・政務官）----
import cabinet
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
pname_ = lambda x: re.sub(r"（\d{4}年結成）$", "", x)
CABINETS = [("第1次橋本内閣", "1996-10-20"), ("第1次森内閣", "2000-06-25"), ("第1次小泉第2次改造内閣", "2003-11-09"),
            ("第2次小泉改造内閣", "2005-09-11"), ("野田第3次改造内閣", "2012-12-16"), ("第2次安倍改造内閣", "2014-12-14"),
            ("第3次安倍第3次改造内閣", "2017-10-22"), ("第1次岸田内閣", "2021-10-31"), ("第1次石破内閣", "2024-10-27"),
            ("第1次高市内閣", "2026-02-08")]
by_title = {p_["jawiki_title"]: p_["person_id"] for p_ in persons}
cab_evidence = []   # 内閣の記事の所属欄にある派閥（派閥の当てはめで使う）
cab_unmatched = []
cab_path = os.path.join(W2, "cabinets.json")
if os.path.exists(cab_path):
    cabs = json.load(open(cab_path))
    for title, day in CABINETS:
        rec = cabs.get(title)
        if not rec:
            continue
        src_ = add_source(f"Wikipedia {rec['title']}", "https://ja.wikipedia.org/wiki/" + rec["title"], "wikipedia", rec["revid"])
        for r in cabinet.in_office(cabinet.extract(rec["text"]), day, ""):
            pid_ = by_title.get(r["article"]) or by_title.get((info.get(r["article"]) or {}).get("title", "")) \
                or unique_person(r["name"])
            if not pid_:
                cab_unmatched.append(f"{r['name']}（{title}・{r['post']}）")
                continue
            note = "；".join(filter(None, [r["extra"], r["note"]]))
            posts.append({"person_id": pid_, "kind": r["kind"], "post": r["post"], "body": title, "start_date": r["start"],
                          "end_date": r["end"], "as_of": day, "source_id": src_, "note": note[:200]})
            if r["faction"]:
                cab_evidence.append({"person_id": pid_, "day": day, "link": r["faction"][0], "label": r["faction"][1],
                                     "source_id": src_})
# ---- 党首（各版の衆院選の記事の情報欄）と、自民党の四役・参議院議長（歴代一覧と本人の記事の情報欄）----
import officers as officers_mod
LEADER_TITLE = {"自由民主党": "総裁", "日本共産党": "委員長", "社会民主党": "党首", "新進党": "党首", "公明党": "代表",
                "自由党": "党首", "保守党": "党首", "次世代の党": "党首"}
for n in nums:
    t = elec_art[n]["text"][:40000]
    vote = ELECTIONS[n][1]
    names = dict(re.findall(r"\|\s*(\d+)党名\s*=\s*([^\n]*)", t))
    for i, raw in re.findall(r"\|\s*(\d+)党首\s*=\s*([^\n]*)", t):
        party = LINK_RE.sub(lambda m: m.group(2) or m.group(1), names.get(i, "")).replace("'", "").strip()
        party = re.sub(r"\s*\(.*?\)", "", party)
        party_c = by_party(party, vote) if party else ""
        parts = re.split(r"<hr\s*/?>", re.sub(r"\{\{efn2?[^{}]*\}\}|<ref.*?</ref>|<ref[^>]*/>", "", raw, flags=re.S))
        for j, part in enumerate(parts):
            for k_, m in enumerate(LINK_RE.finditer(part)):
                pid_ = by_title.get(m.group(1).strip()) or by_title.get((info.get(m.group(1).strip()) or {}).get("title", "")) \
                    or unique_person((m.group(2) or m.group(1)).strip().replace("'", ""))
                if not pid_:
                    continue  # 議員でない党首（知事など）や、台帳の範囲外の人
                title_ = LEADER_TITLE.get(pname_(party_c), "代表")
                post = title_ if (j == 0 and k_ == 0) or len(parts) == 1 else "共同代表"
                posts.append({"person_id": pid_, "kind": "党首", "post": post, "body": pname_(party_c), "start_date": "",
                              "end_date": "", "as_of": vote, "source_id": SRC_ELEC[n],
                              "note": "衆院選の記事の情報欄の党首" + ("（複数を並べて記載）" if len(parts) > 1 else "")})
OFFICER_POSTS = [("自由民主党幹事長", "幹事長", "党執行部", "自由民主党"), ("自由民主党総務会長", "総務会長", "党執行部", "自由民主党"),
                 ("自由民主党政務調査会長", "政務調査会長", "党執行部", "自由民主党"),
                 ("自由民主党選挙対策委員長", "選挙対策委員長", "党執行部", "自由民主党"), ("参議院議長", "議長", "参議院の役職", "参議院")]
# 一覧と情報欄で決まらず、本人の記事の本文・継承表で確かめたもの
OFFICER_FIX = {("2014-12-14", "自由民主党総務会長"): ("二階俊博", "本人の記事の本文（2014年9月、6年ぶりに総務会長に就任）"),
               ("2021-10-31", "自由民主党政務調査会長"): ("高市早苗", "本人の記事の本文（2021年10月1日、政務調査会長に再就任）"),
               ("2026-02-08", "自由民主党政務調査会長"): ("小林鷹之", "本人の記事の継承表（第64代、2025年〜現職）"),
               ("2026-02-08", "自由民主党幹事長"): ("鈴木俊一 (衆議院議員)", "本人の記事の継承表（第57代、2025年〜現職）"),
               # たけさんの指摘（2026-11-02）を受け、本人の記事の本文で確かめたもの
               ("1996-10-20", "自由民主党総務会長"): ("塩川正十郎", "本人の記事の本文（1996年の総選挙で「現職の党総務会長ながら落選」）"),
               ("2024-10-27", "自由民主党総務会長"): ("鈴木俊一 (衆議院議員)", "本人の記事の本文（2024年9月30日、再び総務会長に就任）"),
               ("2026-02-08", "自由民主党選挙対策委員長"): ("古屋圭司", "本人の記事の本文（2025年10月7日、選挙対策委員長に就任）")}
off_unresolved = []
off_path = os.path.join(W2, "officers.json")
if os.path.exists(off_path):
    offs = json.load(open(off_path))
    _op = os.path.join(W2, "officer_people.json")
    off_people = json.load(open(_op)) if os.path.exists(_op) else {}
    bt_ = {v["title"]: v for v in arts.values() if v}

    def article_of(a):
        r = arts.get(a) or arts.get(a.replace(" ", "_")) or bt_.get(a) or off_people.get(a)
        return r["text"] if r else None
    off_src = {k: add_source(f"Wikipedia {v['title']}", "https://ja.wikipedia.org/wiki/" + v["title"], "wikipedia", v["revid"])
               for k, v in offs.items()}
    for n in nums:
        vote = ELECTIONS[n][1]
        for key, post, kind, body in OFFICER_POSTS:
            if key == "自由民主党選挙対策委員長" and vote < "2007-09-01":
                continue
            if n == 45 and key != "参議院議長":
                continue  # 2009年は自民党版の名簿の党執行部がある
            r = officers_mod.at(vote, offs[key]["text"], key, article_of)
            if (vote, key) in OFFICER_FIX:
                art, why = OFFICER_FIX[(vote, key)]
                r = (art, "art", why)
            if not r or r[0] == "?":
                off_unresolved.append(f"{vote} {key}")
                continue
            pid_ = by_title.get(r[0]) or by_title.get((info.get(r[0]) or {}).get("title", "")) \
                or unique_person(re.sub(r" \(.*\)$", "", r[0]))
            if not pid_:
                off_unresolved.append(f"{vote} {key}（{r[0]} が台帳にいない）")
                continue
            posts.append({"person_id": pid_, "kind": kind, "post": post, "body": body, "start_date": "", "end_date": "",
                          "as_of": vote, "source_id": P[pid_]["_src"] if r[1] == "art" else off_src[key], "note": r[2]})
if off_unresolved:
    issues.append("投票日の党役員・議長を決められなかったもの：" + "、".join(off_unresolved))
if cab_unmatched:
    issues.append("内閣の役職で台帳に結びつかなかった人（民間からの閣僚・補佐官など）：" + "、".join(cab_unmatched))
# ---- 派閥：残りの版（自民党版の名簿がない版）を、内閣の記事と本人の記事から当てる ----
import faction as faction_mod
import faction_manual
FAC_SHORT = {"清和政策研究会": "清和会", "平成研究会": "平成研", "近未来政治研究会": "近未来研", "番町政策研究所": "番町研",
             "政策科学研究所": "政策科学研究所"}
GENERIC = {"清和会", "平成研", "経世会", "宏池会", "志帥会", "番町研", "大勇会", "為公会", "志公会", "新しい波", "水月会", "有隣会",
           "清和政策研究会", "平成研究会", "近未来政治研究会", "番町政策研究所", "政策科学研究所", "新財政研究会"}


def fac_label(entity, year, old=False):
    if entity == "無派閥":
        return "無派閥"
    if old:
        # 自民党版（2026年）と同じ書き方にそろえる
        fixed = {"清和政策研究会": "旧安倍派（清和会）", "平成研究会": "旧茂木派（平成研究会）", "宏池会": "旧岸田派（宏池会）",
                 "志帥会": "旧二階派（志帥会）", "近未来政治研究会": "旧森山派（近未来政治研究会）"}
        if entity in fixed and year >= 2021:
            return fixed[entity]
        lab = fac_label(entity, year)
        m = re.match(r"(.+?)（(.+)）$", lab)
        return f"旧{m.group(2)}（{m.group(1)}）" if m else "旧" + lab
    c = [(a, l_) for l_, e, a, b in faction_mod.LABELS if e == entity and a <= year <= b and l_ not in GENERIC
         and not l_.endswith("G")]
    short = FAC_SHORT.get(entity, entity)
    if not c:
        return short
    lab = max(c)[1]
    if entity == "宏池会（谷垣派系）":
        return f"{lab}（宏池会から分かれた加藤派の系統）"
    return f"{short}（{lab}）" if lab != short else short


def fac_org(entity, src_):
    name = "無派閥" if entity == "無派閥" else entity
    if name not in oid_of:
        oid = OBOOK.get(name)
        oid_of[name] = oid
        kind = "グループ" if name in ("菅グループ", "石破グループ", "有隣会") else "派閥"
        orgs.append({"org_id": oid, "name": name, "kind": kind, "lineage": faction_mod.LINEAGE.get(name, "無派閥"),
                     "founded": "", "dissolved": "", "predecessors": "", "successors": "", "source_id": src_})
    return oid_of[name]


# その時点の名簿（総裁選の推薦人一覧、派閥の記事の時点つきの構成表）
import snapshots as snapshots_mod
from datetime import date as _date
snap_by = {}
snap_src = {}
_fs = os.path.join(W2, "fac_src.json")
if os.path.exists(_fs):
    for sn in snapshots_mod.collect(json.load(open(_fs))):
        pid_ = by_title.get(sn["article"]) or by_title.get((info.get(sn["article"]) or {}).get("title", "")) or unique_person(sn["name"])
        if not pid_:
            continue
        y_ = int(sn["date"][:4])
        if sn["kind"] == "派閥の構成":
            ent = sn["label"]
        else:
            c = faction_mod.lookup(sn["label"], y_)
            if not c:
                continue
            ent = c[0][0]
        if sn["page"] not in snap_src:
            snap_src[sn["page"]] = add_source(f"Wikipedia {sn['page']}", "https://ja.wikipedia.org/wiki/" + sn["page"], "wikipedia", sn["revid"])
        snap_by.setdefault(pid_, []).append({**sn, "entity": ent, "source_id": snap_src[sn["page"]]})


def snap_at(pid_, day):
    """day にいちばん近い、およそ16か月以内の名簿。派閥の合流をまたぐときは合流先に直す。"""
    best = None
    for sn in snap_by.get(pid_, []):
        gap = abs((_date.fromisoformat(sn["date"]) - _date.fromisoformat(day)).days)
        if gap > 480:
            continue
        ent = sn["entity"]
        if ent == "政策科学研究所" and day >= "1999-03-18":
            ent = "志帥会"
        if ent in ("為公会", "番町政策研究所") and sn["date"] < "2017-07-01" <= day:
            ent = "志公会"
        if ent == "志公会" and day < "2017-07-01":
            continue
        if ent == "宏池会（谷垣派系）" and day >= "2008-05-01":
            ent = "宏池会"
        if best is None or gap < best[0]:
            best = (gap, ent, sn)
    return best


# 議員でなくなった時点の所属（派閥の記事の「その他国政選挙落選・引退者」）
exit_by = {}
if os.path.exists(_fs):
    for ex in snapshots_mod.exits(json.load(open(_fs))):
        pid_ = by_title.get(ex["article"]) or by_title.get((info.get(ex["article"]) or {}).get("title", "")) or unique_person(ex["name"])
        if pid_:
            if ex["page"] not in snap_src:
                snap_src[ex["page"]] = add_source(f"Wikipedia {ex['page']}", "https://ja.wikipedia.org/wiki/" + ex["page"], "wikipedia", ex["revid"])
            exit_by.setdefault(pid_, []).append({**ex, "source_id": snap_src[ex["page"]]})
last_end = {}
for t in terms:
    e_ = t["end_date"] or "9999"
    last_end[t["person_id"]] = max(last_end.get(t["person_id"], ""), e_)


def exit_at(pid_, day):
    """議員でなくなった時点の所属を、その日に当てる（8年以内に議員でなくなった人だけ。分裂・合流の前は元の派閥に直す）。"""
    xs = exit_by.get(pid_, [])
    end = last_end.get(pid_, "9999")
    if len(xs) != 1 or end == "9999" or end < day or int(end[:4]) - int(day[:4]) > 8:
        return None
    ent = xs[0]["entity"]
    if ent == "志公会系":
        ent = "志公会" if end >= "2017-07-01" else ("為公会" if end >= "2006-12-01" else "大勇会")
    if ent == "近未来政治研究会" and day < "1998-12-01":
        ent = "政策科学研究所"   # 山崎派は1998年に旧渡辺派から分かれた
    if ent in ("大勇会", "為公会") and day < "1998-12-01":
        ent = "宏池会"           # 河野グループは1998年に宮澤派から分かれた
    lo, hi = faction_mod.ENTITY_SPAN.get(ent, [0, 9999])
    if ent in ("志帥会", "志公会", "有隣会", "水月会") and not (lo <= int(day[:4]) <= hi):
        return None              # 結成前の所属は一つに決まらない
    return ent, xs[0], end


# ---- 参院議員の投票日時点の党派（国会会議録の会派から）----
# 参院議員は衆院の投票日には当選から最長6年たっていて、離党・入党・党の合流がありうる。
# 会議録で投票日にいちばん近い発言の会派を引き、当選時の党派と照らして「その日の党派」を as_of の行にする。
import kaiha as kaiha_mod
LINEAGE.update({"新社会党": "社会党系", "改革クラブ（1998年結成）": "非自民再編系", "自由党（2016年結成）": "非自民再編系",
                "太陽の党": "保守系", "日本のこころを大切にする党": "維新系", "改革クラブ": "保守系",
                "教育無償化を実現する会": "維新系", "みどりの風": "非自民再編系", "みどりの会議": "諸派", "国民の生活が第一": "非自民再編系"})
kaiha_mod.MINOR = {k for k, v in LINEAGE.items() if v in ("諸派", "2019年以降の新党")}
SRC_KAIHA = add_source("国会会議録検索システム（発言者の会派）", "https://kokkai.ndl.go.jp/", "公的記録")
_kj = os.path.join(W2, "kaiha.json")
kaiha_raw = json.load(open(_kj)) if os.path.exists(_kj) else {}
oname = {}
for o in orgs:
    oname[o["org_id"]] = o["name"]
PARTY_KINDS = {"政党"}
chairs = {}
for d_, xs in kaiha_mod.CHAIR.items():
    for nm, role, party in xs:
        pid_ = unique_person(nm)
        if pid_:
            chairs[(pid_, d_)] = (role, party)
        else:
            issues.append(f"参院{role} {nm}（{d_}）が台帳で一人に決まらない")
san_party_at, kaiha_unresolved, kaiha_stats = {}, [], {}
party_ids = {o["org_id"] for o in orgs if o["kind"] == "政党"}
_bt = {v["title"]: v["text"] for v in arts.values() if v}


def party_org(name):
    if name == "無所属":
        return ""
    if name not in oid_of:
        oid = OBOOK.get(name)
        oid_of[name] = oid
        oname[oid] = name
        orgs.append({"org_id": oid, "name": name, "kind": "政党", "lineage": LINEAGE.get(name, ""), "founded": "",
                     "dissolved": "", "predecessors": "", "successors": "", "source_id": SRC_KAIHA})
        if name not in LINEAGE:
            issues.append(f"系譜を決めていない政党: {name}")
    return oid_of[name]


for n in nums:
    D = ELECTIONS[n][1]
    for t in terms:
        if t["house"] != "参" or not (t["start_date"] <= D and (not t["end_date"] or t["end_date"] >= D)):
            continue
        pid_ = t["person_id"]
        # 当選時の党派：この在職の始まり（通常選挙は投票日）の所属の行。行がなければ無所属で当選
        e_date = next(e["date"] for e in elections if e["election_id"] == t["election_id"])
        keys = (t["start_date"],) if t["route"] in ("補選", "繰上", "再選挙") else (t["start_date"], e_date)
        mine = [a for a in affs if a["person_id"] == pid_ and a["start_date"] in keys and not a.get("as_of")
                and a["org_id"] in party_ids]
        base = oname[mine[0]["org_id"]] if mine else "無所属"
        r = kaiha_mod.decide(pid_, D, base, kaiha_raw.get(f"{pid_}|{D}"),
                             kaiha_mod.chain(_bt.get(P[pid_]["jawiki_title"], "")),
                             chairs.get((pid_, D)))
        party, basis, note = r
        if basis == "?":
            kaiha_unresolved.append(f"{D} {P[pid_]['name']}（{note}）")
        kaiha_stats.setdefault(D, {}).setdefault("kept" if party == base else "changed", 0)
        kaiha_stats[D]["kept" if party == base else "changed"] += 1
        oid = party_org(party)
        san_party_at[(pid_, D)] = oid
        affs.append({"person_id": pid_, "org_id": oid, "start_date": "", "end_date": "", "as_of": D, "role": "",
                     "basis": "est" if basis in ("est", "?") else basis, "source_id": SRC_KAIHA,
                     "note": f"投票日の党派；{note}"})
if kaiha_unresolved:
    issues.append("参院議員の投票日の党派を会派から決めきれず推定にしたもの：" + "、".join(kaiha_unresolved))

snap_conflict = []
exit_count = {}
cab_ev = {}
for ev in cab_evidence:
    cab_ev[(ev["person_id"], ev["day"])] = ev
fac_stats, fac_check = {}, {"agree": 0, "disagree": []}
pending_fac = []   # ここまでで決まらなかった (人, 投票日)。あとで他の時点の所属から埋める
ldp_oid = oid_of.get("自由民主党")
for n in nums:
    vote = ELECTIONS[n][1]
    if n in (45, 51):
        continue  # 2009年と2026年は自民党版の名簿から
    members = []
    for t in terms:
        if t["start_date"] <= vote and (not t["end_date"] or t["end_date"] >= vote):
            e_date = next(e["date"] for e in elections if e["election_id"] == t["election_id"])
            a = next((x for x in affs if x["person_id"] == t["person_id"] and x["start_date"] in (t["start_date"], e_date)), None)
            if t["house"] == "参":
                a = {"org_id": san_party_at.get((t["person_id"], vote))}   # 参院議員は投票日の党派で数える
            if a and a["org_id"] == ldp_oid:
                members.append(t["person_id"])
    dissolved = vote >= "2024-01-25"   # 2024年1月に麻生派以外の派閥が解散した後の版
    for pid_ in sorted(set(members)):
        y = int(vote[:4])
        if dissolved:
            # 解散後の版は、自民党版（2026年）と同じく解散時の所属（旧派閥）で示す
            j = jimin26.get(pid_)
            if j and j[1] in ("old", "left", "est") or (j and j[1] == "none"):
                ent = "無派閥" if j[0] == "無派閥" else j[0]
                lab = fac_label(ent, 2023, old=True) if j[1] in ("old", "est") and ent not in ("無派閥", "志公会") else fac_label(ent, 2023)
                if j[1] == "left":
                    lab = "無派閥"
                    ent = "無派閥"
                affs.append({"person_id": pid_, "org_id": fac_org(ent, ldp_src["ldp_2026.json"]), "start_date": "",
                             "end_date": "", "as_of": vote, "role": "", "basis": "est" if j[1] == "est" else "doc",
                             "source_id": ldp_src["ldp_2026.json"],
                             "note": "；".join(filter(None, [f"【{lab}】", "推定" if j[1] == "est" else "",
                                                            "2024年1月の解散時の所属（自民党版2026年の分類）。この投票日には麻生派以外の派閥はない"]))})
                fac_stats.setdefault(vote, {}).setdefault("doc", 0)
                fac_stats[vote]["doc"] += 1
                continue
            if j and j[1] == "member" and "移籍" not in j[2]:
                affs.append({"person_id": pid_, "org_id": fac_org("志公会", ldp_src["ldp_2026.json"]), "start_date": "",
                             "end_date": "", "as_of": vote, "role": "", "basis": "est", "source_id": ldp_src["ldp_2026.json"],
                             "note": "【志公会（麻生派）】；推定；2026年10月の自民党版で麻生派"})
                fac_stats.setdefault(vote, {}).setdefault("est", 0)
                fac_stats[vote]["est"] += 1
                continue
        rec = info.get(P[pid_]["jawiki_title"]) or {}
        raw = arts.get(P[pid_]["jawiki_title"]) or arts.get(P[pid_]["jawiki_title"].replace(" ", "_")) or {}
        if not raw:
            raw = next((v for v in arts.values() if v and v.get("title") == P[pid_]["jawiki_title"]), {}) or {}
        text = raw.get("text", "")
        res, why, src_, basis = None, "", P[pid_]["_src"], ""
        ce = None if dissolved else cab_ev.get((pid_, vote))
        guess = None
        day_ = "2023-12-31" if dissolved else vote
        if text:
            ch = faction_mod.chain(person.infobox(text))
            guess = faction_mod.at(day_, ch)
            gtxt = "→".join(ch)
            if not guess:
                guess = faction_mod.at_events(day_, faction_mod.events(text))
                gtxt = "本文の入会・退会の記述"
        if ce:
            c = faction_mod.lookup(ce["label"], y)
            if c and c[0][0]:
                res, basis, src_ = c[0][0], "doc", ce["source_id"]
                why = f"内閣の記事の所属欄（{ce['label']}）"
                if guess:
                    if guess[0] == res:
                        fac_check["agree"] += 1
                    else:
                        fac_check["disagree"].append(f"{P[pid_]['name']} {vote}：内閣{res}・推定{guess[0]}")
        sn = None if dissolved else snap_at(pid_, vote)
        mf = faction_manual.MANUAL.get((pid_, vote))
        if not res and mf:
            res, basis, why = mf[0], mf[1], f"本人の記事の本文を読んで確かめた（{mf[2]}）" + ("" if mf[1] == "art" else "。推定")
        if not res and sn and sn[0] <= 100:
            res, basis, src_ = sn[1], "doc", sn[2]["source_id"]
            why = f"{sn[2]['title']}（{sn[2]['date']}）で{sn[2]['label']}"
        elif not res and guess and guess[2] == "art":
            res, basis = guess[0], "art"
            why = f"本人の記事の所属政党欄（{gtxt}）から"
            if sn and sn[1] != res:
                snap_conflict.append(f"{P[pid_]['name']} {vote}：記事{res}・名簿{sn[1]}（{sn[2]['title']}）")
        elif not res and sn:
            res, basis, src_ = sn[1], "est", sn[2]["source_id"]
            why = f"{sn[2]['title']}（{sn[2]['date']}）で{sn[2]['label']}。投票日とは{sn[0]}日離れている"
        if not res and guess:
            res, basis = guess[0], guess[2]
            why = f"本人の記事の所属政党欄（{gtxt}）から" + ("" if basis == "art" else "推定")
        if res and sn and basis == "doc" and why.startswith("内閣") and sn[1] != res:
            snap_conflict.append(f"{P[pid_]['name']} {vote}：内閣{res}・名簿{sn[1]}（{sn[2]['title']}）")
        if not res:
            xa = exit_at(pid_, vote)
            if xa:
                res, basis, src_ = xa[0], "est", xa[1]["source_id"]
                why = f"{xa[1]['page']}の記事で、議員でなくなった時（{xa[2]}）にこの派閥にいた人の一覧にある。推定"
                exit_count[vote] = exit_count.get(vote, 0) + 1
        if res in ("為公会", "番町政策研究所") and vote >= "2017-07-01":
            res = "志公会"   # 2017年7月、為公会と番町政策研究所（山東派）などが合流して志公会に
        if not res:
            pending_fac.append((pid_, vote, dissolved, y, text))
            continue
        fac_stats.setdefault(vote, {}).setdefault(basis, 0)
        fac_stats[vote][basis] += 1
        lab = fac_label(res, 2023 if dissolved else y)
        if dissolved and res not in ("無派閥", "志公会"):
            lab, why = fac_label(res, 2023, old=True), why + "。2024年1月の解散前の所属（この投票日には派閥はない）"
        affs.append({"person_id": pid_, "org_id": fac_org(res, src_), "start_date": "", "end_date": "", "as_of": vote,
                     "role": "", "basis": basis, "source_id": src_,
                     "note": "；".join(filter(None, [f"【{lab}】", "推定" if basis == "est" else "", why]))})
# ---- 派閥：決まらなかった人を、他の時点で出てくる派閥で埋める ----
# 一度でもある派閥に出てくる人は、退会が書かれていない限りその派閥にいたものとする（たけさんの方針、2026-11-05）。
# 手がかり：台帳の他の版の派閥の行、その時点の名簿（離れていても）、議員でなくなった時の所属の一覧、本文の入会・退会、
# 情報欄の派閥が一つだけの場合。投票日より前の手がかりがあればいちばん近いもの、なければ投票日より後のいちばん近いもの。
FWD = [("為公会", "志公会", "2017-07-01"), ("番町政策研究所", "志公会", "2017-07-01"), ("政策科学研究所", "志帥会", "1999-03-18"),
       ("新しい波", "志帥会", "2009-11-01"), ("宏池会（谷垣派系）", "宏池会", "2008-05-01"), ("大勇会", "為公会", "2006-12-01"),
       ("水月会", "石破グループ", "2021-10-01")]
BWD = [("為公会", "大勇会", "2006-12-01"), ("大勇会", "宏池会", "1999-01-01"), ("近未来政治研究会", "政策科学研究所", "1998-12-01"),
       ("石破グループ", "水月会", "2021-10-01"), ("宏池会（谷垣派系）", "宏池会", "2001-01-01")]


def fac_move(ent, frm, day):
    """frm の日の派閥 ent を、合流・改称・分かれた元をたどって day の日の派閥に直す。決まらなければ None。"""
    if ent == "無派閥":
        return ent
    if frm <= day:
        changed = True
        while changed:
            changed = False
            for a, b, d in FWD:
                if ent == a and frm < d <= day:
                    ent, frm, changed = b, d, True
    else:
        changed = True
        while changed:
            changed = False
            for a, b, d in BWD:
                if ent == a and day < d:
                    ent, changed = b, True
    lo, hi = faction_mod.ENTITY_SPAN.get(ent, [0, 9999])
    return ent if lo <= int(day[:4]) <= hi else None


fac_evidence = {}
for a in affs:
    o = oname.get(a["org_id"]) or next((k for k, v in oid_of.items() if v == a["org_id"]), "")
    if a.get("as_of") and any(z["org_id"] == a["org_id"] and z["kind"] in ("派閥", "グループ") for z in orgs):
        d_ = "2023-12-31" if "解散時" in a["note"] or "解散前" in a["note"] else a["as_of"]
        lab = re.match(r"【([^】]*)】", a["note"])
        fac_evidence.setdefault(a["person_id"], []).append(
            (d_, o, f"{d_[:4]}年の所属（{lab.group(1) if lab else o}）", a["source_id"]))
for pid_, xs in snap_by.items():
    for sn in xs:
        fac_evidence.setdefault(pid_, []).append((sn["date"], sn["entity"], f"{sn['title']}（{sn['date']}）で{sn['label']}", sn["source_id"]))
for pid_, xs in exit_by.items():
    end = last_end.get(pid_, "9999")
    for ex in xs:
        if end != "9999" and ex["entity"] != "志公会系":
            fac_evidence.setdefault(pid_, []).append((end, ex["entity"], f"{ex['page']}の記事の、議員でなくなった時（{end}）にこの派閥にいた人の一覧", ex["source_id"]))
def persist_pick(pid_, day_, text, skip_day=None):
    ev = [x for x in fac_evidence.get(pid_, []) if x[0] != skip_day]
    if text:
        for ey, e, act in faction_mod.events(text):
            ev.append((f"{ey}-07-01", "無派閥" if act == "out" else e, f"本文の{ey}年の{'退会' if act == 'out' else '入会'}の記述", P[pid_]["_src"]))
    pick = None
    before = sorted((x for x in ev if x[0] <= day_), key=lambda x: x[0])
    after = sorted((x for x in ev if x[0] > day_), key=lambda x: x[0])
    if before:
        x = before[-1]
        ent = fac_move(x[1], x[0], day_)
        if ent:
            pick = (ent, x, "前")
    if not pick and after and after[0][1] != "無派閥":
        x = after[0]
        ent = fac_move(x[1], x[0], day_)
        if ent:
            pick = (ent, x, "後")
    if not pick and text:
        labs = faction_mod.chain(person.infobox(text))
        ents = {e for lab in labs for e, _a, _b in faction_mod.lookup(lab)} - {"無派閥"}
        lins = {faction_mod.LINEAGE.get(e, e) for e in ents}
        # 情報欄の派閥が一つの系譜だけなら、その系譜で投票日にあった派閥（一つに決まるときだけ）
        cand = {m for e in ents for m in [fac_move(e, "0000-01-01", day_), fac_move(e, "9999-12-31", day_)] if m}
        ent = next(iter(cand)) if len(lins) == 1 and len(cand) == 1 and "無派閥" not in labs else None
        if ent:
            if ent:
                pick = (ent, ("", ent, "本人の記事の情報欄（派閥はこれ一つだけ）", P[pid_]["_src"]), "")
    return pick


fill_count = {}
for pid_, vote, dissolved, y, text in pending_fac:
    day_ = "2023-12-31" if dissolved else vote
    pick = persist_pick(pid_, day_, text)
    if not pick:
        fac_stats.setdefault(vote, {}).setdefault("不明", 0)
        fac_stats[vote]["不明"] += 1
        continue
    res, x, side = pick
    why = (f"{x[2]}。それ以後に退会の記述がないので、この投票日も同じ派閥とした" if side == "前" else
           f"{x[2]}。それより前に別の派閥に入った記述がないので、この投票日も同じ派閥とした" if side == "後" else
           f"{x[2]}。退会の記述がないので、この投票日も同じ派閥とした")
    fill_count[vote] = fill_count.get(vote, 0) + 1
    fac_stats.setdefault(vote, {}).setdefault("est", 0)
    fac_stats[vote]["est"] += 1
    lab = fac_label(res, 2023 if dissolved else y)
    if dissolved and res not in ("無派閥", "志公会"):
        lab = fac_label(res, 2023, old=True)
    affs.append({"person_id": pid_, "org_id": fac_org(res, x[3]), "start_date": "", "end_date": "", "as_of": vote,
                 "role": "", "basis": "est", "source_id": x[3],
                 "note": "；".join([f"【{lab}】", "推定", "他の時点の所属から", why])})

# 確かめ：2009年の確かめ済みの名簿の人を、2009年の行を除いた手がかりだけで当てるとどうなるか
fill_check = {"agree": 0, "disagree": [], "none": 0}
for a in affs:
    if a.get("as_of") == "2009-08-30" and a["note"].startswith("【") and any(z["org_id"] == a["org_id"] and z["kind"] in ("派閥", "グループ") for z in orgs):
        truth = next((k for k, v in oid_of.items() if v == a["org_id"]), "")
        raw = arts.get(P[a["person_id"]]["jawiki_title"]) or {}
        pk = persist_pick(a["person_id"], "2009-08-30", raw.get("text", ""), skip_day="2009-08-30")
        if not pk:
            fill_check["none"] += 1
        elif pk[0] == truth:
            fill_check["agree"] += 1
        else:
            fill_check["disagree"].append(f"{P[a['person_id']]['name']}：名簿{truth}・当てはめ{pk[0]}（{pk[1][2]}）")

kin = sorted(kin.values(), key=lambda k: (k["person_id"], k["degree"] if k["degree"] != "" else 99))
posts.sort(key=lambda r: r["as_of"])  # 同じ時点の中は自民党版の並び（内閣の序列など）のまま
for p_ in persons:
    p_["kin_checked"] = kin_checked.get(p_["person_id"], "")
if post_unmatched:
    issues.append("役職の取り込みで台帳に結びつかなかった人（官僚・台帳の範囲外など）：" + "、".join(post_unmatched))

for o in orgs:
    for x in FACTION_PRED.get(o["name"], []):
        if x in oid_of:
            o["predecessors"] = ";".join(filter(None, [o["predecessors"], oid_of[x]]))
            q = next(z for z in orgs if z["org_id"] == oid_of[x])
            q["successors"] = ";".join(filter(None, [q["successors"], o["org_id"]]))

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
                   ("sources.csv", sources), ("posts.csv", posts), ("kin.csv", kin)]:
    cols = header(name)
    extra = {"terms.csv": ["note"], "persons.csv": ["first_elected", "first_house", "first_basis", "prev_job", "kin_checked"],
             "affiliations.csv": ["as_of"], "posts.csv": ["kind", "as_of", "note"], "kin.csv": ["national"]}.get(name, [])
    for c in extra:
        if c not in cols:
            pos = {"persons.csv": lambda: cols.index("note"), "affiliations.csv": lambda: cols.index("role"),
                   "posts.csv": lambda: (cols.index("post") if c == "kind" else (cols.index("source_id") if c == "as_of" else len(cols))),
                   "kin.csv": lambda: cols.index("source_id")}.get(name, lambda: len(cols))()
            cols.insert(pos, c)
    write(name, rows, cols)

missing_birth = [p["name"] for p in persons if not p["birth_date"]]
missing_kana = [p["name"] for p in persons if not p["name_kana"]]
report = {"persons": len(persons), "terms": len(terms), "affiliations": len(affs), "orgs": len(orgs),
          "sources": len(sources), "checks": checks, "missing_birth": missing_birth, "missing_kana": missing_kana,
          "issues": issues, "by_elections": by_count, "factions": faction_count, "posts": len(posts), "kin": len(kin), "faction_stats": fac_stats, "faction_check": fac_check, "snap_conflict": snap_conflict, "exit_count": exit_count, "fill_count": fill_count, "fill_check": fill_check, "san_snapshot": san_snap, "tenure_check": tenure_check, "san_by_elections": by_count_san,
          "san_routes": {f"{n}-{r}": c for (n, r), c in san_count.items()},
          "routes": {n: {k: sum(1 for t in terms if t["election_id"] == f"shu-{n:03d}" and t["route"] == k)
                         for k in ("小選挙区", "比例復活", "比例単独", "比例")} for n in nums}}
json.dump(report, open(os.path.join(W, "report.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in report.items() if k not in ("missing_kana",)}, ensure_ascii=False, indent=1)[:4000])
