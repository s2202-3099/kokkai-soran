"""選挙記事の「繰上当選」の表から、任期中の欠員と繰上当選を取り出す。"""
import re

from winners import strip_refs

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
REASON = re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\s*(辞職|死去|退職|失職|除名|自動失職)")


def extract(text):
    m = re.search(r"^=+\s*繰上当選[^=\n]*=+\s*$", text, re.M)
    if not m:
        return []
    end = text.find("\n|}", m.end())
    table = strip_refs(text[m.end():end])
    out = []
    for row in table.split("\n|-")[1:]:
        rm = REASON.search(row)
        if rm:
            date, reason = f"{int(rm[1]):04d}-{int(rm[2]):02d}-{int(rm[3]):02d}", rm[4]
        else:
            ym = re.search(r"(\d{4})年\s*(\d{1,2})月", row)
            if not ym:
                continue
            date = f"{int(ym[1]):04d}-{int(ym[2]):02d}"
            last = re.split(r"\|\||\n\|", row.strip())[-1].strip()
            reason = "辞職" if "辞職" in last else ("死去" if "死去" in last else last or "不明")
        blk = re.search(r"^!\s*([^\n|]+)$", row, re.M)
        cells = [c for c in re.split(r"\n\||\|\|", row)]
        links = [(m.group(1).strip(), (m.group(2) or m.group(1)).strip()) for m in LINK.finditer(row)
                 if not re.search(r"ブロック|選挙区|党|会$|^\d", m.group(1))]
        vacant = "（欠員）" in row
        if vacant:
            new = None
            # 欠員者は表の最後の人名セル（リンクのない場合もある）
            names = [re.sub(r"^.*\|\s*", "", c).strip() for c in cells if "background-color" in c]
            old = links[-1] if links else (None, names[-1] if names else "")
        else:
            new, old = (links[0] if links else None), (links[1] if len(links) > 1 else (None, ""))
        out.append({"date": date, "reason": reason, "block": blk.group(1).strip() if blk else "",
                    "new_article": new[0] if new else None, "new_name": new[1] if new else None,
                    "old_article": old[0], "old_name": old[1]})
    return out
