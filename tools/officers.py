"""歴代の一覧の記事（自由民主党幹事長、参議院議長など）と、候補者の記事の情報欄から、ある日の在任者を決める。

一覧の表は年・月までしか書かれていないことが多いので、まず一覧でその年にかかる人を候補にし、
候補者の記事の情報欄の就任日・退任日でその日に在任していたかを確かめる。
"""
import re

import person
import wtable

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def candidates(text):
    """一覧の表の行ごとに (記事名, 表示名, 始まりの年, 終わりの年)。"""
    out = []
    for _, tb in wtable.tables(text):
        for row in wtable.grid(tb):
            cells = [c[1] for c in row]
            names = []
            for c in cells:
                for m in LINK.finditer(c):
                    t = m.group(1)
                    if re.match(r"(?:ファイル|File|file|画像|Image)\s*:", t) or re.search(r"\d|派|会$|内閣|党|選挙|研究", t):
                        continue
                    names.append((t.strip().replace("_", " "), (m.group(2) or t).strip()))
                    break
                if names:
                    break
            if not names:
                continue
            joined = " ".join(cells)
            years = [int(y) for y in re.findall(r"(1[89]\d\d|20\d\d)年", joined)]
            if not years:
                continue
            last = 9999 if "現職" in joined or "現在" in joined else max(years)
            out.append((names[0][0], names[0][1], min(years), last))
    return out


def at(day, text, label, article_of):
    """day に label に在任していた人。返り値は (記事名, 根拠, 説明) または None。
    article_of(記事名) は情報欄を含む記事の本文を返す（なければ None）。"""
    y = int(day[:4])
    cands = [c for c in candidates(text) if c[2] <= y <= c[3]]
    seen, uniq = set(), []
    for c in cands:
        if c[0] not in seen:
            seen.add(c[0])
            uniq.append(c)
    hits = []
    for art, shown, a, b in uniq:
        t = article_of(art)
        if not t:
            continue
        for s, e in person.post_tenure(person.infobox(t), label):
            if s[:10] <= day <= (e if len(e) == 10 else e + "-99"):
                hits.append((art, "art", f"本人の記事の情報欄（{s}〜{'' if e == '9999' else e}）"))
                break
    if len(hits) == 1:
        return hits[0]
    if not hits and len(uniq) == 1 and uniq[0][2] < y < uniq[0][3]:  # 一覧だけで決めるのは、その年が任期の途中のときだけ
        return (uniq[0][0], "doc", f"歴代一覧（{uniq[0][2]}〜{uniq[0][3] if uniq[0][3] != 9999 else ''}年）")
    return None if not hits else ("?", "", "候補が複数：" + "、".join(h[0] for h in hits))
