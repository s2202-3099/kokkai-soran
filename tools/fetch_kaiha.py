"""参院議員の各版の投票日に近い発言の会派を、国会会議録検索システムの API から引く。

使い方: python3 tools/fetch_kaiha.py <data フォルダ> <出力する kaiha.json> [分割数 何番目]
- 対象は、衆院の各総選挙の投票日に在職していた参院議員（terms.csv から）。
- 投票日前1年の最後の発言の会派。それが60日より前なら、投票日後150日の最初の発言も引く。
- 大臣・副大臣・政務官・政務次官などとして話した発言は、会派欄が当てにならない（院の第一会派が入っている例がある）ので使わない。
- 本名で見つからなければ aliases.csv の別名と記事名で引き直す。
- 間隔を空けて引く（1件ごとに約1.2秒）。分割して並べて走らせるときは 3 0、3 1、3 2 のように指定し、できたファイルを merge で一つにする。
build.py は作業フォルダ（第2引数）の kaiha.json を読む。
"""
import csv, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import date, timedelta

API = "https://kokkai.ndl.go.jp/api/speech"
UA = "kokkai-soran/0.1 (https://github.com/s2202-3099/kokkai-soran)"
GOV = re.compile(r"大臣|次官|政務官|長官|補佐官|政府|参考人|議長")


def jobs(R):
    E = {r["election_id"]: r for r in csv.DictReader(open(f"{R}/elections.csv"))}
    P = {r["person_id"]: r for r in csv.DictReader(open(f"{R}/persons.csv"))}
    days = sorted(e["date"] for e in E.values() if e["house"] == "衆" and e["kind"] == "総選挙")
    out = []
    for D in days:
        for t in csv.DictReader(open(f"{R}/terms.csv")):
            if t["house"] == "参" and t["start_date"] <= D and (not t["end_date"] or t["end_date"] >= D):
                out.append((t["person_id"], P[t["person_id"]]["name"], D))
    return list(dict.fromkeys(out)), P


def q(name, a, b):
    url = API + "?" + urllib.parse.urlencode({"speaker": name, "nameOfHouse": "参議院", "from": a, "until": b,
                                               "maximumRecords": 100, "recordPacking": "json"})
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90) as r:
                j = json.load(r)
            time.sleep(1.2)
            return j
        except Exception:
            time.sleep(5 * (i + 1))
    return None


def pick(j, newest):
    recs = [r for r in (j or {}).get("speechRecord", []) if r.get("speakerGroup")]
    gov = [r for r in recs if r.get("speakerPosition") and GOV.search(r["speakerPosition"])]
    ok = sorted((r for r in recs if r not in gov), key=lambda r: r["date"], reverse=newest)
    if not ok:
        return None, bool(gov)
    r = ok[0]
    return {"date": r["date"], "group": r["speakerGroup"], "speaker": r["speaker"], "pos": r.get("speakerPosition"),
            "url": r.get("speechURL"), "n": j.get("numberOfRecords")}, bool(gov)


def look(nm, D):
    d = date.fromisoformat(D)
    out, gov = {}, False
    b, g = pick(q(nm, (d - timedelta(days=365)).isoformat(), D), True)
    gov |= g
    if b:
        out["before"] = b
    if not b or (d - date.fromisoformat(b["date"])).days > 60:
        a, g = pick(q(nm, D, (d + timedelta(days=150)).isoformat()), False)
        gov |= g
        if a:
            out["after"] = a
    return out, gov


def main():
    R, outp = sys.argv[1], sys.argv[2]
    nsh, sh = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (1, 0)
    js, P = jobs(R)
    AL = {}
    for r in csv.DictReader(open(f"{R}/aliases.csv")):
        AL.setdefault(r["person_id"], []).append(r["alias"])
    res = json.load(open(outp)) if os.path.exists(outp) else {}
    for i, (pid, name, D) in enumerate(js):
        key = f"{pid}|{D}"
        if i % nsh != sh or key in res:
            continue
        out, gov = look(name.replace(" ", ""), D)
        alias = None
        if not out:
            for nm in dict.fromkeys(x.replace(" ", "") for x in AL.get(pid, []) + [re.sub(r"\s*\(.*\)$", "", P[pid]["jawiki_title"])]):
                if nm != name.replace(" ", ""):
                    o2, g2 = look(nm, D)
                    if o2:
                        alias = o2.get("before") or o2.get("after")
                        break
        res[key] = {"D": D, "before": out.get("before"), "after": out.get("after"), "alias": alias, "gov": gov}
        if len(res) % 20 == 0:
            json.dump(res, open(outp, "w"), ensure_ascii=False)
    json.dump(res, open(outp, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
