"""選挙記事の「繰上当選」の表から、任期中の欠員と繰上当選を取り出す。

表は「年・月日（月だけの回もある）・ブロック・新旧別・当選者・名簿政党名・欠員・（欠員の政党）・欠員事由」。
date は欠員の日、seated は繰上当選の日（記事に月までしかなければ YYYY-MM）。
"""
import re

from winners import strip_refs

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
REASON = re.compile(r"(\d{4})[.年](\d{1,2})[.月](\d{1,2})日?\s*([^\n|{<]*)")
REASONS = ("自動失職", "当選無効", "辞職", "死去", "退職", "失職", "除名", "辞任")
ATTR = re.compile(r"^\s*(?:[a-z-]+\s*=\s*(?:\"[^\"]*\"|[^\s|\"]+)\s*)+\|(?!\|)")


def _raw_cells(row):
    out = []
    for line in row.split("\n"):
        st = line.strip()
        if not st or st[0] not in "|!" or st.startswith("|}"):
            continue
        for c in re.split(r"\|\||!!", st[1:]):
            out.append((st[0], c))
    return out


def _body(c):
    m = ATTR.match(c)
    return c[m.end():].strip() if m and not c.lstrip().startswith("[[") else c.strip()


def _name(c):
    b = _body(c)
    m = LINK.search(b)
    if m:
        return m.group(1).strip().replace("_", " "), (m.group(2) or m.group(1)).strip()
    return None, re.sub(r"<[^>]+>|\{\{[^}]*\}\}", "", b).strip()


def extract(text):
    m = re.search(r"^=+\s*繰(?:上|り上げ)当選[^=\n]*=+\s*$", text, re.M)
    if not m:
        return []
    start = text.find("{|", m.end())
    nxt = re.search(r"^=+[^=\n]+=+\s*$", text[m.end():], re.M)
    if start < 0 or (nxt and start > m.end() + nxt.start()):
        return []
    end = text.find("\n|}", start)
    table = strip_refs(text[start:end])
    table = re.sub(r"\{\{0\}\}", "", table)
    out, year, md = [], None, None
    for row in table.split("\n|-")[1:]:
        cells = _raw_cells(row)
        if not cells:
            continue
        i = 0
        while i < len(cells) and cells[i][0] == "|" and "background-color" not in cells[i][1]:
            b = _body(cells[i][1])
            if re.fullmatch(r"(?:\[\[\d{4}年[^|\]]*\|)?\d{4}(?:\]\])?", b):
                year = int(re.search(r"\d{4}", b).group())
            elif re.fullmatch(r"\d{1,2}(?:\.\d{1,2})?", b):
                md = b
            elif re.fullmatch(r"[－\-—]", b):
                md = None
            else:
                break
            i += 1
        rm = None
        for _, c in cells:
            x = REASON.search(c)
            if x:
                rm = x
        ym = None
        if not rm:
            # 欠員の日がなく「2013年5月」のような繰上年月だけの表（第46回）
            ym = re.search(r"(\d{4})年\s*(\d{1,2})月", row)
            if not ym:
                continue
        block = next((_body(c) for h, c in cells if h == "!" and not re.search(r"\d{4}年", c)), "")
        if ym and not block:
            block = next((_body(c) for h, c in cells if h == "|" and "ブロック" in c), "")
        block = (LINK.search(block).group(2) or LINK.search(block).group(1)) if LINK.search(block) else block
        people = [c for h, c in cells if h == "|" and "background-color" in c]
        vacant = "（欠員）" in row
        if vacant:
            new, old = (None, None), _name(people[-1]) if people else (None, "")
        else:
            new = _name(people[0]) if people else (None, None)
            if len(people) > 1:
                old = _name(people[1])
            else:  # 欠員の人のセルに色がない書き方
                rest = [c for h, c in cells if h == "|"]
                ri = next(k for k in range(len(rest)) if REASON.search(rest[k]))
                old = _name(rest[ri - 1])
        if ym:
            vac = seated = f"{int(ym[1]):04d}-{int(ym[2]):02d}"
            last = _body(cells[-1][1])
            reason = next((k for k in REASONS if k in last), last or "不明")
        else:
            vac = f"{int(rm[1]):04d}-{int(rm[2]):02d}-{int(rm[3]):02d}"
            seated = ""
            if md and year and not vacant:
                seated = f"{year:04d}-{int(md.split('.')[0]):02d}" + (f"-{int(md.split('.')[1]):02d}" if "." in md else "")
            reason = next((k for k in REASONS if k in rm.group(4)), rm.group(4).strip())
        out.append({"date": vac, "seated": seated, "reason": reason, "block": block,
                    "new_article": new[0], "new_name": new[1], "old_article": old[0], "old_name": old[1]})
    return out
