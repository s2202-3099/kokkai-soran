"""第1回参議院議員通常選挙（1947年）の地方区の当選者表を読む。

この回だけ表の形が違う。各選挙区の見出し（rowspan=2）の右に、上段は当選（任期6年）、下段は補欠当選（任期3年）が並び、
一つの行に二つの選挙区が並ぶこともある。格子に広げて、各セルの左にある最も近い見出しの選挙区とし、
その見出しが上の行から続いているもの（下段）を任期3年とする。全国区は 1〜50位が任期6年、51〜100位が任期3年。
"""
import re

import chusenkyo
import winners
from wtable import tables

LINK = re.compile(r"\[\[([^\]|#]+)(?:\|([^\]]+))?\]\]")
BG = re.compile(r"background(?:-color)?\s*:\s*(#[0-9A-Fa-f]{3,6})")


def chiho(text):
    i = text.find("=== 地方区当選者 ===")
    j = text.find("\n=== ", i + 10)
    sec = text[i:j]
    leg = {chusenkyo._norm_color(c): n for c, n in winners.legend(sec).items()}
    rows = []
    for _, tab in tables(sec):
        for cells in chusenkyo._grid(tab):
            pref, lower = None, False
            for h, a, c, rep in cells:
                if h:
                    lk = LINK.search(c)
                    if lk and "選挙区" in lk.group(1):
                        pref = lk.group(1).replace("選挙区", "").strip()
                        pref = pref if pref == "北海道" else re.sub(r"(都|府|県)$", "", pref)
                        lower = rep
                    continue
                if rep or not pref:
                    continue
                lk = LINK.search(chusenkyo.strip_refs(c))
                if not lk:
                    continue
                m = BG.search(a or "")
                party = leg.get(chusenkyo._norm_color(m.group(1))) if m else None
                rows.append({"kind": "選挙区", "pref": pref, "party": winners.canon(party)[0] if party and party != "無所属" else "無所属",
                             "article": lk.group(1).strip(), "name": (lk.group(2) or lk.group(1)).strip(),
                             "short": lower, "tokutei": False, "note": "補欠（任期3年）" if lower else "", "party_note": ""})
    return rows


def _date(s):
    m = re.match(r"\s*(\d{4})\.(\d{1,2})\.(\d{1,2})", s)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    return ""   # 年だけの行（「1947失職」）は日が分からないので空にし、本人の記事か SAN_VACANCY_DATE で補う


def hosen(text):
    """「補欠当選」の表（年・月日・選挙区・当選者・党派・欠員・党派・欠員事由）。月日が「-」の行は補選のない欠員。"""
    i = text.find("==== 補欠当選")
    j = text.find("\n=== ", i + 5)
    sec = text[i:j]
    out = []
    for _, tab in tables(sec):
        for cells in chusenkyo._grid(tab):
            if len(cells) < 8 or cells[0][0]:
                continue
            vals = [c for _, _, c, _ in cells[-8:]]
            yr, md, dist, win, wparty, old, oparty, why = [chusenkyo.strip_refs(v).strip() for v in vals]
            if not re.match(r"\d{4}", yr):
                continue
            lo = LINK.search(old)
            if not lo:
                continue
            lw = LINK.search(win)
            reason = next((k for k in ("死去", "辞職", "失職", "退職") if k in why), "")
            dm = re.match(r"(\d{1,2})\.(\d{1,2})", md)
            out.append({"date": f"{int(yr):04d}-{int(dm[1]):02d}-{int(dm[2]):02d}" if dm else "",
                        "kind": "補欠選挙" if lw and dm else "未実施", "district": re.sub(r"<[^>]+>", "", dist).strip(),
                        "winner_article": lw.group(1).strip() if lw else None, "winner_name": (lw.group(2) or lw.group(1)).strip() if lw else None,
                        "winner_party": re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", wparty).strip() if lw else "",
                        "old_party": re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", oparty).strip(),
                        "old_article": lo.group(1).strip(), "old_name": (lo.group(2) or lo.group(1)).strip(),
                        "vacated_date": _date(why), "reason": reason})
    return out
