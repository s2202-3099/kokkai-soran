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
    cols = header(name)
    if name == "terms.csv" and "note" not in cols:
        cols.append("note")
    write(name, rows, cols)

missing_birth = [p["name"] for p in persons if not p["birth_date"]]
missing_kana = [p["name"] for p in persons if not p["name_kana"]]
report = {"persons": len(persons), "terms": len(terms), "affiliations": len(affs), "orgs": len(orgs),
          "sources": len(sources), "checks": checks, "missing_birth": missing_birth, "missing_kana": missing_kana,
          "issues": issues, "by_elections": by_count, "san_snapshot": san_snap, "tenure_check": tenure_check, "san_by_elections": by_count_san,
          "san_routes": {f"{n}-{r}": c for (n, r), c in san_count.items()},
          "routes": {n: {k: sum(1 for t in terms if t["election_id"] == f"shu-{n:03d}" and t["route"] == k)
                         for k in ("小選挙区", "比例復活", "比例単独", "比例")} for n in nums}}
json.dump(report, open(os.path.join(W, "report.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in report.items() if k not in ("missing_kana",)}, ensure_ascii=False, indent=1)[:4000])
