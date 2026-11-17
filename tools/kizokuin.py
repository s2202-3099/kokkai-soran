"""貴族院議員の記事から、議員の種別と在職期間を読む。

貴族院には選挙区も総選挙もなく、種別ごとに議員になる道と任期が違う。
- 皇族議員：成年の皇族男子。終身（1946年5月23日に全員が辞任）。
- 公爵議員・侯爵議員：満25歳（1925年から満30歳）で自動的に議員。終身。
- 伯爵議員・子爵議員・男爵議員：同じ爵位の華族の互選。任期7年（1890年から7年ごとの7月10日）と補欠選挙。
- 勅選議員：内閣の奏薦で勅任。終身。
- 帝国学士院会員議員：会員の互選（1925年〜）。任期7年。
- 多額納税者議員：府県ごとの高額納税者の互選。任期7年。
- 朝鮮勅選議員・台湾勅選議員：1945年4月〜1946年7月。
どの種別も、貴族院の廃止（1947年5月2日）で終わる。

読むところは二つ。
1. 記事の分類（Category:貴族院○○議員、○○県選出の貴族院多額納税者議員）→ 種別。
2. 情報欄の「職名 = 貴族院議員」の就任日・退任日 → 在職期間。情報欄になければ本文の決まった書き方から拾う。
"""
import re

ABOLISHED = "1947-05-02"
KINDS = ["皇族議員", "公爵議員", "侯爵議員", "伯爵議員", "子爵議員", "男爵議員", "勅選議員", "帝国学士院会員議員",
         "多額納税者議員", "朝鮮勅選議員", "台湾勅選議員"]
LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
ERA = {"明治": 1867, "大正": 1911, "昭和": 1925}


def strip(s):
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\{\{(?:R|Sfn|sfn|efn|Efn|Refnest)[^{}]*\}\}", "", s)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = LINK.sub(lambda m: m.group(2) or m.group(1), s)
    # 「昭和21年（1946年）7月9日」「明治43年〈1910年〉8月2日」→ 西暦に
    s = re.sub(r"(?:明治|大正|昭和|嘉永|安政|万延|文久|元治|慶応|天保|弘化|文政)\s*(?:\d+|元)\s*年\s*[〈（(]\s*(\d{4})年\s*[）)〉]", r"\1年", s)
    return re.sub(r"[〈（(](?:明治|大正|昭和)\s*(?:\d+|元)\s*年[）)〉]", "", s)


def kinds(text):
    """記事の分類から種別。多額納税者議員は選出の府県も返す。"""
    out, pref = [], ""
    for c in re.findall(r"\[\[Category:([^\]|]+)", text):
        c = c.strip()
        m = re.fullmatch(r"(.+?)選出の貴族院多額納税者議員", c)
        if m:
            pref = m.group(1)
            if "多額納税者議員" not in out:
                out.append("多額納税者議員")
        m = re.fullmatch(r"貴族院(.+議員)", c)
        if m and m.group(1) in KINDS and m.group(1) not in out:
            out.append(m.group(1))
    return out, pref


def _dates(s, year=None):
    """文字列の中の日付を順に (ISO, 位置)。年のない「5月2日」は直前の年を引き継ぐ。月までなら YYYY-MM。"""
    out = []
    for m in re.finditer(r"(?:(\d{4})年)?\s*(\d{1,2})月(?:\s*(\d{1,2})日)?|(\d{4})年", s):
        if m.group(4):
            year = int(m.group(4))
            out.append((f"{year:04d}", m.start()))
            continue
        if m.group(1):
            year = int(m.group(1))
        if not year:
            continue
        iso = f"{year:04d}-{int(m.group(2)):02d}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
        if out and out[-1][0] == f"{year:04d}" and m.group(1):
            pass
        out.append((iso, m.start()))
    # 「1946年」単独の直後に同じ年の月日が続くものは、年だけの項を落とす
    return [d for i, d in enumerate(out) if not (len(d[0]) == 4 and i + 1 < len(out) and out[i + 1][0].startswith(d[0])
                                                 and out[i + 1][1] - d[1] < 8)]


def infobox_spans(text):
    """情報欄の「貴族院議員」の欄から [(始まり, 終わり, 選挙区欄の文字)]。"""
    head = text[:lead_pos(text)] or text[:8000]
    f = {}
    for m in re.finditer(r"^\s*\|\s*([^=|\n]+?)\s*=[ \t]*([^\n]*)", head, re.M):
        f.setdefault(m.group(1).strip(), m.group(2).strip())
    out = []
    for k, v in f.items():
        m = re.fullmatch(r"(?:職名|その他職歴)(\d*)", k)
        if m and k.startswith("その他"):
            # その他職歴N の就任日は通し番号が別（職名の数＋N）。同じ欄の並びで次に出る就任日を取る
            pos = head.find(k)
            mm = re.search(r"就任日(\d+)\s*=", head[pos:])
            m = re.fullmatch(r"(\d*)", mm.group(1)) if mm and "貴族院" in v else None
        if not m or "貴族院" not in v and "議員" not in f.get("選挙区" + m.group(1), ""):
            continue
        if "貴族院" not in v and not re.search(r"勅選議員|爵議員|多額納税|学士院会員議員|皇族議員", f.get("選挙区" + m.group(1), "")):
            continue
        if re.search(r"議長|書記官|事務局", strip(v)) and "議員" not in strip(v):
            continue
        n = m.group(1)
        s_raw, e_raw = strip(f.get("就任日" + n, "")), strip(f.get("退任日" + n, ""))
        area = strip(f.get("選挙区" + n, ""))
        # 就任日・退任日の欄に <br> や <hr> で複数の期間が並ぶ書き方
        parts_s = re.split(r"<br\s*/?>|<hr\s*/?>", s_raw)
        parts_e = re.split(r"<br\s*/?>|<hr\s*/?>", e_raw)
        spans = []
        if len(parts_s) == 1 and len(parts_e) == 1:
            ds, de = _dates(s_raw), _dates(e_raw, int(ds[0][0][:4]) if (ds := _dates(s_raw)) else None)
            if len(ds) == 2 and not de:
                spans.append((ds[0][0], ds[1][0]))
            else:
                spans.append((ds[0][0] if ds else "", de[-1][0] if de else ""))
        else:
            # 「A - B<br>C」＋「D」＝ [A,B] と [C,D]
            lines = []
            for p in parts_s:
                d = _dates(p)
                lines.append([x[0] for x in d])
            tail = _dates(parts_e[-1], None)
            for p in parts_e[:-1]:
                d = _dates(p)
                lines.append([x[0] for x in d])
            for i, d in enumerate(lines):
                if len(d) >= 2:
                    spans.append((d[0], d[1]))
                elif len(d) == 1:
                    spans.append((d[0], tail[-1][0] if tail and i == len(parts_s) - 1 else ""))
        for s, e in spans:
            out.append((s, e, area))
    return out


START_W = r"勅選|勅任|就任|当選|互選|選出|選任|補欠|議員と|議員に|任命|任じ|貴族院議員|皇族議員|爵議員|納税者議員"
END_W = r"辞職|辞任|退任|まで|失職|資格消滅|資格が消滅|免|廃止|辞す|退職|にかけて"
# 貴族院議員になったことを言う語（日付の後ろ45字以内にあれば就任の日付とみる）
BECAME = r"貴族院[^、。（）]{0,14}議員|勅選|皇族議員|爵議員|納税者議員|学士院会員議員|議員に(?:勅選|就任|互選|当選|任)|議員補欠選挙|議員となる|議員となり|議員となった"
OTHER_JOB = r"市長|知事|大臣|長官|総裁|社長|会長|次官|局長|頭取|総長|学長|理事|顧問官|町長|村長|書記官|院長|校長|教授|検事|判事"
DATE_RE = re.compile(r"(?:(\d{4})年|(同年))?\s*(?:(\d{1,2})月|(同月))\s*(?:(\d{1,2})日)?|(\d{4})年|(?<=[（、 ])(\d{1,2})日")


def _scan(sent, ctx):
    """文の中の日付を順に [(ISO, 始まり位置, 終わり位置)]。

    「同年」「同月」、年のない月日、月のない「（22日」は文脈（ctx=[年, 月]）で補う。
    """
    out = []
    for m in DATE_RE.finditer(sent):
        if m.group(7):
            if ctx[0] and ctx[1]:
                out.append((f"{ctx[0]:04d}-{ctx[1]:02d}-{int(m.group(7)):02d}", m.start(), m.end()))
            continue
        if m.group(6):
            ctx[0], ctx[1] = int(m.group(6)), None
            out.append((f"{ctx[0]:04d}", m.start(), m.end()))
            continue
        if m.group(1):
            ctx[0] = int(m.group(1))
        if not ctx[0]:
            continue
        if m.group(3):
            ctx[1] = int(m.group(3))
        elif not ctx[1]:
            continue
        if m.group(4) and not m.group(5):
            continue   # 「同月」だけ
        iso = f"{ctx[0]:04d}-{ctx[1]:02d}" + (f"-{int(m.group(5)):02d}" if m.group(5) else "")
        out.append((iso, m.start(), m.end()))
    return out


def lead_pos(text):
    """記事の冒頭の一文（太字の名前（よみ、生没年）は…）の始まり。情報欄の中の太字は飛ばす。"""
    for m in re.finditer("'''", text):
        ls = text.rfind("\n", 0, m.start()) + 1
        line = text[ls:m.start()]
        if line.lstrip().startswith(("|", "!")) or "=" in line:
            continue
        return m.start()
    return max(text.find("'''"), 0)


def text_spans(text, death=""):
    """本文から在職期間 [(始まり, 終わり)] を拾う（情報欄にないとき）。

    貴族院議員の語のある文（と、その次の文）の日付を、前後の語で就任・退任に振り分ける。
    「AからBまで」「A - B」「（〜B）」「互選（6月24日）」「死去するまで在任」「貴族院廃止まで」も読む。
    """
    body = strip(text[lead_pos(text):])
    body = re.split(r"==\s*(?:脚注|注釈|出典|参考文献|関連項目|親族|家族|系譜|栄典|著書|著作)", body)[0]
    m0 = re.search(r"。", body)
    body = body[m0.end():] if m0 else body   # 冒頭の一文（生没年と肩書き）は読まない
    events = []   # (日付, "s"|"e")
    ctx = [None, None]
    carry = 0
    for sent in re.split(r"[。\n]", body):
        hit = bool(re.search(r"貴族院|皇族議員|勅選議員|爵議員|多額納税者議員", sent))
        ds = _scan(sent, ctx)
        if not hit:
            if carry and re.search(r"まで(?:在任|在職|務め)|議員を辞(?:職|任)|議員辞(?:職|任)|免.{0,4}議員|議員[^、]{0,6}(?:資格|失職)", sent) \
                    and not re.search(OTHER_JOB, sent):
                for d, a, b in ds:
                    if re.search(END_W, sent[b:b + 30]):
                        events.append((d, "e"))
            carry = max(carry - 1, 0)
            continue
        carry = 1
        if re.match(r"\s*[*＊:：]*\s*(?:祖父|曾祖父|父|実父|養父|兄|弟|岳父|義父|長男|二男|次男|三男|四男|叔父|伯父|甥|孫|女婿|娘婿|妻|母|長女|二女|三女|従兄)\s*[・：:、-]", sent):
            continue   # 親族の欄
        if re.search(r"死去するまで|死去まで|薨去まで|薨去するまで|没するまで|逝去するまで|亡くなるまで|在任中に死去|在職中に死去", sent) and death:
            events.append((death, "e"))
        if re.search(r"(?:貴族院|華族制度|同院|制度)(?:が|の)?廃止|廃止されるまで|廃止まで", sent) and not re.search(r"\d日[^、。]{0,12}廃止", sent):
            events.append((ABOLISHED, "e"))
        for i, (d, a, b) in enumerate(ds):
            nxt = ds[i + 1][1] if i + 1 < len(ds) else len(sent)
            prev_end = ds[i - 1][2] if i else 0
            seg, before = sent[b:nxt], sent[prev_end:a]
            paren = re.search(r"[（(]\s*$", before)            # 「…に互選（6月24日」：手前の語で決める
            lead_words = before[-30:] if paren else ""
            if re.search(r"[〜～~\-–－―]\s*$", before) and i:   # 「A - B」「（〜B）」のB
                events.append((d, "e"))
                continue
            if re.match(r"\s*(?:から|より|以降|[〜～~\-–－―])", seg) and (i + 1 < len(ds) or re.search(r"まで|廃止", seg)):
                events.append((d, "s"))
                continue
            if re.match(r"\s*(?:まで|にかけて|に?辞職|に?辞任|に?退任|付で辞|、?貴族院議員を?辞|、?議員を?辞|\s*[-－–]\s*(?:免|貴族院議員辞|議員辞))", seg):
                events.append((d, "e"))
                continue
            if paren and re.search(r"辞職|辞任|退任|失職|消滅|免", lead_words[-14:]):
                events.append((d, "e"))
                continue
            if paren and re.search(BECAME, lead_words):
                events.append((d, "s"))
                continue
            head45 = seg[:45]
            m_end = re.search(END_W, head45)
            m_st = re.search(BECAME, head45)
            # 「4月17日に貴族院議員を辞職」「貴族院廃止により貴族院議員失職」「貴族院議員の資格が消滅」
            if m_st and re.match(r"[^、。]{0,8}?(?:辞職|辞任|退任|辞し|失職|資格)", seg[m_st.end():m_st.end() + 14]):
                events.append((d, "e"))
                continue
            if re.search(r"臣籍降下|皇籍離脱|皇族の身分を離", sent) and re.search(r"資格|退任|失職|消滅", sent) and i == len(ds) - 1:
                events.append((d, "e"))
                continue
            if m_end and (not m_st or m_end.start() < m_st.start()) and re.search(r"議員|在任|在職", sent):
                if re.search(OTHER_JOB, head45[:m_end.start()]):
                    continue
                events.append((d, "e"))
                continue
            if m_st and not re.search(r"書記官|守衛|事務局|の(?:長男|二男|三男|子|養子|弟|孫)", head45[:m_st.end() + 6]):
                events.append((d, "s"))
    # 年だけ・月までの日付は、同じ年・月の詳しい日付があれば捨てる
    def sharpen(xs):
        xs = sorted(set(xs))
        return [x for x in xs if not (len(x) < 10 and any(y != x and y.startswith(x) for y in xs))]
    events = [(d, "e" if d == ABOLISHED else k) for d, k in events]   # 廃止の日は終わり
    starts = sharpen([d for d, k in events if k == "s"])
    ends = sharpen([d for d, k in events if k == "e"])
    spans = []
    for i, st in enumerate(starts):
        nxt = starts[i + 1] if i + 1 < len(starts) else "9999"
        e = next((x for x in ends if st[:len(x)] <= x and x[:len(nxt)] <= nxt and x != st), "")
        if e and e[:len(nxt)] == nxt[:len(e)] and e != nxt and len(e) < 10:
            pass
        spans.append((st, e))
    return spans


def death_date(text):
    m = re.search(r"死没年月日と没時年齢\|\d+\|\d+\|\d+\|(\d+)\|(\d+)\|(\d+)", text)
    if not m:
        lead = strip(text[lead_pos(text):][:1500])
        lead = re.sub(r"[〈（(][^（）()〈〉\-–－―ー〜~]{0,30}[）)〉]", "", lead)   # （文久3年3月20日）などの旧暦・和暦
        m = re.search(r"[-–－―ー〜~]\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", lead[:400])
    if not m:
        m = re.search(r"\|\s*(?:没年月日|死没日|死没)\s*=[^\n]*?(\d{4})年[^\n|]*?(\d{1,2})月\s*(\d{1,2})日", strip(text[:8000]))
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def parse(title, text):
    """一人分：{kinds, pref, spans:[(始まり,終わり,種別の手がかり)], src:'infobox'|'text'|'', death}"""
    ks, pref = kinds(text)
    death = death_date(text)
    spans = infobox_spans(text)
    src = "infobox" if spans else ""
    tspans = text_spans(text, death)
    if not spans:
        spans = [(a_, b_, "") for a_, b_ in tspans]
        src = "text" if spans else ""
    else:
        # 情報欄に退任日がないとき、本文の同じ始まりの期間で補う
        fixed = []
        for s_, e_, area in spans:
            if s_ and not e_:
                e_ = next((b_ for a_, b_ in tspans if b_ and a_[:7] == s_[:7]), "")
            fixed.append((s_, e_, area))
        spans = fixed
    return {"title": title, "kinds": ks, "pref": pref, "spans": spans, "src": src, "death": death}
