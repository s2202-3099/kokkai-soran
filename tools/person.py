"""議員の記事から、台帳に入れる基本の事実を取り出す。"""
import re

PREFS = ["北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県", "茨城県", "栃木県", "群馬県", "埼玉県",
         "千葉県", "東京都", "神奈川県", "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県", "静岡県",
         "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県",
         "広島県", "山口県", "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県", "熊本県", "大分県",
         "宮崎県", "鹿児島県", "沖縄県"]


def clean(s):
    s = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", "／", s)
    return re.sub(r"'''?", "", s).strip()


def infobox(t):
    m = re.search(r"\{\{\s*(?:政治家|基礎情報 政治家|Infobox 政治家)", t)
    if not m:
        return ""
    depth, j = 0, m.start()
    while j < len(t):
        if t.startswith("{{", j):
            depth += 1
            j += 2
        elif t.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                return t[m.start():j]
        else:
            j += 1
    return t[m.start():]


def field(ib, name):
    m = re.search(r"^\|\s*" + re.escape(name) + r"\s*=(.*?)(?=^\|\s*[^=\n|]+?\s*=|\Z)", ib, re.M | re.S)
    return m.group(1).strip() if m else ""


def birth(t, ib):
    for pat in (r"生年月日と年齢\|(\d{4})\|(\d{1,2})\|(\d{1,2})", r"死亡年月日と没年齢\|(\d{4})\|(\d{1,2})\|(\d{1,2})",
                r"生年月日\|(\d{4})\|(\d{1,2})\|(\d{1,2})", r"生年月日=(\d{4})/(\d{1,2})/(\d{1,2})"):
        m = re.search(pat, t)
        if m:
            return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}", "記事の生年月日欄"
    lead = t[t.find("\n'''") if "\n'''" in t else 0:][:1500]
    m = re.search(r"(\d{4})年（[^）]{0,12}）?\s*(\d{1,2})月(\d{1,2})日\s*[-‐–－ー]", lead) or \
        re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*[-‐–－]", lead)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}", "記事の冒頭"
    return "", ""


def kana(t, ib):
    k = clean(field(ib, "各国語表記"))
    if k and re.fullmatch(r"[ぁ-ゖー\s　・]+", k):
        return re.sub(r"[\s　]+", " ", k)
    m = re.search(r"'''[^']+'''\s*（([ぁ-ゖー\s　]+)[、，,）]", t)
    return re.sub(r"[\s　]+", " ", m.group(1)).strip() if m else ""


def sex(t):
    pat = r"\[\[Category:(?:[^\]|]*の)?女性(?!学)[^\]|]*\]\]"
    return "f" if re.search(pat, t) else "m"


def birth_pref(ib):
    s = clean(field(ib, "出生地"))
    for p in sorted(PREFS, key=len, reverse=True):
        if p in s:
            return p
    for p in PREFS:
        short = re.sub(r"[都府県]$", "", p)
        if p != "北海道" and short in s:
            return p
    return ""


def election_rows(t):
    """{{選挙歴}} の衆院の行を {回次: (結果, 選挙区)} にする。"""
    out = {}
    m = re.search(r"\{\{選挙歴.*?\n\}\}", t, re.S)
    if not m:
        return out
    for line in m.group().split("\n"):
        c = [x.strip() for x in line.split("|")]
        if len(c) > 4 and c[1] == "衆" and c[3].isdigit():
            out[int(c[3])] = (c[2], clean(c[4]))
    return out


def _date(s):
    s = clean(re.sub(r"<ref[^>]*/>|<ref.*?</ref>|<!--.*?-->", "", s, flags=re.S))
    if "現職" in s:
        return "現職"
    m = re.search(r"(\d{4})年\s*(\d{1,2})月(?:\s*(\d{1,2})日)?", s)
    if not m:
        return ""
    return f"{int(m[1]):04d}-{int(m[2]):02d}" + (f"-{int(m[3]):02d}" if m[3] else "")


def house_tenure(ib, house="参議院議員"):
    """情報欄で、その院の議員の行の直後にある就任日・退任日の組を拾う（番号のずれがあるため並び順で取る）。"""
    out, on = [], False
    start = None
    for line in ib.split("\n"):
        m = re.match(r"\|\s*([^=|]+?)\s*=(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if re.match(r"(?:職名|その他職歴)\d*$", key):
            on = bool(re.search(re.escape(house) + r"(?!会長|副会長|団|総会)", val))
            continue
        if on and re.match(r"就任日\d*$", key):
            start = _date(val.split("<hr>")[-1])
        elif on and re.match(r"退任日\d*$", key):
            out.append((start, _date(val)))
            on = False
    return out


def extract(rec):
    t = rec["text"]
    ib = infobox(t)
    b, bsrc = birth(t, ib)
    return {"title": rec["title"], "pageid": rec["pageid"], "qid": rec.get("qid") or "", "revid": rec.get("revid"),
            "birth": b, "birth_src": bsrc, "kana": kana(t, ib), "sex": sex(t), "birth_pref": birth_pref(ib),
            "elections": election_rows(t), "san_tenure": house_tenure(ib), "disambiguation": rec.get("disambiguation", False),
            "length": rec.get("length")}
