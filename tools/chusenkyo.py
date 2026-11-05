"""中選挙区制の衆院選（第23〜40回）の選挙記事から、当選者の表を読む。

表は「都道府県（見出し）→ 選挙区（見出し）→ 当選者のセル（背景色が党派）」の並び。
一つの区が行をまたぐときは、区の見出しに rowspan が付いている。格子に広げたうえで、
各セルの左にある最も近い区の見出しを、そのセルの区とする。
"""
import re

from wtable import _split_cells, _span, tables

LINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")
COLORBOX = re.compile(r"\{\{colorbox\|\s*(#?[0-9A-Fa-f]{3,6})\s*\|\s*([^}|]+?)\s*\}\}")
BG = re.compile(r"background(?:-color)?\s*:\s*(#[0-9A-Fa-f]{3,6})")


def _norm_color(c):
    c = c.lower().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return "#" + c


def strip_refs(s):
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{[Rr]efnest[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}", "", s)
    s = re.sub(r"\{\{efn[^{}]*\}\}", "", s)
    return s


def legend(text):
    """凡例（{{colorbox|#色|党名}}・{{政党箱|党名}}・{{政党箱|色|党名}}）から 色→党名。"""
    import winners
    return {_norm_color(c): name for c, name in winners.legend(text).items()}


def _grid(table):
    lines = table.split("\n")[1:]
    rows, cur = [], None
    for ln in lines:
        st = ln.strip()
        if st.startswith("|}"):
            break
        if st.startswith("|-"):
            if cur is not None:
                rows.append(cur)
            cur = []
            continue
        if not st or st[0] not in "|!" or st.startswith("|+"):
            if cur and st and st[0] not in "|!{":
                h, a, c = cur[-1]
                cur[-1] = (h, a, c + "\n" + st)
            continue
        if cur is None:
            cur = []
        cur.extend(_split_cells(st))
    if cur is not None:
        rows.append(cur)
    out, pending = [], {}
    for raw in rows:
        cells, col, items = [], 0, list(raw)
        while items or col in pending:
            if col in pending:
                n, val = pending[col]
                cells.append(val + (True,))
                if n <= 1:
                    del pending[col]
                else:
                    pending[col] = (n - 1, val)
                col += 1
                continue
            h, a, c = items.pop(0)
            rs, cs = _span(a, "rowspan"), _span(a, "colspan")
            for _ in range(cs):
                cells.append((h, a, c, False))
                if rs > 1:
                    pending[col] = (rs - 1, (h, a, c))
                col += 1
        out.append(cells)
    return out


def _district(content):
    """区の見出しから (都道府県, 区の名前)。「[[北海道第1区 (中選挙区)|1区]]」「[[鳥取県全県区|全県区]]」など。"""
    lk = LINK.search(content)
    target = lk.group(1).strip() if lk else re.sub(r"<[^>]+>", "", content).strip()
    if target.startswith("奄美群島"):
        return "鹿児島県", "奄美群島区"
    m = re.match(r"(.+?[都道府県]|北海道)(第\d+区|全県区|全区)", target.replace("北海道第", "北海道第"))
    if m:
        name = m.group(2).replace("第", "")
        return m.group(1), name
    shown = (lk.group(2) or lk.group(1)).strip() if lk else target
    if re.fullmatch(r"\d+区|全県区|全区", shown):
        return None, shown
    return None


def extract(text):
    """当選者 [{pref, district, party, article, name, note}] と、気づいたことの一覧を返す。"""
    i = text.find("=== 当選者 ===")
    if i < 0:
        raise ValueError("「当選者」の見出しがない")
    end = text.find("\n==", i + 10)
    sec = text[i:end if end > 0 else len(text)]
    leg = legend(sec)
    tabs = [t for _, t in tables(sec)]
    if not tabs:
        raise ValueError("当選者の表がない")
    table = max(tabs, key=len)
    rows, notes, seen = [], [], set()
    pref = None
    for cells in _grid(table):
        cur = None
        for h, a, c, repeated in cells:
            if h:
                lk = LINK.search(c)
                tgt = lk.group(1) if lk else c
                if re.fullmatch(r"\s*(?:\[\[)?[^\]|]*?(都|道|府|県)(?:\]\])?\s*", c) and "区" not in c:
                    pref = re.sub(r"[\[\]\s]", "", lk.group(1) if lk else c)
                    continue
                d = _district(c)
                if d:
                    cur = (d[0] or pref, d[1])
                continue
            if repeated or cur is None:
                continue
            body = strip_refs(c)
            lk = LINK.search(body)
            if not lk:
                continue
            m = BG.search(a or "")
            color = _norm_color(m.group(1)) if m else None
            party = leg.get(color)
            if not party:
                notes.append(f"{cur[0]}{cur[1]} {lk.group(1)}：凡例にない色 {color}")
                party = "無所属"
            key = (cur, lk.group(1).strip())
            if key in seen:
                continue
            seen.add(key)
            refs = re.findall(r"\{\{[Rr]efnest\|[^{}]*?\|name=\"?[^|}\"]*\"?\|([^{}]*)\}\}", c)
            rows.append({"kind": "中選挙区", "pref": cur[0], "district": cur[1], "party": party,
                         "article": lk.group(1).strip(), "name": (lk.group(2) or lk.group(1)).strip(),
                         "note": refs[0].strip() if refs else ""})
    return rows, notes
