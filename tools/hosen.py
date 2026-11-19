"""選挙記事の「補欠選挙」の表から、補選の当選者と欠員になった議員を取り出す。

衆院選の記事の表は「年・月日・選挙区・新旧別・当選者・当選政党・欠員・欠員政党・欠員事由」、
参院選の記事の表は、これに「選出」（補欠選挙・再選挙）の列が加わる。
補選をせずに欠員のまま解散・任期満了を迎えた行（「未実施」「実施せず」）も、欠員として返す。
"""
import re

from winners import strip_refs

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
REASON = re.compile(r"(\d{4})[.年](\d{1,2})[.月](\d{1,2})日?\s*([^\n|{<]*)")
REASONS = ("自動失職", "当選無効", "選挙無効", "応召", "辞職", "死去", "退職", "失職", "除名", "辞任")


def _cells(row):
    """表の1行をセルの並びにする（属性は落とす）。"""
    return [(h, c) for h, c, _ in _cells_rs(row)]


def _cells_rs(row):
    """表の1行を (見出しか, 中身, rowspan) の並びにする。"""
    out = []
    for line in row.split("\n"):
        line = line.strip()
        if not line or line[0] not in "|!":
            continue
        head = line[0]
        for c in re.split(r"\|\||!!", line[1:]):
            # 属性（引用符あり・なしが混ざってもよい：「align="right" rowspan=2 | 5.10」）
            attr = re.match(r"\s*((?:[a-z-]+\s*=\s*(?:\"[^\"]*\"|[^|\s\"]+)\s*)+)\|(?!\|)", c)
            rs = 1
            if attr and not c.lstrip().startswith("[["):
                m_ = re.search(r"rowspan\s*=\s*\"?(\d+)", attr.group(1))
                rs = int(m_.group(1)) if m_ else 1
                c = c[attr.end():]
            out.append((head, c.strip(), rs))
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
    out, year, prev_held = [], None, False
    pend_kind, pend_dist = None, None   # 行をまたぐ（rowspan の）「選出」と「選挙区」のセル：[中身, 残りの行数]
    pend_why = None                     # 行をまたぐ「欠員事由」のセル（第10回の「rowspan="2" | 1909.7.3選挙法第11条該当」）
    for row in table.split("\n|-")[1:]:
        rcells = _cells_rs(row)
        cells = [(h, c) for h, c, _ in rcells]
        kind_here = dist_here = why_here = None
        for h_, c_, rs_ in rcells:
            if rs_ > 1 and h_ == "|" and REASON.search(c_):
                why_here = (c_, rs_)
            if rs_ > 1 and h_ == "!" and dist_here is None:
                dist_here = (_plain(c_), rs_)
            elif rs_ > 1 and h_ == "|" and re.fullmatch(r"[^\[\]]{0,8}(選挙|当選|補欠|再|補充|復職|更正決定)", _plain(c_)):
                kind_here = (_plain(c_), rs_)
        use_kind = pend_kind[0] if pend_kind and pend_kind[1] > 0 and not kind_here else None
        use_dist = pend_dist[0] if pend_dist and pend_dist[1] > 0 and not dist_here else None
        if pend_kind:
            pend_kind[1] -= 1
        if pend_dist:
            pend_dist[1] -= 1
        use_why = pend_why[0] if pend_why and pend_why[1] > 0 and not why_here else None
        if pend_why:
            pend_why[1] -= 1
        if why_here:
            pend_why = [why_here[0], why_here[1] - 1]
        if kind_here:
            pend_kind = [kind_here[0], kind_here[1] - 1]
        if dist_here:
            pend_dist = [dist_here[0], dist_here[1] - 1]
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
        elif i < len(cells) and cells[i][0] == "|" and re.fullmatch(r"[-－‐ー]", cells[i][1]):
            i += 1  # 未実施の行の「-」だけの月日
        cont = False
        if (i >= len(cells) or cells[i][0] != "!") and use_dist and (md or out):
            # 選挙区のセルが上の行から続いている行（「! rowspan="2" | 広島県郡部」の二行目）
            cells = cells[:i] + [("!", use_dist)] + cells[i:]
        if i >= len(cells) or cells[i][0] != "!":
            # 選挙区の見出しセルがない行（同じ日の続き）は、前の日付を使う
            if out and md is None and cells and cells[0][0] == "!":
                i = 0
            elif out and md is None and cells and _plain(cells[0][1]) in ("新", "前", "元", "現") and prev_held:
                cont = True   # 同じ選挙区で二人が当選した補欠選挙の二行目（年・月日・選挙区・選出のセルが上の行と共通）
            else:
                continue
        if md:
            last_date = f"{year:04d}-{int(md.split('.')[0]):02d}-{int(md.split('.')[1]):02d}"
        elif out and i == 0:
            last_date = out[-1]["date"]
        else:
            last_date = ""
        if cont:
            district, kind, last_date = out[-1]["district"], out[-1]["kind"], out[-1]["date"]
            rest = [c for _, c in cells]
        else:
            district = _plain(cells[i][1])
            rest = [c for _, c in cells[i + 1:]]
            kind = "補欠選挙"
            p0 = _plain(rest[0]) if rest else ""
            if rest and p0 not in ("新", "前", "元", "現") and re.fullmatch(r"[^\[\]]{0,8}(選挙|当選|補欠|再|補充|復職|更正決定)", p0):
                kind = {"補欠": "補欠選挙", "再": "再選挙"}.get(p0, p0)   # 「[[第16回…|合併選挙]]」のようなリンクも。「復職」は応召した議員の復帰
                rest = rest[1:]
            elif use_kind:
                kind = {"補欠": "補欠選挙", "再": "再選挙"}.get(use_kind, use_kind)   # 上の行から続く「選出」のセル
        ri = next((k for k in range(len(rest) - 1, -1, -1) if REASON.search(rest[k])), None)
        if ri is None and use_why:
            rest = rest + [use_why]   # 欠員事由のセルが上の行から続いている
            ri = len(rest) - 1
        if ri is None:
            continue
        rm = REASON.search(rest[ri])
        old = _person(rest[ri - 2]) if ri >= 2 else (None, None)
        held = ri >= 5 and not any(x in "".join(rest[:ri]) for x in ("未実施", "実施せず"))
        win = _person(rest[1]) if held and len(rest) > 1 else (None, None)
        wparty = _plain(rest[2]) if held and len(rest) > 2 else ""
        oparty = _plain(rest[ri - 1]) if ri >= 1 else ""
        prev_held = held
        out.append({"date": last_date if held else "", "kind": kind if held else "未実施",
                    "district": district,
                    "winner_article": win[0], "winner_name": win[1], "winner_party": wparty,
                    "old_party": oparty,
                    "old_article": old[0], "old_name": old[1],
                    "vacated_date": f"{int(rm[1]):04d}-{int(rm[2]):02d}-{int(rm[3]):02d}",
                    "reason": _reason(rest[ri][rm.start(4):])})
    return out


BULLET = re.compile(r"^\*\s*(\S+?)選挙区\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]（([^）]*)）\s*→\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]（([^）]*)）", re.M)


def bullets(text, heading=r"補欠当選"):
    """古い参院選の記事の、箇条書きの補欠当選（* 山口選挙区 [[江島淳]]（1987.5.25死去）→[[二木秀夫]]（1987.7.12補欠当選））。
    当選者の党派は書かれていないので空。欠員の日が書かれていない行（「知事選立候補による退職」）は vacated_date を空にする。"""
    m = re.search(r"^=+\s*" + heading + r"[^=\n]*=+\s*$", text, re.M)
    if not m:
        return []
    nxt = re.search(r"^=+[^=\n]+=+\s*$", text[m.end():], re.M)
    sec = text[m.end(): m.end() + (nxt.start() if nxt else len(text))]
    out = []
    for b in BULLET.finditer(strip_refs(sec)):
        why, won = b.group(4), b.group(7)
        rm, wm = REASON.search(why), REASON.search(won)
        out.append({"date": f"{int(wm[1]):04d}-{int(wm[2]):02d}-{int(wm[3]):02d}" if wm else "",
                    "kind": "再選挙" if "再選挙" in won else "補欠選挙", "district": b.group(1) + "県",
                    "winner_article": b.group(5).strip(), "winner_name": (b.group(6) or b.group(5)).strip(),
                    "winner_party": "", "old_party": "", "old_article": b.group(2).strip(),
                    "old_name": (b.group(3) or b.group(2)).strip(),
                    "vacated_date": f"{int(rm[1]):04d}-{int(rm[2]):02d}-{int(rm[3]):02d}" if rm else "",
                    "reason": _reason(why)})
    return out


SHU_BULLET = re.compile(r"^\*\s*(\S+?[都道府県])第(\d+)区\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]（([^）]*)）\s*→\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]（([^）]*)）", re.M)


def shu_bullets(text, heading=r"補欠当選"):
    """1889年の法の時代（第6回など）の衆院選の記事の、箇条書きの補欠当選
    （* 熊本県第3区 [[古荘嘉門]]（1899.6.3辞職）→[[犬飼真平]]（1899.6.29補欠当選））。
    当選者の党派は書かれていないので空。"""
    m = re.search(r"^=+\s*" + heading + r"[^=\n]*=+\s*$", text, re.M)
    if not m:
        return []
    nxt = re.search(r"^=+[^=\n]+=+\s*$", text[m.end():], re.M)
    sec = text[m.end(): m.end() + (nxt.start() if nxt else len(text))]
    out = []
    for b in SHU_BULLET.finditer(strip_refs(sec)):
        why, won = b.group(5), b.group(8)
        rm, wm = REASON.search(why), REASON.search(won)
        out.append({"date": f"{int(wm[1]):04d}-{int(wm[2]):02d}-{int(wm[3]):02d}" if wm else "",
                    "kind": "再選挙" if "再選挙" in won else "補欠選挙", "district": f"{b.group(1)}第{b.group(2)}区",
                    "winner_article": b.group(6).strip(), "winner_name": (b.group(7) or b.group(6)).strip(),
                    "winner_party": "", "old_party": "", "old_article": b.group(3).strip(),
                    "old_name": (b.group(4) or b.group(3)).strip(),
                    "vacated_date": f"{int(rm[1]):04d}-{int(rm[2]):02d}-{int(rm[3]):02d}" if rm else "",
                    "reason": _reason(why[rm.start(4):] if rm else why)})
    return out
