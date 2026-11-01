"""内閣の記事から、国務大臣・内閣官房副長官・首相補佐官・副大臣・大臣政務官を取り出す。

表（wikitable）の書き方と、箇条書き（*'''[[役職]]''' - [[氏名]]：-日付、…）の書き方の両方を読む。
備考の「…任命」「…辞任」などの日付から在任の始まりと終わりを拾う。所属欄の（…派）は派閥の手がかりとして返す。
"""
import re

import wtable

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
DATE = re.compile(r"(\d{4})年(?:\s*[（(][^）)]*[）)])?\s*\[?\[?(\d{1,2})月(\d{1,2})日\]?\]?")
SECTIONS = {"国務大臣": "閣僚", "内閣官房副長官": "閣僚", "内閣総理大臣補佐官": "閣僚", "副大臣": "副大臣", "大臣政務官": "大臣政務官"}
START_W = r"任命|就任|発令|から|兼任|昇格"
END_W = r"罷免|辞任|辞職|退任|免|死去|まで|更迭|解任|失職|逝去|転出"


def plain(s):
    s = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{(?:Small|small|nowrap|Nowrap)\|([^{}]*)\}\}", r"\1", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"'''?|<[^>]+>", "", s)
    return s.strip()


def _iso(m):
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def dates(note):
    """備考から (始まり, 終わり) を拾う。"""
    start = end = ""
    s = re.sub(r"<br\s*/?>", " ", note)
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    for m in DATE.finditer(s):
        before, after = s[max(0, m.start() - 3):m.start()], s[m.end():m.end() + 8]
        if re.match(r"\s*(?:" + END_W + ")", after) or re.search(r"[-－–〜~]\s*$", before):
            end = end or _iso(m)
        elif re.match(r"\s*(?:" + START_W + r")|\s*[-－–〜~]", after):
            start = start or _iso(m)
    return start, end


def _person(cell):
    for m in LINK.finditer(cell):
        t = m.group(1)
        if re.match(r"(?:画像|File|file|ファイル|Image)\s*:", t):
            continue
        return t.strip().replace("_", " "), (m.group(2) or t).strip()
    return None


def _faction(cell):
    """所属欄の（[[清和政策研究会|森派]]）のような派閥の手がかり。"""
    m = re.search(r"[（(]\s*(\[\[[^\]]+\]\]|[^（）()<\[\]]{1,20}?)\s*[）)]", re.sub(r"<br\s*/?>", " ", cell))
    if not m:
        return None
    lk = LINK.search(m.group(1))
    return (lk.group(1).strip(), (lk.group(2) or lk.group(1)).strip()) if lk else (None, m.group(1).strip())


def _section_of(text, pos):
    hs = re.findall(r"^=+\s*([^=\n]+?)\s*=+\s*$", text[:pos], re.M)
    if not hs:
        return None
    h = hs[-1]
    return next((v for k, v in SECTIONS.items() if k in h), None), h


def extract(text):
    out = []
    for pos, tb in wtable.tables(text):
        sec = _section_of(text, pos)
        if not sec or not sec[0]:
            continue
        kind, head = sec
        g = wtable.grid(tb)
        if not g:
            continue
        hdr = [plain(c[1]) for c in g[0]]
        col = lambda *names: next((i for i, h in enumerate(hdr) if any(n in h for n in names)), None)
        c_role, c_note, c_aff = col("職名", "役職"), col("備考"), col("所属", "出身")
        name_cols = [i for i, h in enumerate(hdr) if "氏名" in h]
        for row in g[1:]:
            if c_role is None or len(row) <= c_role:
                continue
            person = None
            for i in name_cols:
                if i < len(row):
                    person = _person(row[i][1])
                    if person:
                        cell = row[i][1]
                        break
            if not person or re.match(r"\s*[（(]", plain(cell)):
                continue  # （小泉純一郎）のような臨時の兼任
            role_lines = [x for x in plain(row[c_role][1]).split("\n") if x.strip()]
            note = row[c_note][1] if c_note is not None and c_note < len(row) else ""
            s, e = dates(note)
            fac = _faction(row[c_aff][1]) if c_aff is not None and c_aff < len(row) else None
            out.append({"kind": kind, "section": head, "post": role_lines[0] if role_lines else "",
                        "extra": "・".join(role_lines[1:]), "article": person[0], "name": person[1],
                        "start": s, "end": e, "faction": fac, "note": plain(note).replace("\n", "　")})
    # 箇条書きの副大臣・大臣政務官
    for m in re.finditer(r"^\*\s*'''\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'''\s*[-－–]\s*(.+)$", text, re.M):
        sec = _section_of(text, m.start())
        if not sec or not sec[0]:
            continue
        post = (m.group(2) or m.group(1)).strip()
        for part in re.split(r"、", m.group(3)):
            person = _person(part)
            if not person:
                continue
            s, e = "", ""
            tail = part[part.find("]]") + 2:]
            dm = DATE.search(LINK.sub(lambda x: x.group(2) or x.group(1), tail))
            if dm:
                txt = LINK.sub(lambda x: x.group(2) or x.group(1), tail)
                if re.search(r"[：:]\s*[-－–]", txt):
                    e = _iso(dm)
                else:
                    s = _iso(dm)
            out.append({"kind": sec[0], "section": sec[1], "post": post, "extra": "", "article": person[0],
                        "name": person[1], "start": s, "end": e, "faction": None, "note": plain(tail).strip("：: ")})
    return out


def in_office(rows, day, cab_start):
    """day に在任していた行。"""
    return [r for r in rows if (not r["start"] or r["start"] <= day) and (not r["end"] or r["end"] >= day)
            and (r["start"] or cab_start <= day)]
