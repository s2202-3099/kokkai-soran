"""「その時点の名簿」から、議員ごとの派閥を拾う。

- 自民党総裁選の記事の推薦人一覧（「[[氏名]]（町村派）」の形で、推薦人ごとに派閥が書かれている）
- 派閥の記事の、時点のはっきりした構成の表（「志帥会結成時の構成」「2008年4月の構成」「解散時の構成」など）
返り値は [{date, article, name, label, kind, title}]。label は派閥の呼び名か、構成の表なら派閥の名前。
"""
import re

import wtable

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
PAIR = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]\s*[　 ]*[（(]((?:\[\[[^\]]*\]\]|[^）)\n])+?)[）)]")

# 総裁選の投票日
SOUSAI = {2006: "2006-09-20", 2007: "2007-09-23", 2008: "2008-09-22", 2009: "2009-09-28", 2012: "2012-09-26",
          2015: "2015-09-08", 2018: "2018-09-20", 2020: "2020-09-14", 2021: "2021-09-29", 2024: "2024-09-27",
          2025: "2025-10-04"}
# 派閥の記事の、時点のはっきりした構成の節： (記事, 見出しの手がかり, 日付, 派閥)
ROSTERS = [("政策科学研究所", "志帥会結成時の構成", "1999-03-18", "政策科学研究所"),
           ("志帥会", "発足当初の構成", "1999-03-18", "志帥会"),
           ("新財政研究会", "2008年4月の構成", "2008-04-01", "宏池会"),
           ("番町政策研究所", "解散時の構成", "2017-06-30", "番町政策研究所"),
           ("新しい波 (派閥)", "解散時の構成", "2009-11-01", "新しい波")]


def sousai(text, year):
    out = []
    for _, tb in wtable.tables(text):
        if "推薦人" not in tb:
            continue
        for m in PAIR.finditer(tb):
            art, shown, lab = m.group(1).strip(), (m.group(2) or m.group(1)).strip(), m.group(3)
            lab = LINK.sub(lambda x: x.group(2) or x.group(1), lab).strip()
            if re.match(r"(?:ファイル|File|画像)\s*:", art) or re.search(r"\d", lab):
                continue
            out.append({"date": SOUSAI[year], "article": art.replace("_", " "), "name": shown, "label": lab,
                        "kind": "総裁選の推薦人", "title": f"{year}年自由民主党総裁選挙"})
    return out


def roster(text, head, date, entity, title):
    m = re.search(r"^=+\s*[^=\n]*" + re.escape(head) + r"[^=\n]*=+\s*$", text, re.M)
    if not m:
        return []
    lvl = len(re.match(r"=+", m.group()).group())
    nxt = re.search(r"^={1,%d}[^=\n]+={1,%d}\s*$" % (lvl, lvl), text[m.end():], re.M)
    sec = text[m.end(): m.end() + (nxt.start() if nxt else len(text))]
    out = []
    for _, tb in wtable.tables(sec):
        for row in wtable.grid(tb):
            for _h, c in row:
                lk = LINK.search(c)
                if not lk or re.search(r"区|ブロック|選挙|ファイル|File|画像", lk.group(1)):
                    continue
                out.append({"date": date, "article": lk.group(1).strip().replace("_", " "),
                            "name": (lk.group(2) or lk.group(1)).strip(), "label": entity, "kind": "派閥の構成",
                            "title": f"{title}（{head}）"})
    # 箇条書きの名簿（* [[原健三郎]]（20回、…））と、役員欄（*会長 - [[古賀誠]]）
    for line in sec.split("\n"):
        mm = re.match(r"^\*\s*'*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", line)
        if mm and not re.search(r"区|ブロック|選挙", mm.group(1)):
            out.append({"date": date, "article": mm.group(1).strip().replace("_", " "),
                        "name": (mm.group(2) or mm.group(1)).strip(), "label": entity, "kind": "派閥の構成",
                        "title": f"{title}（{head}）"})
            continue
        if line.startswith("*") and " - " in line:
            for lk in LINK.finditer(line.split(" - ", 1)[1]):
                out.append({"date": date, "article": lk.group(1).strip().replace("_", " "),
                            "name": (lk.group(2) or lk.group(1)).strip(), "label": entity, "kind": "派閥の構成",
                            "title": f"{title}（{head}）"})
    return out


def collect(src):
    out = []
    for y in SOUSAI:
        rec = src.get(f"{y}年自由民主党総裁選挙")
        if rec:
            for r in sousai(rec["text"], y):
                r["revid"], r["page"] = rec["revid"], rec["title"]
                out.append(r)
    for art, head, date, entity in ROSTERS:
        rec = src.get(art)
        if rec:
            for r in roster(rec["text"], head, date, entity, rec["title"]):
                r["revid"], r["page"] = rec["revid"], rec["title"]
                out.append(r)
    return out


EXIT_ARTICLES = {"清和政策研究会": "清和政策研究会", "平成研究会": "平成研究会", "宏池会": "宏池会", "志帥会": "志帥会",
                 "近未来政治研究会": "近未来政治研究会", "番町政策研究所": "番町政策研究所", "志公会": "志公会系",
                 "有隣会": "有隣会", "水月会": "水月会"}


def exits(src):
    """派閥の記事の「その他国政選挙落選・引退者」（議員でなくなった時点でその派閥にいた人）。[{article, name, entity, page, revid}]"""
    out = []
    for art, ent in EXIT_ARTICLES.items():
        rec = src.get(art)
        if not rec:
            continue
        t = rec["text"]
        m = re.search(r"^=+\s*その他国政選挙落選・引退者\s*=+\s*$", t, re.M)
        if not m:
            continue
        nxt = re.search(r"^=+[^=\n]+=+\s*$", t[m.end():], re.M)
        sec = t[m.end(): m.end() + (nxt.start() if nxt else len(t))]
        for mm in re.finditer(r"^\*\s*'*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'*\s*[※◆●†]", sec, re.M):
            out.append({"article": mm.group(1).strip().replace("_", " "), "name": (mm.group(2) or mm.group(1)).strip(),
                        "entity": ent, "page": rec["title"], "revid": rec["revid"]})
    return out
