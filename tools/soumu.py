"""総務省の結果調「届出政党等別男女別新前元別当選人数」の表から、党派ごとの当選者数を読む。"""
import re

import pandas as pd


def party_totals(path):
    """{党派: {'小選挙区': n, '比例': n, '計': n}} を返す。"""
    out = {}
    for _, df in pd.read_excel(path, sheet_name=None, header=None).items():
        df = df.fillna("").astype(str).map(lambda s: re.sub(r"\s", "", s))
        n = len(df)
        r = 0
        while r < n:
            row = df.iloc[r]
            names = {c: row.iloc[c] for c in range(2, df.shape[1]) if row.iloc[c] and not re.fullmatch(r"[男女計0-9.]+", row.iloc[c])
                     and row.iloc[c] not in ("区分",)}
            if names and set(names.values()) <= {"本人･推薦届出", "合計", "小計"}:
                # 無所属の表は、党派名が一段下の行にある
                r += 1
                continue
            if names and not any(x in "".join(names.values()) for x in ("開票結果", "党派別男女別", "届出政党")):
                # 続く行で「計」の行を順に拾う（小選挙区・比例・合計）
                kei = []
                for rr in range(r + 1, min(r + 18, n)):
                    if df.iloc[rr, 1] == "計" or (df.iloc[rr, 0].endswith("計") and df.iloc[rr, 1] == ""):
                        kei.append(rr)
                    if len(kei) == 3:
                        break
                if len(kei) == 3:
                    for c, name in names.items():
                        col = c + 2  # 男・女・計 の「計」
                        vals = []
                        for rr in kei:
                            v = df.iloc[rr, col] if col < df.shape[1] else ""
                            vals.append(int(float(v)) if v else 0)
                        fv = df.iloc[kei[2], col - 1] if col - 1 < df.shape[1] else ""
                        women = int(float(fv)) if fv else 0
                        if name in ("合計", "小計"):
                            continue
                        if name == "政党等所属":
                            name = "本人届出（政党等所属）"
                        if any(vals):
                            d = out.setdefault(name, {"小選挙区": 0, "比例": 0, "計": 0, "女": 0})
                            d["女"] += women
                            d["小選挙区"] += vals[0]
                            d["比例"] += vals[1]
                            d["計"] += vals[2]
                    r = kei[-1] + 1
                    continue
            r += 1
    return out


VARIANTS = str.maketrans({"髙": "高", "﨑": "崎", "嵜": "崎", "邉": "辺", "邊": "辺", "齋": "斎", "齊": "斎", "濵": "浜",
                          "濱": "浜", "德": "徳", "惠": "恵", "眞": "真", "櫻": "桜", "澤": "沢", "廣": "広", "實": "実",
                          "會": "会", "國": "国", "壽": "寿", "藏": "蔵", "龍": "竜", "瀨": "瀬", "冨": "富", "鄕": "郷",
                          "隆": "隆", "博": "博", "淸": "清", "彥": "彦", "神": "神", "祐": "祐", "狹": "狭", "ッ": "ツ"})


def norm(name):
    return re.sub(r"[\s　]", "", name).translate(VARIANTS)


def smd_candidates(txt_path):
    """候補者別得票数（小選挙区）の PDF をテキストにしたものから、候補者の本名を {正規化した名前: 年齢} で返す。"""
    out = {}
    lines = open(txt_path, encoding="utf-8").read().split("\n")
    for i, line in enumerate(lines):
        for m in re.finditer(r"(?:^|\s)(?:当|落)\s+([^\d()（）]+?)\s+(?:[男女]\s+)?(\d{2,3})\s", line):
            nm = norm(m.group(1))
            if re.fullmatch(r"[\u3005\u4e00-\u9fff\uf900-\ufaff]{2,8}", nm):
                out.setdefault(nm, None)
        for m in re.finditer(r"[(（]([^()（）]{2,24})[)）]", line):
            nm = norm(m.group(1))
            if not re.fullmatch(r"[々぀-ヿ一-鿿豈-﫿A-Za-zー・]{2,12}", nm):
                continue
            out.setdefault(nm, None)
    return out
