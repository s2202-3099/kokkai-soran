"""派閥の記事の「所属していた国会議員一覧」「その他国政選挙落選・引退者」から、議員ごとの派閥の手がかりを読む。

本人の記事に派閥が書かれていない議員（昭和40年代までに多い）を、派閥の側の一覧から当てるためのもの。
返すのは {本人の記事名: [(派閥, 始まりの年, 終わりの年, 記事名, 一覧の見出し)]}。年は分かるときだけ（なければ None）。

- 解消した派閥の一覧：見出しのない並びはその派閥の議員。「○○へ移籍」の下の議員は、その派閥にいて後に○○へ移った
  （時期は書かれていない）ので、両方を手がかりにする（投票日の年に両方あれば決めない）。
- 続いた派閥の「その他国政選挙落選・引退者」：議員でなくなるまでその派閥にいた人。
  「かつて所属していた人物」（離脱・離党した人）は時期がまちまちなので使わない。
"""
import re

LINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")

# 記事名 → 派閥（faction.py の entity）。解消した派閥
OLD = {"水曜会 (自民党)": "水曜会", "交友クラブ": "交友クラブ", "愛正会": "愛正会", "一新会 (自民党)": "一新会",
       "巽会": "巽会", "春秋会": "春秋会", "周山会": "周山会", "睦政会": "睦政会", "自由革新同友会": "自由革新同友会"}
# 続いた派閥（落選・引退者の一覧だけを使う）
MAIN = {"宏池会": "宏池会", "清和政策研究会": "清和政策研究会", "平成研究会": "平成研究会",
        "番町政策研究所": "番町政策研究所", "志帥会": "志帥会", "近未来政治研究会": "近未来政治研究会"}
# 見出しのリンク先 → 派閥
TARGET = {"木曜クラブ": "木曜クラブ", "春秋会": "春秋会", "番町政策研究所": "番町政策研究所", "交友クラブ": "交友クラブ",
          "自由革新同友会": "自由革新同友会", "宏池会": "宏池会", "清和政策研究会": "清和政策研究会", "巽会": "巽会",
          "政策科学研究所": "政策科学研究所", "睦政会": "睦政会", "一新会 (自民党)": "一新会", "一新会_(自民党)": "一新会",
          "愛正会": "愛正会", "水曜会 (自民党)": "水曜会"}
# 巽会（水田派）は1971年12月に村上派（一陽会）を母体に、船田派・藤山派からの議員を加えて結成（巽会の記事）。
# 見出しは出身を表すので、出身の派閥は1971年まで、巽会は1971年から。一陽会系は1965年の大野派の分裂から村上派
TATSUMI = {"一陽会系": [("巽会", 1965, 1977)], "一新会系": [("一新会", 1965, 1971), ("巽会", 1971, 1977)],
           "愛正会系": [("愛正会", 1960, 1971), ("巽会", 1971, 1977)], "その他": [("巽会", 1971, 1977)]}


def _clean(s):
    s = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{(?:Refnest|Sfn|efn)[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}", "", s)
    return s


def _names(line):
    """「* [[A]]、[[B]]（後に[[C派]]へ移籍）」→ [A, B]。括弧の中のリンクは人ではない。"""
    line = re.sub(r"（[^（）]*(?:（[^（）]*）[^（）]*)*）", "", _clean(line))
    return [m.group(1).strip() for m in LINK.finditer(line)]


def _section(text, head):
    i = text.find(head)
    if i < 0:
        return ""
    lvl = len(re.match(r"=+", head).group(0))
    m = re.search(r"\n={2,%d}[^=]" % lvl, text[i + len(head):])
    return text[i:i + len(head) + m.start()] if m else text[i:]


def extract(pages):
    """pages: {記事名: {"text": ...}}。"""
    out = {}

    def add(name, ent, a, b, art, head):
        out.setdefault(name, [])
        if (ent, a, b, art, head) not in out[name]:
            out[name].append((ent, a, b, art, head))

    for art, ent in OLD.items():
        t = (pages.get(art) or {}).get("text") or ""
        sec = _section(t, "== 所属していた国会議員一覧 ==")
        sub, tgt = "", None
        for ln in sec.split("\n")[1:]:
            h = re.match(r"\s*===\s*(.*?)\s*===\s*$", _clean(ln))
            if h:
                sub = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", h.group(1)).strip()
                lk = LINK.search(h.group(1))
                tgt = TARGET.get(lk.group(1).strip()) if lk and "移籍" in h.group(1) else None
                if "福田派" in h.group(1):      # 「南条グループ分派→福田派」
                    tgt = "清和政策研究会"
                continue
            if not ln.lstrip().startswith("*") or ln.lstrip().startswith("*:"):
                continue
            for nm in _names(ln):
                if ent == "巽会":
                    for e2, a, b in TATSUMI.get(sub, [("巽会", None, None)]):
                        add(nm, e2, a, b, art, sub)
                    if "田中派へ移籍" in ln:
                        add(nm, "木曜クラブ", None, None, art, sub)
                    continue
                add(nm, ent, None, None, art, sub or "所属していた国会議員一覧")
                if tgt and tgt != ent:
                    add(nm, tgt, None, None, art, sub)
                if "田中派へ移籍" in ln and sub != "無派閥":   # 「無派閥」の下の人は、移るまでの無派閥の時期が分からない
                    add(nm, "木曜クラブ", None, None, art, sub)
    for art, ent in MAIN.items():
        t = (pages.get(art) or {}).get("text") or ""
        sec = _section(t, "=== その他国政選挙落選・引退者 ===")
        for ln in sec.split("\n")[1:]:
            if ln.lstrip().startswith("*") and not ln.lstrip().startswith("*:"):
                for nm in _names(ln):
                    add(nm, ent, None, None, art, "その他国政選挙落選・引退者")
    return out
