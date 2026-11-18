"""貴族院議員の記事（分類から集めたもの）を読み、投票日に在職していた議員の名簿 kizokuin.json を作る。

使い方: PYTHONPATH=tools python3 tools/run_kizokuin.py <貴族院の作業フォルダ> <参院の作業フォルダ> 日付 [日付 ...]
- 作業フォルダの arts.json（記事）を kizokuin.parse で読む。
- 終わりの日が書かれていない在職は、種別の決まりで閉じる（推定）：
  互選の議員（伯子男爵・多額納税者・帝国学士院会員）は次の改選の前日まで、終身の議員（皇族・公侯爵・勅選）は
  死去か貴族院の廃止まで。皇族議員は1946年5月23日に全員が辞任、朝鮮・台湾勅選議員は1946年7月4日に資格消滅。
- 読み取りで決まらないもの・読み違えるものは FIX（本人の記事を読んで確かめたもの）で直す。
- 最初の日付から貴族院の廃止（1947年5月2日）までの間に在職していた人だけを書き出し、その人たちの記事を person_articles_kz.json に入れる。
"""
import json
import os
import re
import sys

import kizokuin

W, W2, DAYS = sys.argv[1], sys.argv[2], sys.argv[3:]
ABOL = kizokuin.ABOLISHED
GOSEN = [f"{y}-07-09" for y in (1897, 1904, 1911, 1918, 1925, 1932, 1939)] + [ABOL]   # 伯子男爵議員の任期の終わり
TAGAKU = [f"{y}-09-28" for y in (1897, 1904, 1911, 1918, 1925, 1932, 1939)] + [ABOL]  # 多額納税者・学士院会員議員
KOZOKU_END = "1946-05-23"      # 皇族議員が全員辞任した日
GAICHI = ("1945-04-03", "1946-07-04")   # 朝鮮・台湾勅選議員の制度の始まりと終わり
KAIHA = ["研究会", "公正会", "交友倶楽部", "同和会", "同成会", "火曜会", "無所属倶楽部"]

# 本人の記事を読んで確かめた在職（読み取りでは決まらないもの）：記事名 → {kind, pref, spans:[(始まり, 終わり, 終わりの理由)], note}
FIX = {
    "堀田正養": {"spans": [("1890-07-10", "1911-05-09", "死去")],
                 "note": "本人の記事（1890年7月10日に選ばれ「連続して3期にわたって議員に選ばれた」。在職中に死去の分類）"},
    "大谷五平": {"kind": "多額納税者議員", "pref": "福島県", "spans": [("1939-09-29", "1946-04-23", "辞職")],
                 "note": "本人の記事「1939年9月29日〜1946年4月23日には貴族院議員を務め」"},
    "渡邉昭": {"spans": [("1943-06-24", "1946-04-13", "辞職")], "note": "本人の記事の年譜（1943年6月24日互選、1946年4月13日辞職）"},
    "徳川義親": {"spans": [("1911-10-04", "1927-04-22", "辞職"), ("1931-12-21", "1946-06-05", "辞職")],
                 "note": "本人の記事（1911年に満25歳で就任、1927年辞任、1931年復帰、1946年6月5日辞職）"},
    "筑波藤麿": {"kind": "侯爵議員", "spans": [("1935-02-24", ABOL, "貴族院廃止")],
                 "note": "本人の記事（皇族議員を経て臣籍降下。1935年2月24日から侯爵議員）"},
    "井上篤太郎": {"spans": [("1946-08-14", ABOL, "貴族院廃止")], "note": "本人の記事"},
    "大木操": {"spans": [("1945-10-05", ABOL, "貴族院廃止")], "note": "本人の記事"},
    "安倍能成": {"spans": [("1945-12-19", ABOL, "貴族院廃止")], "note": "本人の記事（12月19日〜1947年5月2日）"},
    "小林次郎": {"spans": [("1945-11-24", ABOL, "貴族院廃止")], "note": "本人の記事（貴族院書記官長在任のまま1945年11月24日に勅任、1947年5月2日退任）"},
    "遠藤柳作": {"spans": [("1936-04-28", "1946-02-16", "辞職")], "note": "本人の記事の年譜"},
    "宮澤俊義": {"spans": [("1946-06-08", ABOL, "貴族院廃止")], "note": "本人の記事（議員勅選、6月8日）"},
    "我妻榮": {"spans": [("1946-06-19", ABOL, "貴族院廃止")], "note": "本人の記事の年譜（1946年6月19日）"},
    "長岡半太郎": {"spans": [("1934", ABOL, "貴族院廃止")], "note": "本人の記事（帝国学士院会員議員、1934〜1947年。就任の月日は記事にない）"},
    "中山太一": {"spans": [("1939-09-29", ABOL, "貴族院廃止")], "note": "本人の記事"},
    "塩田団平": {"spans": [("1939-09-29", ABOL, "貴族院廃止")], "note": "本人の記事"},
    "河西豊太郎": {"spans": [("1941-10-21", ABOL, "貴族院廃止")], "note": "本人の記事"},
    "長島銀蔵": {"spans": [("1946-05-18", ABOL, "貴族院廃止")], "note": "本人の記事"},
    "徳彦王": {"kind": "皇族議員", "spans": [("1942-11-19", "1943-06-07", "臣籍降下")], "note": "本人の記事（1943年6月7日に臣籍降下、龍田伯爵家）"},
    "邦英王": {"kind": "皇族議員", "spans": [("1930-05-15", "1931-04-04", "臣籍降下")], "note": "本人の記事（東伏見伯爵家を創設）"},
    "家彦王": {"kind": "皇族議員", "spans": [("1940-03-17", "1942-10-05", "臣籍降下")], "note": "本人の記事（宇治伯爵家）"},
    "彰常王": {"kind": "皇族議員", "spans": [("1940-05-13", "1940-10-25", "臣籍降下")], "note": "本人の記事（粟田侯爵家）"},
    "鏑木忠正": {"spans": [("1946", ABOL, "貴族院廃止")], "note": "本人の記事（1946年に多額納税者議員に選出。月日は記事にない）"},
    "長岡隆一郎": {"spans": [("1929-07-01", "1946-03-18", "辞職")], "note": "本人の記事（1929年7月1日勅選、1946年3月18日辞任）"},
    "秩父宮雍仁親王": {"spans": [("1922-06-25", KOZOKU_END, "辞職")], "note": "本人の記事（成年の日に皇族議員、1946年5月23日辞職）"},
}


GOSEN_YEARS = {x[:4] for x in GOSEN[:-1]} | {"1890"}
TAGAKU_YEARS = {x[:4] for x in TAGAKU[:-1]} | {"1890"}


def snap_start(kind, s):
    """年だけの始まりで、その年が互選の年なら互選の日にする（伯子男爵は7月10日、多額納税者・学士院会員は9月29日）。"""
    if len(s) == 4 and kind in ("伯爵議員", "子爵議員", "男爵議員") and s in GOSEN_YEARS:
        return s + "-07-10"
    if len(s) == 4 and kind in ("多額納税者議員", "帝国学士院会員議員") and s in TAGAKU_YEARS:
        return s + "-09-29"
    return s


def pad_start(s):
    """年・月までの始まりは、その年・月の終わりに始まったものとして比べる（その年のうちの投票日には数えない）。"""
    return s if len(s) >= 10 else s + "-99"


def close(kind, s, e, death):
    """終わりの日のない在職を種別の決まりで閉じる。(終わり, 理由, 推定かどうか)"""
    if e:
        if len(e) == 7 and e == ABOL[:7]:
            e = ABOL
        return e, "", False
    if kind in ("伯爵議員", "子爵議員", "男爵議員"):
        e = next(x for x in GOSEN if x >= pad_start(s))
    elif kind in ("多額納税者議員", "帝国学士院会員議員"):
        e = next(x for x in TAGAKU if x >= pad_start(s))
    elif kind == "皇族議員":
        e = KOZOKU_END
    elif kind == "朝鮮・台湾勅選議員":
        e = GAICHI[1]
    else:
        e = ABOL
    if death and death < e:
        return death, "死去", True
    return e, {ABOL: "貴族院廃止", KOZOKU_END: "辞職", GAICHI[1]: "資格消滅"}.get(e, "任期満了"), True


def kaiha(text):
    """本人の記事に書かれた院内会派（所属・属しの語の近くの会派名）。"""
    body = kizokuin.strip(text[kizokuin.lead_pos(text):])
    found = []
    for m in re.finditer("|".join(KAIHA), body):
        ctx = body[max(0, m.start() - 12):m.end() + 14]
        if re.search(r"所属|属し|属す|入会|に属|加入|会員", ctx) and m.group(0) not in found:
            found.append(m.group(0))
    return found


def reason_of(text, e, death):
    if e == ABOL:
        return "貴族院廃止"
    if death and e == death:
        return "死去"
    body = kizokuin.strip(text)
    y, mo, d = (e.split("-") + ["", ""])[:3]
    pat = rf"{int(mo)}月{int(d)}日" if d else (rf"{int(mo)}月" if mo else y + "年")
    for m in re.finditer(pat, body):
        seg = body[m.start():m.end() + 50]
        if re.search(r"臣籍降下|皇籍離脱", body[max(0, m.start() - 60):m.end() + 60]):
            return "臣籍降下"
        if "資格" in seg and "消滅" in seg:
            return "資格消滅"
        if "失職" in seg:
            return "失職"
        if re.search(r"死去|薨去|逝去", seg):
            return "死去"
        if re.search(r"辞職|辞任|辞し|免", seg):
            return "辞職"
    if e in GOSEN or e in TAGAKU:
        return "任期満了"   # 「1939年9月28日まで1期在任」
    return "退任"


arts = json.load(open(os.path.join(W, "arts.json")))
by_page, names = {}, {}
for t, v in arts.items():
    if not v or t.startswith(("Template", "Category")) or "議長" in t and "(" in t:
        continue
    names.setdefault(v["pageid"], set()).update((t, v["title"]))   # 転送元の名前（皇族時代の名など）でも FIX を引けるように
    if v["pageid"] not in by_page or t == v["title"]:
        by_page[v["pageid"]] = v
out, keep, problems = [], {}, []
for v in by_page.values():
    t = v["title"]
    r = kizokuin.parse(t, v["text"])
    fx = next((FIX[x] for x in names[v["pageid"]] if x in FIX), {})
    ks = r["kinds"]
    body = kizokuin.strip(v["text"])
    if re.search(r"朝鮮・台湾勅選議員|朝鮮勅選議員|台湾勅選議員", body) and not ({"勅選議員"} & set(ks)):
        ks = ["朝鮮・台湾勅選議員"]
    if not ks:
        m = re.search(r"貴族院[^。、]{0,8}?(皇族|公爵|侯爵|伯爵|子爵|男爵|勅選|多額納税者|帝国学士院会員)", body)
        if m:
            ks = [m.group(1) + "議員"]
        elif re.search(r"皇族議員", body):
            ks = ["皇族議員"]
    spans = []
    if fx.get("spans"):
        kind = fx.get("kind") or (ks[-1] if ks else "")
        spans = [(s, e, why, False, kind) for s, e, why in fx["spans"]]
    else:
        raw = [(s, e, area) for s, e, area in r["spans"] if s and s != ABOL and s <= ABOL]
        for i, (s, e, area) in enumerate(raw):
            # 種別：情報欄の選挙区欄にあればそれ。なければ分類。皇族議員と爵位議員の両方がある人は、先の在職が皇族議員
            kind = next((k for k in kizokuin.KINDS if k[:-2] in area), None) or fx.get("kind")
            if not kind:
                if "皇族議員" in ks and len(ks) > 1:
                    # 在職が一つだけなら、記事名が「○○王」「○○親王」の人は皇族議員、臣籍降下後の名前の人は爵位の議員
                    first_is_kozoku = len(raw) > 1 or re.search(r"(?:王|親王)$", t)
                    kind = "皇族議員" if i == 0 and first_is_kozoku else next(k for k in ks if k != "皇族議員")
                else:
                    kind = ks[-1] if ks else ""
            if kind == "朝鮮・台湾勅選議員":
                s, e = GAICHI[0], e or ""
            if e and len(e) >= 7 and e[:7] == ABOL[:7]:
                e = ABOL
            if e and r["death"] and r["death"] < e[:10].ljust(10, "9"):
                e = r["death"]   # 議員の資格だけが残っていても、亡くなった日まで
            s = snap_start(kind, s)
            e2, why, est = close(kind, s, e, r["death"])
            if e2 < s[:len(e2)] or e2 == s:
                continue   # 終わりが始まりより前、または長さのない在職（「1939年7月9日任期満了」を始まりと読んだものなど）
            why = why or reason_of(v["text"], e2, r["death"])
            if kind == "皇族議員" and e2 == KOZOKU_END:
                why = "辞職"   # 1946年5月23日、在職していた皇族議員の全員が辞任
            spans.append((s, e2, why, est, kind))
    # 前の在職の中に始まりが入っている期間は同じ在職の言い換え（「1947年、廃止まで在任」など）なので捨てる
    spans.sort(key=lambda x: x[0])
    kept = []
    for sp in spans:
        if kept and kept[-1][0][:len(sp[0])] <= sp[0] <= kept[-1][1][:len(sp[0])]:
            continue
        kept.append(sp)
    spans = kept
    # 最初の日付から貴族院の廃止までの間に在職していた期間（投票日の間に就任して退任した人も入れる）
    hit = [sp for sp in spans if sp[0] <= ABOL and sp[1] >= min(DAYS)[:len(sp[1])]]
    if not hit:
        continue
    if not hit[0][4]:
        problems.append(f"種別が分からない：{t}")
    kh = kaiha(v["text"])
    out.append({"title": t, "kinds": ks, "pref": fx.get("pref") or r["pref"], "death": r["death"], "src": "fix" if fx.get("spans") else r["src"],
                "note": fx.get("note", ""), "kaiha": kh,
                "spans": [{"start": s, "end": e, "reason": why, "est": est, "kind": k} for s, e, why, est, k in hit]})
    keep[t] = v
json.dump(out, open(os.path.join(W2, "kizokuin.json"), "w"), ensure_ascii=False, indent=0)
json.dump(keep, open(os.path.join(W2, "person_articles_kz.json"), "w"), ensure_ascii=False)
import collections
for D in DAYS:
    c = collections.Counter(sp["kind"] for m in out for sp in m["spans"] if pad_start(sp["start"]) <= D and sp["end"] >= D[:len(sp["end"])])
    print(D, sum(c.values()), dict(c))
print("推定の終わり", sum(1 for m in out for sp in m["spans"] if sp["est"]), "会派なし", sum(1 for m in out if not m["kaiha"]))
for p in problems:
    print(p)
