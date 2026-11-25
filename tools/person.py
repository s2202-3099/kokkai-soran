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
    # {{死亡年月日と没年齢|生年|月|日|没年|月|日}}。生没を逆に書いた記事（小野重行氏）もあるので、早いほうを生年月日とする
    m = re.search(r"死亡年月日と没年齢\|(\d{4})\|(\d{1,2})\|(\d{1,2})\|(\d{4})\|(\d{1,2})\|(\d{1,2})", t)
    if m and not re.search(r"生年月日と年齢\|", t):
        d1 = f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
        d2 = f"{int(m[4]):04d}-{int(m[5]):02d}-{int(m[6]):02d}"
        return min(d1, d2), "記事の生年月日欄"
    for pat in (r"生年月日と年齢\|(\d{4})\|(\d{1,2})\|(\d{1,2})", r"死亡年月日と没年齢\|(\d{4})\|(\d{1,2})\|(\d{1,2})",
                r"生年月日\|(\d{4})\|(\d{1,2})\|(\d{1,2})", r"生年月日=(\d{4})/(\d{1,2})/(\d{1,2})",
                r"選挙歴\|生年月日=(\d{4})年(\d{1,2})月(\d{1,2})日"):
        m = re.search(pat, t)
        if m:
            return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}", "記事の生年月日欄"
    # 情報欄の「生年月日 = [[1913年]][[2月15日]]」（テンプレートを使わない書き方）
    m = re.search(r"\|\s*生年月日\s*=\s*(?:\[\[)?(\d{4})年(?:\]\])?(?:（[^）]{0,12}）)?\s*(?:\[\[)?(\d{1,2})月(\d{1,2})日", t)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}", "記事の生年月日欄"
    # 冒頭の一文を平らにして読む：出典・テンプレート・リンクを外し、「明治3年10月4日（1870年10月28日）」の和暦を落とす
    import kizokuin as _kz
    lead2 = _kz.strip(t[_kz.lead_pos(t):][:1200])
    lead2 = re.sub(r"\{\{[^{}]*\}\}", "", lead2)
    lead2 = re.sub(r"(?:明治|大正|昭和|慶応|慶應|文化|享和|寛政|元治|文久|万延|安政|嘉永|弘化|天保|文政)\s*(?:\d+|元)\s*年\s*\d{1,2}月\s*\d{1,2}日\s*[（〈(]\s*(\d{4}年\s*\d{1,2}月\s*\d{1,2}日)\s*[）〉)]", r"\1", lead2)
    lead2 = re.sub(r"[〈（(〔][^（）()〈〉〔〕\-‐–－―ー〜~]{0,40}[）)〉〕]", "", lead2)
    m = re.search(r"^'''[^']+'''[^（(。、]{0,20}[（(][^）)]{0,60}?(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*[-‐–－ー―〜~]", lead2)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}", "記事の冒頭"
    if re.search(r"^'''[^']+'''[^（(。、]{0,20}[（(][^）)]{0,60}?(?:\d{4}|(?:明治|大正|昭和|慶応|慶應|文化|享和|寛政|元治|文久|万延|安政|嘉永|弘化|天保|文政)\s*(?:\d+|元))年(?:\s*\d{1,2}月)?\s*[-‐–－ー―〜~]", lead2):
        return "", ""   # 冒頭の生年が年・月までしかない（「弘化元年12月 - 」も。後ろの別の日付を生年月日に取らない）
    i_ = t.find("\n'''") if "\n'''" in t else t.find("}}'''")
    lead = t[max(i_, 0):][:1500]
    lead = re.split(r"\n==", lead)[0]   # 冒頭の段落だけ（「== 栄典 ==」の日付を生年月日に取らない）
    lead = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", lead, flags=re.S)
    lead = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", lead)
    m = re.search(r"(\d{4})年(?:（[^）]{0,12}）|〈[^〉]{0,12}〉)?\s*(\d{1,2})月(\d{1,2})日\s*[-‐–－ー]", lead) or \
        re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s*[-‐–－]", lead)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}", "記事の冒頭"
    return "", ""


def _kana_first(t, ib):
    k = clean(field(ib, "各国語表記"))
    if k and re.fullmatch(r"[ぁ-ゖー\s　・]+", k):
        return re.sub(r"[\s　]+", " ", k)
    m = re.search(r"'''[^']+'''\s*（([ぁ-ゖー\s　]+)[、，,）]", t)
    if m:
        return re.sub(r"[\s　]+", " ", m.group(1)).strip()
    # 出典・注のテンプレートを外した冒頭で読む（「（かんどう<ref>…</ref> さいいち / しんどう…」「（國、はら くに、」「（さかい たかよし{{R|…}} / けいぎ」）
    i = t.find("'''")
    lead = t[max(i, 0):max(i, 0) + 2500]
    lead = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|\{\{(?:R|r|sfn|Sfn|efn|Refnest|refnest)\|[^{}]*\}\}", "", lead, flags=re.S)
    m = re.search(r"'''[^']+'''\s*（(?:[^、（）ぁ-ゖ]{1,8}、)?\s*([ぁ-ゖー\s　/／]+?)\s*[、，,）]", lead)
    if not m:
        return ""
    # 読みが二通りあるとき（「うまおか / まおか じろう」「さかい たかよし / けいぎ」）は最初の読み
    pieces = [x.split() for x in re.split(r"[/／]", m.group(1)) if x.strip()]
    if not pieces:
        return ""
    first = pieces[0] if len(pieces[0]) >= 2 else pieces[0] + pieces[-1][-1:]
    return " ".join(first[:2]) if len(first) >= 2 else ""


def kana(t, ib):
    return _kana_first(t, ib) or kana_lead(t)


def _hira(s):
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def kana_lead(t):
    """上の読み方で読めないときの冒頭の読み。
    - 冒頭の一文の太字から読む（情報欄の中の旧字体などの太字は飛ばす）。
    - 名前の読みの前に旧字体・別の表記が並ぶ（「（{{旧字体|…}}、なかの てつぞう、」「（渡邉 嘉蔵、渡辺 カ三、わたなべ かぞう、」）。
    - 片仮名の名前の読み（「くつぬぎ タケこ」「かとう シヅエ」）は平仮名にする。
    - 読みの後ろが空白・日付・注（「おかもと りゅういち [[1906年]]」「きしま とらぞう{{Refnest…」「こまつ もとき –」）。
    - 「'''山口 哲夫'''|やまぐち てつお|1928年…」のようにテンプレートの引数で読みを書くもの。
    姓と名の二つに分かれ、平仮名を含む読みだけを採る。"""
    pos = None
    for m in re.finditer("'''", t):
        ls = t.rfind("\n", 0, m.start()) + 1
        line = t[ls:m.start()]
        if line.lstrip().startswith(("|", "!", "{{", "<")) or "=" in line:
            continue
        pos = m.start()
        break
    if pos is None:
        return ""
    lead = t[pos:pos + 1500]
    lead = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", lead, flags=re.S)
    lead = re.sub(r"\{\{旧字体\|([^{}]*)\}\}", r"\1", lead)
    lead = lead.replace("'''", "")
    m = re.match(r"[^（(|\n]{1,30}?[（(|]((?:[^、（）()|\n]{1,40}?、){0,3}?)\s*([ぁ-ゖァ-ヶー]+[ \t　]+[ぁ-ゖァ-ヶー]+)\s*(?=[、，,）)|/／{<–\-\[]|\s|$)", lead)
    if not m:
        return ""
    if re.search(r"[ぁ-ゖ]", m.group(1)):
        return ""   # 前に並ぶものに平仮名がある（別の読み・本名の読み）なら採らない
    if not re.search(r"[ぁ-ゖ]", m.group(2)):
        return ""   # 片仮名だけのもの（外国名の表記など）は採らない
    return _hira(re.sub(r"[ \t　]+", " ", m.group(2)).strip())


def sex(t):
    # 「女性参政権活動家」は男性にも付く（坂東幸太郎氏）
    pat = r"\[\[Category:(?:[^\]|]*の)?女性(?!学|参政権)[^\]|]*\]\]"
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
            start = _date(val.split("<hr>")[0])
        elif on and re.match(r"退任日\d*$", key):
            out.append((start, _date(val)))
            on = False
    return out


SHU_YEAR = dict(zip(range(1, 52), [1890, 1892, 1894, 1894, 1898, 1898, 1902, 1903, 1904, 1908, 1912, 1915, 1917, 1920,
                                    1924, 1928, 1930, 1932, 1936, 1937, 1942, 1946, 1947, 1949, 1952, 1953, 1955, 1958,
                                    1960, 1963, 1967, 1969, 1972, 1976, 1979, 1980, 1983, 1986, 1990, 1993, 1996, 2000,
                                    2003, 2005, 2009, 2012, 2014, 2017, 2021, 2024, 2026]))
SAN_YEAR = dict(zip(range(1, 28), [1947, 1950, 1953, 1956, 1959, 1962, 1965, 1968, 1971, 1974, 1977, 1980, 1983, 1986,
                                   1989, 1992, 1995, 1998, 2001, 2004, 2007, 2010, 2013, 2016, 2019, 2022, 2025]))


def first_win(t, ib):
    """国政選挙で初めて当選した年と院。選挙歴の表と、情報欄の衆議院議員・参議院議員の就任日のうち早いほう。"""
    cands = []
    m = re.search(r"\{\{選挙歴.*?\n\}\}", t, re.S)
    if m:
        body = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", m.group())
        for line in body.split("\n"):
            c = [x.strip() for x in line.split("|")]
            if len(c) < 4 or c[0] != "" or "当" not in c[2] or "無効" in c[2]:
                continue
            if c[1] == "衆" and c[3].isdigit() and int(c[3]) in SHU_YEAR:
                cands.append((SHU_YEAR[int(c[3])], "衆", "選挙歴"))
            elif c[1] == "参" and c[3].isdigit() and int(c[3]) in SAN_YEAR:
                cands.append((SAN_YEAR[int(c[3])], "参", "選挙歴"))
            elif c[1].startswith("補") and ("衆議院" in c[3] or "参議院" in c[3] or c[1] in ("補衆", "補参")):
                y = re.search(r"(1[89]\d\d|20\d\d)[年/]", line)
                if y:
                    cands.append((int(y.group(1)), "参" if "参" in c[3] or c[1] == "補参" else "衆", "選挙歴"))
    for house, h in (("衆議院議員", "衆"), ("参議院議員", "参")):
        for s_, _ in house_tenure(ib, house):
            if s_ and s_[:4].isdigit():
                cands.append((int(s_[:4]), h, "情報欄"))
    return min(cands) if cands else None


def prev_job(ib):
    s = field(ib, "前職")
    s = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = clean(s)
    s = re.sub(r"[\s　]*／[\s　]*", "／", s).strip("／ 　")
    s = re.sub(r"\n+", "／", s)
    return s


def post_tenure(ib, label):
    """情報欄で、職名にその役職を含む欄の在任期間を [(始まり, 終わり)] で返す。
    「A - B<hr>C」のように一つの欄に複数の期間がある書き方も分ける。終わりが現職なら "9999"。"""
    out, on, starts = [], False, []
    pat = re.compile(re.escape(label) + r"(?!会長|副会長|団|総会|代行|代理)")
    for line in ib.split("\n"):
        m = re.match(r"\|\s*([^=|]+?)\s*=(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if re.match(r"(?:職名|その他職歴)\d*$", key):
            on = bool(pat.search(clean(val)))
            continue
        if on and re.match(r"就任日\d*$", key):
            starts = [x for x in re.split(r"<hr\s*/?>", val)]
        elif on and re.match(r"退任日\d*$", key):
            ends = [x for x in re.split(r"<hr\s*/?>", val)]
            for i, seg in enumerate(starts):
                parts = re.split(r"\s[-－–〜~]\s|\]\][-－–〜~]|[-－–〜~]\s*\[\[", seg)
                if len(parts) >= 2 and _date(parts[-1]):
                    a, b = _date(parts[0]), _date(parts[-1])
                else:
                    a = _date(seg)
                    b = _date(ends[i] if i < len(ends) else ends[-1])
                if a:
                    out.append((a, "9999" if b in ("現職", "") else b))
            on = False
    return out


def _place(t, ib):
    """出生地欄の都道府県（これまでの読み方）。なければ本文の「…に生まれる」、それもなければ出身地（place.py）。"""
    p = birth_pref(ib)
    if p:
        return {"birth_pref": p, "birth_pref_basis": "出生地欄"}
    import place
    p, why = place.birth_place(t, ib, field)
    return {"birth_pref": p, "birth_pref_basis": why}


def extract(rec):
    t = rec["text"]
    ib = infobox(t)
    b, bsrc = birth(t, ib)
    return {"title": rec["title"], "pageid": rec["pageid"], "qid": rec.get("qid") or "", "revid": rec.get("revid"),
            "birth": b, "birth_src": bsrc, "kana": kana(t, ib), "sex": sex(t), **_place(t, ib),
            "elections": election_rows(t), "san_tenure": house_tenure(ib), "first": first_win(t, ib),
            "prev_job": prev_job(ib), "disambiguation": rec.get("disambiguation", False),
            "length": rec.get("length")}
