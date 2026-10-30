"""選挙記事の「補欠選挙」の表から、補選の当選者と欠員になった議員を取り出す。

衆院選の記事の表は「年・月日・選挙区・新旧別・当選者・当選政党・欠員・欠員政党・欠員事由」、
参院選の記事の表は、これに「選出」（補欠選挙・再選挙）の列が加わる。
補選をせずに欠員のまま解散・任期満了を迎えた行（「未実施」「実施せず」）も、欠員として返す。
"""
import re

from winners import strip_refs

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
REASON = re.compile(r"(\d{4})[.年](\d{1,2})[.月](\d{1,2})日?\s*([^\n|{<]*)")
REASONS = ("自動失職", "当選無効", "辞職", "死去", "退職", "失職", "除名", "辞任")


def _cells(row):
    """表の1行をセルの並びにする（属性は落とす）。"""
    out = []
    for line in row.split("\n"):
        line = line.strip()
        if not line or line[0] not in "|!":
            continue
        head = line[0]
        for c in re.split(r"\|\||!!", line[1:]):
            attr = re.match(r"\s*((?:[a-z-]+\s*=\s*\"[^\"]*\"\s*)+|(?:[a-z-]+\s*=\s*[^|\s\"]+\s*)+)\|(?!\|)", c)
            if attr and not c.lstrip().startswith("[["):
                c = c[attr.end():]
            out.append((head, c.strip()))
    return out


def _person(c):
    m = LINK.search(c)
    if m:
        return m.group(1).strip().replace("_", " "), (m.group(2) or m.group(1)).strip()
    s = re.sub(r"<[^>]+>|\{\{[^}]*\}\}", "", c).strip()
    return (None, s) if s else (None, None)


def _plain(c):
    m = LINK.search(c)
    return (m.group(2) or m.group(1)).strip() if m else re.sub(r"<[^>]+>", "", c).strip()


def _reason(s):
    for k in REASONS:
        if k in s:
            return k
    if re.search(r"刺殺|死亡|死", s):
        return "死去"
    return _plain(s)


def extract(text, heading=r"補欠(?:選挙|当選)[^=\n]*"):
    m = re.search(r"^=+\s*" + heading + r"=+\s*$", text, re.M)
    if not m:
        return []
    start = text.find("{|", m.end())
    nxt = re.search(r"^=+[^=\n]+=+\s*$", text[m.end():], re.M)
    if start < 0 or (nxt and start > m.end() + nxt.start()):
        return []
    end = text.find("\n|}", start)
    table = strip_refs(text[start:end])
    table = re.sub(r"\{\{(?:efn2?|Refnest)[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}", "", table)
    out, year = [], None
    for row in table.split("\n|-")[1:]:
        cells = _cells(row)
        i = 0
        # 年（rowspan で省略されることがある）
        if i < len(cells) and cells[i][0] == "|" and re.fullmatch(r"(?:\[\[\d{4}年日本の補欠選挙\|)?\d{4}(?:\]\])?\s*", cells[i][1]):
            year = int(re.search(r"(\d{4})", cells[i][1]).group(1))
            i += 1
        elif i < len(cells) and cells[i][0] == "|" and cells[i][1] == "":
            i += 1
        md = None
        if i < len(cells) and re.fullmatch(r"\d{1,2}\.\d{1,2}", cells[i][1]):
            md = cells[i][1]
            i += 1
        elif i < len(cells) and re.fullmatch(r"\d{1,2}", cells[i][1]):
            i += 1  # 「10」だけの月（実施せず）
        if i >= len(cells) or cells[i][0] != "!":
            # 選挙区の見出しセルがない行（同じ日の続き）は、前の日付を使う
            if out and md is None and cells and cells[0][0] == "!":
                i = 0
            else:
                continue
        if md:
            last_date = f"{year:04d}-{int(md.split('.')[0]):02d}-{int(md.split('.')[1]):02d}"
        elif out and i == 0:
            last_date = out[-1]["date"]
        else:
            last_date = ""
        district = _plain(cells[i][1])
        rest = [c for _, c in cells[i + 1:]]
        kind = "補欠選挙"
        if rest and rest[0] not in ("新", "前", "元", "現") and not LINK.search(rest[0]) and \
                re.search(r"選挙|当選|補欠|再", rest[0]):
            kind = {"補欠": "補欠選挙", "再": "再選挙"}.get(rest[0], rest[0])
            rest = rest[1:]
        ri = next((k for k in range(len(rest) - 1, -1, -1) if REASON.search(rest[k])), None)
        if ri is None:
            continue
        rm = REASON.search(rest[ri])
        old = _person(rest[ri - 2]) if ri >= 2 else (None, None)
        held = ri >= 5 and not any(x in "".join(rest[:ri]) for x in ("未実施", "実施せず"))
        win = _person(rest[1]) if held and len(rest) > 1 else (None, None)
        wparty = _plain(rest[2]) if held and len(rest) > 2 else ""
        oparty = _plain(rest[ri - 1]) if ri >= 1 else ""
        out.append({"date": last_date if held else "", "kind": kind if held else "未実施",
                    "district": district,
                    "winner_article": win[0], "winner_name": win[1], "winner_party": wparty,
                    "old_party": oparty,
                    "old_article": old[0], "old_name": old[1],
                    "vacated_date": f"{int(rm[1]):04d}-{int(rm[2]):02d}-{int(rm[3]):02d}",
                    "reason": _reason(rest[ri][rm.start(4):])})
    return out
