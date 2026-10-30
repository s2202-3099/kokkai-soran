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


def legend(section):
    """凡例 {{政党箱|党名}} / {{政党箱|色|党名}} から 色→党名 の対応を作る。"""
    out = {}
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
    nxt = re.search(r"^===?\s*[^=\n]+=+\s*$", text[m.end():], re.M)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


def extract(text):
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
