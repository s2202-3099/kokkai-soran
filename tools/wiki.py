"""Wikipedia日本語版から記事を取るための小さな道具。

取り過ぎで断られる（HTTP 429）ので、間隔を空け、断られたら待って取り直す。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://ja.wikipedia.org/w/api.php"
UA = "kokkai-soran/0.1 (https://github.com/s2202-3099/kokkai-soran)"
_last = [0.0]


def call(params, min_gap=1.5):
    params = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(15):
        wait = _last[0] + min_gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            data = json.load(urllib.request.urlopen(req, timeout=90))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(min(int(e.headers.get("Retry-After") or 0) or 10 * (attempt + 1), 120))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(10 * (attempt + 1))
            continue
        if data.get("error", {}).get("code") == "maxlag":
            time.sleep(10)
            continue
        return data
    raise RuntimeError("Wikipediaから取れなかった: " + url[:200])


def pages(titles, batch=20, content=True):
    """記事名の一覧を受け取り、{渡した記事名: 記事情報} を返す。転送と表記ゆれをたどる。"""
    out = {}
    titles = list(dict.fromkeys(titles))
    for i in range(0, len(titles), batch):
        chunk = titles[i:i + batch]
        params = {"action": "query", "redirects": "1", "titles": "|".join(chunk),
                  "prop": "pageprops|info" + ("|revisions" if content else ""),
                  "ppprop": "wikibase_item|disambiguation"}
        if content:
            params.update({"rvprop": "content|ids|timestamp", "rvslots": "main"})
        q = call(params)["query"]
        norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
        red = {x["from"]: x["to"] for x in q.get("redirects", [])}
        by = {p["title"]: p for p in q["pages"]}
        for t in chunk:
            tt = norm.get(t, t)
            tt = red.get(tt, tt)
            p = by.get(tt)
            if not p or p.get("missing"):
                out[t] = None
                continue
            rec = {"title": p["title"], "pageid": p["pageid"], "length": p.get("length"),
                   "qid": p.get("pageprops", {}).get("wikibase_item"),
                   "disambiguation": "disambiguation" in p.get("pageprops", {})}
            if content and p.get("revisions"):
                rv = p["revisions"][0]
                rec.update({"revid": rv["revid"], "ts": rv["timestamp"], "text": rv["slots"]["main"]["content"]})
            out[t] = rec
    return out
