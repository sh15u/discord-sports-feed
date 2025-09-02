#!/usr/bin/env python3
import os, json, hashlib, argparse, time
from datetime import datetime, timedelta
from dateutil import parser as dtparse
import pytz
import feedparser
from feedgen.feed import FeedGenerator

JST = pytz.timezone("Asia/Tokyo")

TITLE_MAX = 70     # tweak if you want shorter titles
DESC_MAX  = 120    # tweak if you want shorter descriptions

def load_config(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def normalize_dt(dt_str: str):
    if not dt_str:
        return None
    try:
        dt = dtparse.parse(dt_str)
        if not dt.tzinfo:
            dt = pytz.utc.localize(dt)
        return dt.astimezone(JST)
    except Exception:
        return None

def make_guid(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def shorten(s: str, n: int):
    s = (s or "").strip()
    return s if len(s) <= n else s[: max(0, n - 1)].rstrip() + "…"

def collect_items(cfg):
    seen = set()
    items = []
    for feed in cfg["feeds"]:
        url = feed["url"]
        sport = feed["sport"]
        target_url = feed["target_url"]
        name = feed.get("name", sport.upper())
        parsed = feedparser.parse(url)
        for e in parsed.entries:
            title = getattr(e, "title", "").strip()
            link = getattr(e, "link", "").strip()
            summary = getattr(e, "summary", "").strip() if hasattr(e, "summary") else ""
            published = e.get("published") or e.get("updated") or ""
            sig = (link or "") + "||" + title
            if sig in seen:
                continue
            seen.add(sig)
            pub_dt = normalize_dt(published) or datetime.now(JST)
            items.append({
                "raw_title": title,
                "link": link or url,
                "summary": summary,
                "published": pub_dt,
                "sport": sport,
                "bet_url": target_url,
                "source_name": name
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    return items

def collect_demo_items(cfg, per_sport=3):
    now = datetime.now(JST)
    demo_titles = {
        "npb": ["阪神 vs 巨人 きょう18:00 先発発表", "広島が接戦を制す、終盤で逆転", "パ・リーグ投手戦 注目ポイント"],
        "jleague": ["浦和 vs 川崎F プレビュー", "神戸、首位攻防戦を制す", "横浜FM 新戦力が躍動"],
        "keiba": ["セントライト記念 展望", "重賞トリプルトレンド：注目馬3頭", "今週の追い切り評価"],
        "mlb": ["ドジャース 大谷がマルチ安打", "パドレス ダルビッシュ復帰登板", "カブス 鈴木誠也が決勝打"]
    }
    items = []
    for feed in cfg["feeds"]:
        sport = feed["sport"]
        target_url = feed["target_url"]
        name = feed.get("name", sport.upper())
        titles = demo_titles.get(sport, [f"{sport.upper()} Demo News"])
        for i, t in enumerate(titles[:per_sport]):
            pub_dt = now - timedelta(minutes=(i * 7))
            items.append({
                "raw_title": t,
                "link": "https://example.com/demo-article",
                "summary": "（デモ）これはテスト用のニュース要約です。実運用では実際の記事の概要が入ります。",
                "published": pub_dt,
                "sport": sport,
                "bet_url": target_url,
                "source_name": name
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    return items

def write_feed(outpath, title, link, description, items, emoji_by_sport, guid_suffix="", limit_per_sport=3):
    # cap items per sport to reduce spam
    capped, counts = [], {}
    for it in items:
        k = it["sport"]
        counts[k] = counts.get(k, 0) + 1
        if counts[k] <= limit_per_sport:
            capped.append(it)

    fg = FeedGenerator()
    fg.id(link)
    fg.title(title)
    fg.link(href=link, rel='self')
    fg.language("ja")
    fg.description(description)

    for it in capped:
        sport = it["sport"]
        emoji = emoji_by_sport.get(sport, "🎲")
        display_title = f"{emoji} [{it['source_name']}] {shorten(it['raw_title'], TITLE_MAX)}"
        summary_short = shorten(it["summary"], DESC_MAX)

        fe = fg.add_entry()
        guid_seed = it["link"] + "||" + it["raw_title"] + "||" + guid_suffix
        fe.id(make_guid(guid_seed))
        fe.title(display_title)
        fe.link(href=it["link"])

        # CTA FIRST, bold + underline; links in <...> to prevent embeds
        cta = f"{emoji} __**ベットはこちら**__ → <{it['bet_url']}>"
        desc_lines = [cta]
        if summary_short:
            desc_lines.append(summary_short)
        fe.description("\n\n".join(desc_lines))
        fe.pubDate(it["published"])

    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    fg.rss_file(outpath, pretty=True, encoding="utf-8")
    print(f"Wrote {outpath} ({len(capped)} items)")

def main():
    p = argparse.ArgumentParser(description="JP Sports Enriched RSS")
    p.add_argument("--demo", action="store_true", help="Generate demo items")
    p.add_argument("--per-sport", type=int, default=3, help="Max items per sport (anti-spam)")
    p.add_argument("--demo-run-id", type=str, default="", help="Force-unique IDs for demo runs")
    args = p.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    cfg = load_config(os.path.join(root, "config.json"))
    emoji_by_sport = cfg.get("emoji_by_sport", {})

    guid_suffix = ""
    if args.demo:
        guid_suffix = args.demo_run_id or str(int(time.time()))
        all_items = collect_demo_items(cfg, per_sport=args.per_sport)
    else:
        all_items = collect_items(cfg)

    outdir = os.path.join(root, "dist")
    os.makedirs(outdir, exist_ok=True)

    # Combined
    write_feed(
        os.path.join(outdir, "feed.xml"),
        cfg.get("feed_title", "JP Sports Betting Digest"),
        cfg.get("feed_link", "https://example.com/feed.xml"),
        cfg.get("feed_description", ""),
        all_items, emoji_by_sport, guid_suffix, args.per_sport
    )

    # Per-sport (always emit files)
    by_sport = {}
    for it in all_items:
        by_sport.setdefault(it["sport"], []).append(it)

    sport_files = {"npb": "npb.xml", "jleague": "jleague.xml", "keiba": "keiba.xml", "mlb": "mlb.xml"}
    base_link = cfg.get("feed_link","https://example.com/feed.xml").rsplit("/",1)[0]

    for sport, filename in sport_files.items():
        items = by_sport.get(sport, [])
        title = f"{cfg.get('feed_title','JP Sports Betting Digest')} - {sport.upper()}"
        link  = f"{base_link}/{filename}"
        desc  = f"{cfg.get('feed_description','')}（{sport.upper()}のみ）"
        write_feed(os.path.join(outdir, filename), title, link, desc, items, emoji_by_sport, guid_suffix, args.per_sport)

if __name__ == "__main__":
    main()
