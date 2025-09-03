#!/usr/bin/env python3
import os, json, hashlib, argparse, time, re
from datetime import datetime, timedelta
from dateutil import parser as dtparse
import pytz, feedparser
from feedgen.feed import FeedGenerator

TITLE_MAX = 70
DESC_MAX  = 120
PER_SPORT_CAP_DEFAULT = 3
JST = pytz.timezone("Asia/Tokyo")

def load_config(p): return json.load(open(p, "r", encoding="utf-8"))
def normalize_dt(s):
    if not s: return None
    try:
        dt = dtparse.parse(s);  dt = dt if dt.tzinfo else pytz.utc.localize(dt)
        return dt.astimezone(JST)
    except Exception: return None
def make_guid(t): return hashlib.sha1(t.encode("utf-8")).hexdigest()
def shorten(s, n): s=(s or "").strip();  return s if len(s)<=n else s[:max(0,n-1)].rstrip()+"…"

# ---------- match-only filters ----------
def compile_filters(cfg, sport):
    root = cfg.get("filters") or {}
    flt  = root.get(sport, {})
    inc = [re.compile(p, re.IGNORECASE) for p in flt.get("include", [])]
    exc = [re.compile(p, re.IGNORECASE) for p in flt.get("exclude", [])]
    return root.get("mode","off"), inc, exc
def looks_like_match(cfg, sport, title, summary):
    mode, inc, exc = compile_filters(cfg, sport)
    if mode != "match_only": return True
    text = f"{title} {summary}"
    if inc and not any(r.search(text) for r in inc): return False
    if exc and any(r.search(text) for r in exc): return False
    if sport in ("npb","mlb","jleague") and not re.search(r"\bvs\b|対|試合|スタメン|先発|ハイライト|結果|スコア", text, re.I): return False
    if sport == "keiba" and not re.search(r"出走|枠順|結果|払戻|確定|レース|予想", text): return False
    return True
# ----------------------------------------

def collect_items(cfg):
    seen, items = set(), []
    for feed in cfg["feeds"]:
        parsed = feedparser.parse(feed["url"])
        for e in parsed.entries:
            title = getattr(e, "title", "").strip()
            summary = getattr(e, "summary", "").strip() if hasattr(e,"summary") else ""
            link = getattr(e, "link", "").strip()
            if not looks_like_match(cfg, feed["sport"], title, summary): continue
            sig = (link or "") + "||" + title
            if sig in seen: continue
            seen.add(sig)
            items.append({
                "raw_title": title, "summary": summary, "link": link or feed["url"],
                "published": normalize_dt(e.get("published") or e.get("updated")) or datetime.now(JST),
                "sport": feed["sport"], "bet_url": feed["target_url"], "source_name": feed.get("name", feed["sport"].upper())
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    return items

def collect_demo_items(cfg, per_sport=PER_SPORT_CAP_DEFAULT, run_id=""):
    now = datetime.now(JST)
    demo = {
        "npb":["阪神 vs 巨人 きょう18:00 先発発表","広島が接戦を制す、終盤で逆転","パ・リーグ投手戦 注目ポイント"],
        "jleague":["浦和 vs 川崎F プレビュー","神戸、首位攻防戦を制す","横浜FM 新戦力が躍動"],
        "keiba":["セントライト記念 展望","重賞トリプルトレンド：注目馬3頭","今週の追い切り評価"],
        "mlb":["ドジャース 大谷がマルチ安打","パドレス ダルビッシュ復帰登板","カブス 鈴木誠也が決勝打"]
    }
    items=[]
    for f in cfg["feeds"]:
        titles = demo.get(f["sport"], [f"{f['sport'].upper()} Demo News"])
        for i,t in enumerate(titles[:per_sport]):
            items.append({
                "raw_title": t, "summary":"（デモ）テスト要約。", "link": f"https://example.com/demo?s={f['sport']}&r={run_id}&i={i}",
                "published": now - timedelta(minutes=i*7), "sport": f["sport"], "bet_url": f["target_url"], "source_name": f.get("name", f["sport"].upper())
            })
    items.sort(key=lambda x: x["published"], reverse=True);  return items

def write_feed(outpath, channel_title, self_link, channel_desc, items, emoji_map,
               guid_suffix="", limit_per_sport=PER_SPORT_CAP_DEFAULT, cta_text="ベットはこちら"):
    capped, cnt = [], {}
    for it in items:
        k=it["sport"]; cnt[k]=cnt.get(k,0)+1
        if cnt[k] <= limit_per_sport: capped.append(it)

    fg = FeedGenerator()
    fg.id(self_link); fg.title(channel_title); fg.link(href=self_link, rel='self')
    fg.language("ja"); fg.description(channel_desc)

    jp = {"npb":"NPB","jleague":"Jリーグ","keiba":"競馬","mlb":"MLB"}
    for it in capped:
        sport = it["sport"]; sport_label = jp.get(sport, sport.upper())
        emoji = emoji_map.get(sport, "🎲")

        # item title: only "⚾ [NPB] <short title>"
        display_title = f"{emoji} [{sport_label}] {shorten(it['raw_title'], TITLE_MAX)}"
        summary_short = shorten(it["summary"], DESC_MAX)

        fe = fg.add_entry()
        fe.id(make_guid(it["link"]+"||"+it["raw_title"]+"||"+guid_suffix))
        fe.title(display_title)
        # no fe.link(...) → prevents embed unfurl

        cta_top = f"👉 __**[{cta_text}]({it['bet_url']})**__"
        article_link = f"<{it['link']}>"
        desc = [cta_top] + ([summary_short] if summary_short else []) + [f"📰 記事を読む {article_link}"]
        fe.description("\n\n".join(desc)); fe.pubDate(it["published"])

    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    fg.rss_file(outpath, pretty=True, encoding="utf-8")
    print(f"Wrote {outpath} ({len(capped)} items)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true"); ap.add_argument("--per-sport", type=int, default=PER_SPORT_CAP_DEFAULT)
    args = ap.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    cfg  = load_config(os.path.join(root,"config.json"))
    emoji = cfg.get("emoji_by_sport", {}); cta_text = cfg.get("cta",{}).get("text","ベットはこちら")
    suppress_title = cfg.get("suppress_channel_title", True)
    invisible = "\u200B" if suppress_title else None

    if args.demo:
        guid = str(int(time.time()))
        items = collect_demo_items(cfg, per_sport=args.per_sport, run_id=guid)
    else:
        guid = ""; items = collect_items(cfg)

    outdir = os.path.join(root,"dist"); os.makedirs(outdir, exist_ok=True)

    # Combined feed
    combined_title = invisible if invisible is not None else cfg.get("feed_title","スポーツ速報（ベットリンク付き）")
    write_feed(
        os.path.join(outdir,"feed.xml"),
        combined_title,
        cfg.get("feed_link","https://example.com/feed.xml"),
        cfg.get("feed_description",""),
        items, emoji, guid, args.per_sport, cta_text
    )

    # Per sport feeds
    by = {}
    for it in items: by.setdefault(it["sport"], []).append(it)
    jp = {"npb":"NPB","jleague":"Jリーグ","keiba":"競馬","mlb":"MLB"}
    base_link = cfg.get("feed_link","https://example.com/feed.xml").rsplit("/",1)[0]

    files = {"npb":"npb.xml","jleague":"jleague.xml","keiba":"keiba.xml","mlb":"mlb.xml"}
    for sport, fname in files.items():
        title = invisible if invisible is not None else f"{cfg.get('feed_title','スポーツ速報（ベットリンク付き）')}｜{jp.get(sport, sport.upper())}"
        link  = f"{base_link}/{fname}"
        desc  = f"{cfg.get('feed_description','')}（{jp.get(sport, sport.upper())}のみ）"
        write_feed(os.path.join(outdir,fname), title, link, desc, by.get(sport, []), emoji, guid, args.per_sport, cta_text)

if __name__ == "__main__":
    main()
