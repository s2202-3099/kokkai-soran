"""人物のよみ・出生地の空欄を、本人の記事をいま取り直して埋める。よみの読み違いも洗い出す。

使い方: PYTHONPATH=tools python3 tools/fill_persons.py data <作業フォルダ> [--all]

build.py は作業フォルダにためた記事から person.extract で読む。この道具は、作業フォルダがなくても
台帳（data/persons.csv）だけから、同じ読み取り（person.kana、person._place）で空欄を埋めるためのもの。
- 対象：よみか出生地が空の人。--all を付けると全員の記事を取り、すでにあるよみと新しい読み取りの食い違いを
  作業フォルダの kana_diff.json に書き出す（台帳は変えない。確かめてから KANA_FIX に入れる）。
- 記事は50件ずつ取り、作業フォルダの persons_arts.json にためる。記事名が別の記事に転送されるもの
  （人物の記事がなく、家や事柄の記事に向いているもの）は使わない。
- よみ：姓と名の二つに分かれたものだけ。名前に仮名があるとき（「越原はる」）は、よみの同じところが同じ仮名であるものだけ。
- 出生地：根拠（出生地欄・本文（生まれ）・出身）を birth_pref_basis に入れる。
- すでに入っている値は変えない（KANA_FIX に挙げたよみの直しを除く）。
"""
import csv
import json
import os
import re
import sys

import person
import wiki

D, W = sys.argv[1], sys.argv[2]
ALL = "--all" in sys.argv
os.makedirs(W, exist_ok=True)

# すでに入っているよみの直し（--all の食い違いの一覧から、本人の記事の冒頭を読んで確かめたもの）：記事名 → (今のよみ, 直したよみ)
KANA_FIX = {
    # 空白のないもの、本名・旧名・別名や号の断片が入っていたもの。代数の付く3人（澁澤金蔵・片倉兼太郎・伊藤伝七）は代数を外す
    "木村義雄 (香川県の政治家)": ("きむらよしお", "きむら よしお"),
    "菅原喜重郎": ("すがわら きじゅうろう", "すがはら きじゅうろう"),
    "西村章三": ("にしむらしょうぞう", "にしむら しょうぞう"),
    "菅野志桜里": ("やまお しおり", "かんの しおり"),
    "角田義一": ("つのだ きいち", "つのだ ぎいち"),
    "北川イッセイ": ("きたがわ かずなり", "きたがわ いっせい"),
    "市井紗耶香": ("わたなべ さやか", "いちい さやか"),
    "白川容子": ("しらかわようこ", "しらかわ ようこ"),
    "山口淑子": ("おおたか よしこ", "やまぐち よしこ"),
    "西村尚治": ("にしむらしょうじ", "にしむら しょうじ"),
    "逢沢英雄": ("あいざわ ひでお", "あいさわ ひでお"),
    "久次米健太郎": ("くじめけんたろう", "くじめ けんたろう"),
    "望月優子": ("すずき みえこ", "もちづき ゆうこ"),
    "八木一男": ("やぎかずお", "やぎ かずお"),
    "西村関一": ("にしむら かんいち", "にしむら せきかづ"),
    "西郷吉之助": ("さいごうきちのすけ", "さいごう きちのすけ"),
    "鹿島守之助": ("ながとみ", "かじま もりのすけ"),
    "草葉隆圓": ("くさばりゅうえん", "くさば りゅうえん"),
    "有馬英二": ("ありま えいじ", "ありま ひでじ"),
    "荒畑寒村": ("あらはた かつぞう", "あらはた かんそん"),
    "澁澤金蔵 (3代)": ("さんだい しぶさわ きんぞう", "しぶさわ きんぞう"),
    "片倉兼太郎 (3代目)": ("さんだいめ かたくら かねたろう", "かたくら かねたろう"),
    "伊豆富人": ("いずとみと", "いず とみと"),
    "樋口龍峡": ("ひぐち ひでお", "ひぐち りゅうきょう"),
    "中林友信": ("なかばやし とものぶ", "なかばやし ゆうしん"),
    "岡田温 (農業技師)": ("おかだゆたか", "おかだ ゆたか"),
    "伊藤伝七 (10代目)": ("じゅうだいめ いとう でんしち", "いとう でんしち"),
    "加藤重三郎": ("かとう じゅうざぶろう", "かとう じゅうさぶろう"),
    "漆昌巌": ("うるし", "うるし しょうがん"),
    "日比野寛": ("おだ", "ひびの ゆたか"),
    "上村耕作": ("すてぎく", "うえむら こうさく"),
    "東海散士": ("しば しろう", "とうかい さんし"),
    "一木喜徳郎": ("おかだ きゅうへい", "いちき きとくろう"),
    "浜口吉右衛門": ("ようしょ", "はまぐち きちえもん"),
    "南郷茂光": ("あさづ とみのすけ", "なんごう しげみつ"),
    "小村壽太郎": ("こむら こうへい", "こむら じゅたろう"),
    "沢原俊雄": ("よしみ", "さわはら としお"),
    "由利公正": ("みつおか はちろう", "ゆり きみまさ"),
    "坂口平兵衛 (初代)": ("しょだい さかぐち へいべえ", "さかぐち へいべえ"),
    "松本良順": ("まつもと じゅん", "まつもと りょうじゅん"),
    "山田喜之助": ("てんなん", "やまだ きのすけ"),
    "毛利元徳": ("ひろあつ", "もうり もとのり"),
    "久邇宮朝彦親王": ("なかがわのみや", "くにのみや あさひこしんのう"),
    "木内キヤウ": ("", "きうち きょう"),
    # 読み取りで読めない書き方（{{読み仮名}} のテンプレート、変体仮名、読みが二通りのものは最初の読み、姓だけ・名だけに注が挟まるもの）を記事の冒頭で確かめて入れたもの
    "山口哲夫": ("", "やまぐち てつお"),
    "濱尾四郎": ("", "はまお しろう"),
    "松田三徳": ("", "まつだ みのり"),
    "石井謹吾": ("", "いしい きんご"),
    "西周 (啓蒙家)": ("", "にし あまね"),
    "西郷従道": ("", "さいごう じゅうどう"),
    "はたともこ": ("", "はた ともこ"),
    "いずみたく": ("", "いずみ たく"),
    "椎井康雄": ("", "しい やすお"),
    "小杉イ子": ("", "こすぎ いね"),
    "山下ツ子": ("", "やました つね"),
    "矢後嘉蔵": ("", "やご かぞう"),
    "四王天延孝": ("", "しおうでん のぶたか"),
    "仲田伝之じょう": ("", "なかた でんのじょう"),
    "宮島幹之助": ("", "みやじま みきのすけ"),
    "渡辺新太郎 (衆議院議員)": ("", "わたなべ しんたろう"),
    "保阪潤治": ("", "ほさか じゅんじ"),
    "千種有梁": ("", "ちぐさ ありはる"),
    "竹内綱": ("", "たけうち つな"),
    "阿部興人": ("", "あべ おきと"),
    "江崎権兵衛": ("", "えさき ごんべえ"),
    "福羽美静": ("", "ふくば びせい"),
    "清水宗徳 (政治家)": ("", "しみず そうとく"),
    "柴立芳文": ("", "しばたて よしふみ"),   # 名前の「キヤウ」は歴史的仮名遣い。記事の冒頭は「きうち きょう」
}

with open(os.path.join(D, "persons.csv"), encoding="utf-8") as f:
    rdr = csv.DictReader(f)
    cols = rdr.fieldnames
    persons = list(rdr)

todo = [r for r in persons if r["jawiki_title"] and (ALL or not r["name_kana"] or not r["birth_pref"])]
cache_path = os.path.join(W, "persons_arts.json")
arts = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
need = sorted({r["jawiki_title"] for r in todo} - set(arts))
for i in range(0, len(need), 50):
    batch = need[i:i + 50]
    res = wiki.call({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                     "titles": "|".join(batch), "redirects": "1"})
    norm = {x["to"]: x["from"] for x in res["query"].get("normalized", [])}
    redir = {x["to"]: x["from"] for x in res["query"].get("redirects", [])}
    for pg in res["query"]["pages"]:
        t = pg["title"]
        if t in redir:
            arts[norm.get(redir[t], redir[t])] = {"redirect": t, "text": ""}
            continue
        arts[norm.get(t, t)] = {"text": pg.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("content", "")}
    print("記事", min(i + 50, len(need)), "/", len(need), flush=True)
    if i % 1000 == 0 or i + 50 >= len(need):
        json.dump(arts, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)


def kana_ok(name, k):
    """よみが名前の仮名と合うか（「越原はる」に「こしはら はるこ」は合わない）。"""
    parts = k.split(" ")
    if len(parts) != 2 or not all(parts):
        return False
    hira = person._hira(name)
    head = re.match(r"[ぁ-ゖー]+", hira)
    tail = re.search(r"[ぁ-ゖー]+$", hira)
    if head and not parts[0].startswith(head.group(0)) and not k.replace(" ", "").startswith(head.group(0)):
        return False
    if tail and not parts[1].endswith(tail.group(0)):
        return False
    return True


filled = {"kana": [], "birth": [], "fixed": []}
skipped = {"redirect": [], "kana_mismatch": []}
diff = []
for r in persons:
    a = arts.get(r["jawiki_title"])
    if not a:
        continue
    if a.get("redirect"):
        if not r["name_kana"] or not r["birth_pref"]:
            skipped["redirect"].append((r["name"], r["jawiki_title"], a["redirect"]))
        continue
    t = a["text"]
    ib = person.infobox(t)
    k = person.kana(t, ib)
    if r["jawiki_title"] in KANA_FIX:
        old, new = KANA_FIX[r["jawiki_title"]]
        if r["name_kana"] == old:
            r["name_kana"] = new
            filled["fixed"].append((r["name"], old, new))
    elif not r["name_kana"]:
        if k and kana_ok(r["name"], k):
            r["name_kana"] = k
            filled["kana"].append((r["name"], k))
        elif k:
            skipped["kana_mismatch"].append((r["name"], k))
    elif ALL:
        k2 = person.kana_lead(t)
        if k2 and k2 != r["name_kana"]:
            diff.append({"person_id": r["person_id"], "name": r["name"], "title": r["jawiki_title"], "now": r["name_kana"], "lead": k2})
    if not r["birth_pref"]:
        x = person._place(t, ib)
        if x["birth_pref"]:
            r["birth_pref"], r["birth_pref_basis"] = x["birth_pref"], x["birth_pref_basis"]
            filled["birth"].append((r["name"], x["birth_pref"], x["birth_pref_basis"]))

with open(os.path.join(D, "persons.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(persons)
if ALL:
    json.dump(diff, open(os.path.join(W, "kana_diff.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({**filled, **skipped}, open(os.path.join(W, "fill_persons_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("よみを埋めた", len(filled["kana"]), "直した", len(filled["fixed"]), "出生地を埋めた", len(filled["birth"]),
      "転送で使わない", len(skipped["redirect"]), "よみが名前と合わない", len(skipped["kana_mismatch"]),
      "よみの食い違い（--all）", len(diff))
print("残り よみ", sum(1 for r in persons if not r["name_kana"]), "出生地", sum(1 for r in persons if not r["birth_pref"]))
