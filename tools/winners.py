"""衆院選（並立制）の記事から当選者を取り出す。

記事の「小選挙区当選者」「比例区当選者」の表（{{衆院小選挙区当選者}}・{{衆院比例当選者}} の
テンプレート）を読み、党派は表の上にある {{政党箱}} の凡例の色で決める。
"""
import re

import wiki

PREFS = ["北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島", "茨城", "栃木", "群馬", "埼玉", "千葉", "東京",
         "神奈川", "新潟", "富山", "石川", "福井", "山梨", "長野", "岐阜", "静岡", "愛知", "三重", "滋賀", "京都",
         "大阪", "兵庫", "奈良", "和歌山", "鳥取", "島根", "岡山", "広島", "山口", "徳島", "香川", "愛媛", "高知",
         "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄"]
BLOCKS = ["北海道", "東北", "北関東", "南関東", "東京", "北陸信越", "東海", "近畿", "中国", "四国", "九州"]
_color_cache = {}


def party_color(name):
    """{{政党色|名前|1}} を展開して党の色を得る。"""
    if name not in _color_cache:
        r = wiki.call({"action": "expandtemplates", "text": "{{政党色|%s|1}}" % name, "prop": "wikitext"})
        _color_cache[name] = r["expandtemplates"]["wikitext"].strip().lower().lstrip("#")
    return _color_cache[name]


CANON = {"自民党": "自由民主党", "社民党": "社会民主党", "共産党": "日本共産党", "公明": "公明党",
         "さきがけ": "新党さきがけ", "維新": "日本維新の会", "みんな": "みんなの党",
         "維新の会": "日本維新の会", "未来の党": "日本未来の党"}


def canon(name):
    name = re.sub(r"\s+", " ", name).strip()
    m = re.match(r"無所属\s*[（(](.+?)[）)]", name)
    if m:
        return "無所属", m.group(1)
    return CANON.get(name, name), ""


def legend(section):
    """凡例 {{政党箱|党名}} / {{政党箱|色|党名}} / {{colorbox|#色|党名}} から 色→党名 の対応を作る。"""
    out = {}
    for color, name in re.findall(r"\{\{colorbox\|#?([0-9A-Fa-f]{3,6})\|([^}|]+)", section):
        out[color.lower()] = name.split("{{")[0].strip()
    for args in re.findall(r"\{\{政党箱\|([^}]*)\}\}", section):
        a = [x.strip() for x in args.split("|")]
        if len(a) >= 2 and re.fullmatch(r"#?[0-9A-Fa-f]{3,6}", a[0]):
            color, name = a[0].lower().lstrip("#"), a[1]
        else:
            name = a[-1] if len(a) >= 2 else a[0]
            color = party_color(a[0])
        if color in out and out[color] != name:
            raise ValueError(f"凡例の色が重なっている: {color} {out[color]} / {name}")
        out[color] = name
    return out


def template_body(text, name):
    i = text.find("{{" + name)
    if i < 0:
        return None
    depth, j = 0, i
    while j < len(text):
        if text.startswith("{{", j):
            depth += 1
            j += 2
        elif text.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                return text[i:j]
        else:
            j += 1
    raise ValueError("テンプレートが閉じていない: " + name)


def strip_refs(s):
    s = re.sub(r"<ref[^>]*/>|<ref.*?</ref>", "", s, flags=re.S)
    depth_free = re.sub(r"\{\{(?:Refnest|refnest|efn2?|Efn2?)[^{}]*(?:\{\{[^{}]*\}\}[^{}]*)*\}\}", "", s)
    return depth_free


def params(body):
    """テンプレートの引数を {名前: 中身} にする（1段の入れ子まで）。"""
    inner = body[2:-2]
    parts, depth, cur = [], 0, ""
    k = 0
    while k < len(inner):
        if inner.startswith("{{", k) or inner.startswith("[[", k):
            depth += 1
            cur += inner[k:k + 2]
            k += 2
            continue
        if inner.startswith("}}", k) or inner.startswith("]]", k):
            depth -= 1
            cur += inner[k:k + 2]
            k += 2
            continue
        if inner[k] == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += inner[k]
        k += 1
    parts.append(cur)
    out = {}
    for p in parts[1:]:
        if "=" in p:
            key, val = p.split("=", 1)
            out[key.strip()] = val
    return out


LINE = re.compile(r"^\s*([0-9A-Fa-f]{3,6})\s*:\s*(.*)$")
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def lines(val):
    for raw in strip_refs(val).split("\n"):
        m = LINE.match(raw)
        if not m:
            continue
        color, rest = m.group(1).lower(), m.group(2).strip()
        lk = LINK.search(rest)
        if lk:
            yield color, lk.group(1).strip(), (lk.group(2) or lk.group(1)).strip()
        else:
            yield color, None, rest


def section(text, heading_re):
    m = re.search(r"^=+\s*" + heading_re + r"\s*=+\s*$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^=+\s*[^=\n]+=+\s*$", text[m.end():], re.M)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


OLD_BLOCK = {"北海": "北海道", "東北": "東北", "北関": "北関東", "南関": "南関東", "東京": "東京", "北信": "北陸信越",
             "東海": "東海", "近畿": "近畿", "中国": "中国", "四国": "四国", "九州": "九州"}


def _with_color(leg, color, where, notes):
    color = color.lower().lstrip("#")
    if color not in leg and color[:3] in leg:
        notes.append(f"{where}：記事の色指定「{color}」を「{color[:3]}」と読んだ")
        color = color[:3]
    if color not in leg:
        raise ValueError(f"凡例にない色 {color} ({where})")
    return leg[color]


PREF_FULL = {p: (p if p == "北海道" else p + ("都" if p == "東京" else "府" if p in ("京都", "大阪") else "県")) for p in PREFS}
PREF_SHORT = {v: k for k, v in PREF_FULL.items()}
BG = re.compile(r"background-color:\s*#?([0-9A-Fa-f]{3,6})")


def smd_wikitable(text, notes):
    sec = section(text, r"小選挙区当選者")
    i = sec.find("{|")
    leg = legend(sec[:i])
    leg.update(FIX_COLOR)
    rows, pref, dist = [], None, None
    for line in strip_refs(sec[i:]).split("\n"):
        st = line.strip()
        m = re.match(r"!\s*(?:rowspan=\"?\d+\"?\s*\|)?\s*\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]\s*$", st)
        if m and m.group(1) in PREF_SHORT:
            pref = PREF_SHORT[m.group(1)]
        m = re.match(r"!\s*\[\[[^\]|]*第(\d+)区", st)
        if m:
            dist = int(m.group(1))
        bm = BG.search(st)
        if st.startswith("|") and not st.startswith("|-") and pref and dist:
            lk = LINK.search(st.split("|", 2)[-1])
            if not lk:
                continue
            if bm:
                party = _with_color(leg, bm.group(1), f"{pref}{dist}区", notes)
            else:
                party = "無所属"
                notes.append(f"{pref}{dist}区 {lk.group(1)}：色の指定がないので無所属と読んだ")
            rows.append({"kind": "小選挙区", "pref": pref, "district": dist, "party": party,
                         "article": lk.group(1).strip(), "name": (lk.group(2) or lk.group(1)).strip()})
            dist = None
    return rows


def pr_wikitable(text, notes):
    sec = section(text, r"比例区当選者")
    i = sec.find("{|")
    leg = legend(sec[:i])
    leg.update(FIX_COLOR)
    table = strip_refs(sec[i:sec.find("\n|}", i)])
    parts = table.split("\n|-")
    blocks = [b if b != "北海道" else "北海道" for b in re.findall(r"\[\[比例(\S+?)ブロック\|", parts[0])]
    rows = []
    for row in parts[1:]:
        m = re.search(r"^\s*!\s*(\d+)", row)
        if not m:
            continue
        order = int(m.group(1))
        cells = []
        for c in row.split("\n"):
            if c.startswith("|") and not c.startswith("|}"):
                cells += c[1:].split("||")
        for blk, c in zip(blocks, cells):
            bm = BG.search(c)
            lk = LINK.search(c)
            if bm and lk:
                party = _with_color(leg, bm.group(1), f"比例{blk}{order}", notes)
                rows.append({"kind": "比例", "block": blk, "order": order, "party": party,
                             "article": lk.group(1).strip(), "name": (lk.group(2) or lk.group(1)).strip()})
            elif c.strip() and not lk and ("不足" in c or "border" in c):
                notes.append(f"比例{blk}の{order}番目は「{re.sub(r'.*\\|', '', c).strip()}」")
    return rows


FIX_COLOR = {}


def extract_old(text):
    """第49回までの書き方（{{衆議院小選挙区当選者(第49回まで)}} と {{衆議院当選者一覧(比例区)}}）を読む。"""
    rows, notes = [], []
    i = text.find("{{衆議院小選挙区当選者(第49回まで)")
    j = text.rfind("\n=", 0, i)
    body = template_body(text[i:], "衆議院小選挙区当選者(第49回まで)")
    leg = legend(text[j:i])
    leg.update(FIX_COLOR)
    ps = params(body)
    for key, val in ps.items():
        m = re.fullmatch(r"(.+?)(\d+)区", key)
        if not m:
            continue
        pref, k = m.group(1), int(m.group(2))
        lk = LINK.search(strip_refs(val))
        party = _with_color(leg, ps.get(key + "色", ""), key, notes)
        rows.append({"kind": "小選挙区", "pref": pref, "district": k, "party": party,
                     "article": lk.group(1).strip() if lk else None,
                     "name": (lk.group(2) or lk.group(1)).strip() if lk else strip_refs(val).strip(),
                     "_ref": val})
    if "{{衆院比例当選者" in text[i:]:
        pr_rows, pr_notes = _pr_new(text[i:])
        rows += pr_rows
        notes += pr_notes
    elif "{{衆議院当選者一覧(比例区)" not in text:
        rows += pr_wikitable(text, notes)
    else:
        i2 = text.find("{{衆議院当選者一覧(比例区)")
        j2 = text.rfind("\n=", 0, i2)
        leg2 = legend(text[j2:i2])
        ps2 = params(template_body(text[i2:], "衆議院当選者一覧(比例区)"))
        for key, val in ps2.items():
            m = re.fullmatch(r"(\D+?)(\d+)", key)
            if not m or m.group(1) not in OLD_BLOCK:
                continue
            lk = LINK.search(strip_refs(val))
            if not lk:
                notes.append(f"比例{OLD_BLOCK[m.group(1)]}の{m.group(2)}番目は「{strip_refs(val).strip()}」")
                continue
            party = _with_color(leg2, ps2.get(key + "色", ""), "比例" + key, notes)
            rows.append({"kind": "比例", "block": OLD_BLOCK[m.group(1)], "order": int(m.group(2)), "party": party,
                         "article": lk.group(1).strip(), "name": (lk.group(2) or lk.group(1)).strip(), "_ref": val})
    return rows, notes


def _pr_new(text):
    rows, notes = [], []
    pr = section(text, r"比例区当選者") or text
    i = pr.find("{{衆院比例当選者")
    leg2 = legend(pr[:i] if i > 0 else pr)
    ps2 = params(template_body(pr, "衆院比例当選者"))
    for blk in BLOCKS:
        order = 0
        for color, art, name in lines(ps2.get(blk, "")):
            order += 1
            if art is None:
                notes.append(f"比例{blk}の{order}番目は「{name}」（{leg2.get(color, color)}）")
                continue
            party = _with_color(leg2, color, f"比例{blk} {name}", notes)
            rows.append({"kind": "比例", "block": blk, "order": order, "party": party, "article": art, "name": name})
    return rows, notes


def extract(text, fix=None):
    FIX_COLOR.clear()
    FIX_COLOR.update(fix or {})
    if "{{衆議院小選挙区当選者(第49回まで)" in text:
        rows, notes = extract_old(text)
    elif "{{衆院小選挙区当選者" not in text:
        notes = []
        rows = smd_wikitable(text, notes) + pr_wikitable(text, notes)
    else:
        rows, notes = extract_new(text)
    out = []
    for r in rows:
        p, extra = canon(r["party"])
        r["party"] = p
        if extra:
            r["party_note"] = extra
        out.append(r)
    return out, notes


def extract_new(text):
    rows, notes = [], []
    smd = section(text, r"小選挙区当選者")
    if smd is None or "{{衆院小選挙区当選者" not in smd:
        i = text.find("{{衆院小選挙区当選者")
        j = text.rfind("\n=", 0, i)
        smd = text[j:i] + template_body(text[i:], "衆院小選挙区当選者")
        notes.append("小選挙区の表は見出しの外にあったので、表の直前の凡例を使った")
    leg = legend(smd)
    body = template_body(smd, "衆院小選挙区当選者")
    ps = params(body)
    for pref in PREFS:
        if pref not in ps:
            raise ValueError("小選挙区の表に県がない: " + pref)
        for k, (color, art, name) in enumerate(lines(ps[pref]), start=1):
            if color not in leg and color[:3] in leg:
                notes.append(f"{pref}{k}区 {name}：記事の色指定「{color}」を「{color[:3]}」と読んだ")
                color = color[:3]
            if color not in leg:
                raise ValueError(f"凡例にない色 {color} ({pref}{k}区 {name})")
            rows.append({"kind": "小選挙区", "pref": pref, "district": k, "party": leg[color],
                         "article": art, "name": name})
    pr = section(text, r"比例区当選者")
    leg2 = legend(pr)
    ps2 = params(template_body(pr, "衆院比例当選者"))
    for blk in BLOCKS:
        order = 0
        for color, art, name in lines(ps2.get(blk, "")):
            order += 1
            if art is None:
                notes.append(f"比例{blk}の{order}番目は「{name}」（{leg2.get(color, color)}）")
                continue
            if color not in leg2 and color[:3] in leg2:
                notes.append(f"比例{blk} {name}：記事の色指定「{color}」を「{color[:3]}」と読んだ")
                color = color[:3]
            if color not in leg2:
                raise ValueError(f"凡例にない色 {color} (比例{blk} {name})")
            rows.append({"kind": "比例", "block": blk, "order": order, "party": leg2[color],
                         "article": art, "name": name})
        seats = re.sub(r"\D", "", ps2.get(blk + "定数", ""))
        got = sum(1 for r in rows if r.get("block") == blk)
        if seats and int(seats) != got:
            notes.append(f"比例{blk}：定数{seats}に対し当選者{got}人")
    return rows, notes


def summary_table(text):
    """記事の「党派別当選者内訳」の表から {党派: 計} を読む（検証用）。"""
    sec = section(text, r"党派別当選者内訳")
    if not sec:
        return {}
    out = {}
    for row in strip_refs(sec).split("\n|-"):
        m = re.search(r'align="left"\s*\|\s*(?:\[\[(?:[^\]|]*\|)?([^\]]+)\]\]|([^\n|]+))', row)
        n = re.search(r"'''(\d+)'''", row)
        if m and n:
            name = (m.group(1) or m.group(2)).strip()
            out[canon(name)[0]] = out.get(canon(name)[0], 0) + int(n.group(1))
    return out
