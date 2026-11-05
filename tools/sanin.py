"""参院選（通常選挙）の記事から当選者を取り出す。

記事の書き方は回によって違う。
- 選挙区：wikitable（「! [[X選挙区|X]]」の見出しの後に色付きセル）か、{{参院選挙区当選者|東京=色:[[名前]]…}}
- 比例区：wikitable（「!1-10」の見出しの後に色付きセル）か、{{参院比例当選者| 色:[[名前]]…}}
任期3年の合併選挙（補充）の当選者は、テンプレートでは「:補欠」、表では注記（補充当選・任期3年）で示される。
"""
import re

from winners import BG, LINK, PREF_FULL, PREF_SHORT, canon, legend, params, section, strip_refs, template_body

SHORT_TERM = re.compile(r"補充|任期3年|任期は3年|残任期間")


def _leg(sec, upto):
    head = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", sec[:upto], flags=re.S)
    return {k: v.split("<")[0].strip() for k, v in legend(head).items()}


def _party(leg, color, where, notes, fix):
    c = color.lower().lstrip("#")
    if c in fix:
        return fix[c]
    if c in ("fff", "ffffff"):
        return "無所属"
    if c not in leg and c[:3] in leg:
        c = c[:3]
    if c not in leg and c in ("9f9", "9e9") and ({"9f9", "9e9"} & set(leg)):
        c = ({"9f9", "9e9"} & set(leg)).pop()  # 自民党の色の二通りの書き方
    if c not in leg:
        # 大文字小文字や 9F9/9E9 のような近い色の書き分け
        near = [k for k in leg if len(k) == len(c) and sum(a != b for a, b in zip(k, c)) == 1]
        if len(near) == 1:
            notes.append(f"{where}：色「{color}」を凡例の「{near[0]}」（{leg[near[0]]}）と読んだ")
            c = near[0]
        else:
            raise ValueError(f"凡例にない色 {color} ({where}) 凡例={leg}")
    return leg[c]


def _note_text(cell):
    """セルの注記（efn・Refnest・ref）の中身を返す。"""
    return " ".join(re.findall(r"\{\{(?:efn2?|Refnest|refnest)\|([^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*)\}\}", cell) +
                    re.findall(r"<ref[^>/]*>(.*?)</ref>", cell, re.S))


def _pref_of(name):
    name = name.replace("選挙区", "")
    if name in PREF_SHORT:
        return PREF_SHORT[name]
    if name in PREF_FULL:
        return name
    m = re.fullmatch(r"(鳥取|島根|徳島|高知)(?:県)?[・･](鳥取|島根|徳島|高知)(?:県)?", name)
    if m:
        return f"{m.group(1)}・{m.group(2)}"
    return None


def _cells(table):
    """wikitable を（見出しか, セルの生テキスト）の並びにする。"""
    for line in table.split("\n"):
        st = line.strip()
        if not st or st.startswith("|-") or st.startswith("{|") or st.startswith("|}") or st.startswith("|+"):
            continue
        if st[0] not in "|!":
            continue
        head = st[0] == "!"
        for c in re.split(r"\|\||!!", st[1:]):
            yield head, c


def _header_grid_rows(sec, notes, fix):
    """「見出しの行（県名、colspan が定数）→ 当選者の行」が交互に続く表（1980年代の記事）を読む。"""
    from wtable import _split_cells, _span
    i = sec.find("{|")
    leg = _leg(sec, i)
    end = sec.find("\n|}", i)
    body = sec[i:end if end > 0 else len(sec)]
    rows, cols = [], None
    for chunk in body.split("\n|-")[1:]:
        cells = []
        for line in chunk.split("\n"):
            st = line.strip()
            if st and st[0] in "|!" and not st.startswith("|}"):
                cells += _split_cells(st)
        heads = [c for c in cells if c[0]]
        if heads and not any(not c[0] and BG.search(c[1] or "") for c in cells):
            cols = []
            for _h, a, c in heads:
                lk = LINK.search(c)
                p = (_pref_of(lk.group(2) or lk.group(1)) or _pref_of(lk.group(1))) if lk else None
                cols += [p] * _span(a, "colspan")
            continue
        if cols is None:
            continue
        data = [c for c in cells if not c[0] and BG.search(c[1] or "")]
        for k, (_h, a, c) in enumerate(data):
            bm = BG.search(a or "")
            lk = LINK.search(strip_refs(c))
            if not bm or not lk or k >= len(cols) or not cols[k]:
                continue
            note = _note_text(c)
            rows.append({"kind": "選挙区", "pref": cols[k], "party": _party(leg, bm.group(1), cols[k], notes, fix),
                         "article": lk.group(1).strip().replace("_", " "), "name": (lk.group(2) or lk.group(1)).strip(),
                         "short": bool(SHORT_TERM.search(note)), "tokutei": False, "note": note[:200]})
        cols = None
    return rows


def _table_rows(sec, kind, notes, fix):
    rows = []
    i = sec.find("{|")
    if i < 0:
        return rows
    if kind == "選挙区" and re.search(r"^!.*\]\]\s*!!", sec[i:], re.M):
        return _header_grid_rows(sec, notes, fix)
    leg = _leg(sec, i)
    pref, rank_base, k = None, None, 0
    for head, c in _cells(sec[i:]):
        if head:
            lk = LINK.search(c)
            if kind == "選挙区" and lk:
                p = _pref_of(lk.group(2) or lk.group(1)) or _pref_of(lk.group(1))
                if p:
                    pref = p
            m = re.match(r"\s*(?:[^|]*\|)?\s*(\d+)\s*位?\s*[-‐–〜~]\s*\d+", c)
            if kind in ("比例", "全国区") and m:
                rank_base, k = int(m.group(1)), 0
            continue
        bm = BG.search(c.split("|")[0]) if "|" in c else None
        body = c.split("|", 1)[1] if bm else c
        lk = LINK.search(strip_refs(body))
        if not lk or not bm:
            continue
        where = pref if kind == "選挙区" else f"{kind}{(rank_base or 0) + k}"
        party = _party(leg, bm.group(1), where, notes, fix)
        note = _note_text(body)
        r = {"kind": kind, "party": party, "article": lk.group(1).strip().replace("_", " "),
             "name": (lk.group(2) or lk.group(1)).strip(), "short": bool(SHORT_TERM.search(note)) and kind == "選挙区",
             "tokutei": False, "note": note[:200]}
        if kind == "選挙区":
            if not pref:
                continue
            r["pref"] = pref
        else:
            r["order"] = (rank_base or 1) + k
            k += 1
        rows.append(r)
    return rows


ITEM = re.compile(r"([0-9A-Fa-f]{3,6})\s*:\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]((?:\s*:\s*[^\s\[{<|:]+)*)")


def _template_rows(sec, name, kind, notes, fix):
    body = template_body(sec, name)
    i = sec.find("{{" + name)
    leg = _leg(sec, i)
    rows = []
    if kind == "選挙区":
        for key, val in params(body).items():
            pref = _pref_of(key.strip())
            if not pref:
                continue
            for m in ITEM.finditer(strip_refs(val)):
                flags = m.group(4) or ""
                rows.append({"kind": kind, "pref": pref, "party": _party(leg, m.group(1), pref, notes, fix),
                             "article": m.group(2).strip().replace("_", " "), "name": (m.group(3) or m.group(2)).strip(),
                             "short": "補欠" in flags, "tokutei": False, "note": flags.strip(" :")})
    else:
        for n, m in enumerate(ITEM.finditer(strip_refs(body)), 1):
            flags = m.group(4) or ""
            rows.append({"kind": kind, "order": n, "party": _party(leg, m.group(1), f"比例{n}", notes, fix),
                         "article": m.group(2).strip().replace("_", " "), "name": (m.group(3) or m.group(2)).strip(),
                         "short": False, "tokutei": "特定枠" in flags, "note": flags.strip(" :")})
    return rows


def extract(text, fix=None, tokutei=()):
    """fix は 色→党名 の上書き、tokutei は特定枠の当選者名（注記が名前参照で拾えない回のため）。"""
    fix = {k.lower(): v for k, v in (fix or {}).items()}
    notes = []
    out = []
    national = section(text, r"(?:比例区当選者|比例代表選出議員)") is None and \
        section(text, r"(?:この選挙で)?全国区当選(?:者)?") is not None   # 1980年までの全国区
    for kind, heads, tpl in (("選挙区", r"(?:この選挙で)?(?:選挙区|地方区)当選(?:者)?", "参院選挙区当選者"),
                             ("全国区", r"(?:この選挙で)?全国区当選(?:者)?", "参院比例当選者") if national else
                             ("比例", r"(?:比例区当選者|比例代表選出議員)", "参院比例当選者")):
        sec = section(text, heads)
        if sec is None:
            raise ValueError(f"{kind}の見出しがない")
        sub = re.search(r"^====", sec, re.M)
        sec = sec[:sub.start()] if sub else sec
        rows = _template_rows(sec, tpl, kind, notes, fix) if "{{" + tpl in sec else _table_rows(sec, kind, notes, fix)
        for r in rows:
            r["party"], r["party_note"] = canon(r["party"]) if r["party"] != "無所属" else ("無所属", "")
        for r in rows:
            if r["name"] in tokutei:
                r["tokutei"] = True
        out += rows
    return out, notes
