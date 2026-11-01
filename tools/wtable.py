"""wikitable を、rowspan・colspan を広げた格子（行ごとのセルの並び）にする。"""
import re

ATTR = re.compile(r"^\s*((?:[a-zA-Z-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s|\"']+)\s*)+)\|(?!\|)")


def _split_cells(line):
    """1行（| または ! で始まる）を、(見出しか, 属性, 中身) の並びにする。[[..|..]] と {{..|..}} の中の | は区切らない。"""
    head = line[0] == "!"
    body = line[1:]
    parts, depth, cur, k = [], 0, "", 0
    while k < len(body):
        two = body[k:k + 2]
        if two in ("[[", "{{"):
            depth += 1; cur += two; k += 2; continue
        if two in ("]]", "}}"):
            depth = max(0, depth - 1); cur += two; k += 2; continue
        if depth == 0 and (two == "||" or (head and two == "!!")):
            parts.append(cur); cur = ""; k += 2; continue
        cur += body[k]; k += 1
    parts.append(cur)
    out = []
    for p in parts:
        m = ATTR.match(p)
        attr, content = (m.group(1), p[m.end():]) if m and "[[" not in p[:m.end()] else ("", p)
        out.append((head, attr, content.strip()))
    return out


def _span(attr, name):
    m = re.search(name + r"\s*=\s*[\"']?(\d+)", attr or "")
    return int(m.group(1)) if m else 1


def tables(text):
    """text の中の wikitable（入れ子でないもの）を、上から順に返す。"""
    out, pos = [], 0
    while True:
        i = text.find("{|", pos)
        if i < 0:
            return out
        depth, j = 0, i
        while j < len(text):
            if text.startswith("{|", j):
                depth += 1; j += 2
            elif text.startswith("|}", j):
                depth -= 1; j += 2
                if depth == 0:
                    break
            else:
                j += 1
        out.append((i, text[i:j]))
        pos = j


def grid(table):
    """表を行の並びにする。各行は [(見出しか, 中身)] で、rowspan・colspan は広げてある。"""
    lines = table.split("\n")[1:]
    rows, cur, pending = [], None, {}
    for ln in lines:
        st = ln.strip()
        if st.startswith("|}"):
            break
        if st.startswith("|-"):
            if cur is not None:
                rows.append(cur)
            cur = []
            continue
        if st.startswith("|+") or not st or st[0] not in "|!":
            if cur is not None and cur and st and st[0] not in "|!{":
                tag, (h, a, c) = cur[-1]
                cur[-1] = (tag, (h, a, c + "\n" + st))
            continue
        if cur is None:
            cur = []
        cur.extend(("raw", x) for x in _split_cells(st))
    if cur is not None:
        rows.append(cur)
    out = []
    for raw in rows:
        cells, col = [], 0
        items = [x for _, x in raw]
        while items or col in pending:
            if col in pending:
                n, val = pending[col]
                cells.append(val)
                if n <= 1:
                    del pending[col]
                else:
                    pending[col] = (n - 1, val)
                col += 1
                continue
            head, attr, content = items.pop(0)
            rs, cs = _span(attr, "rowspan"), _span(attr, "colspan")
            for _ in range(cs):
                cells.append((head, content))
                if rs > 1:
                    pending[col] = (rs - 1, (head, content))
                col += 1
        if cells:
            out.append(cells)
    return out
