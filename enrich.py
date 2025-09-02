#!/usr/bin/env python3
import os, json, hashlib, argparse
from datetime import datetime, timedelta
from dateutil import parser as dtparse
import pytz
import feedparser
from feedgen.feed import FeedGenerator

JST = pytz.timezone("Asia/Tokyo")

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
                "title": f"[{name}] {title}",
                "link": link or url,
                "summary": summary,
                "published": pub_dt,
                "sport": sport,
                "bet_url": target_url
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    return items

def collect_demo_items(cfg, per_sport=3):
    """Create fake items so you can test immediately without waiting on real RSS updates."""
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
        name = feed.get("name", sport.upper())
        target_url = feed["target_url"]
        titles = demo_titles.get(sport, [f"{sport.upper()} Demo News 1", f"{sport.upper()} Demo News 2"])
        for i, t in enumerate(titles[:per_sport]):
            pub_dt = now - timedelta(minutes=(i * 7))  # stagger times
            items.append({
                "title": f"[{name}] {t}",
                "link": "https://example.com/demo-article",
                "summary": "（デモ）これはテスト用のニュース要約です。実運用では実際の記事の概要が入ります。",
                "published": pub_dt,
                "sport": sport,
                "bet_url": target_url
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    return items

def write_feed(outpath, title, link, description, items, emoji_by_sport):
    fg = FeedGenerator()
    fg.id(link)
    fg.title(title)
    fg.link(href=link, rel='self')
    fg.language("ja")
    fg.description(description)
    for it in items:
        fe = fg.add_entry()
        fe.id(make_guid(it["link"] + "||" + it["title"]))
        fe.title(it["title"])
        fe.link(href=it["link"])
        emoji = emoji_by_sport.get(it["sport"], "🎲")
        desc = (it["summary"] + "\n\n" if it["summary"] else "") + f"{emoji} ベットはこちら: {it['bet_url']}"
        fe.description(desc)
        fe.pubDate(it["published"])
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    fg.rss_file(outpath, pretty=True, encoding="utf-8")
    print(f"Wrote {outpath} ({len(items)} items)")

def main():
    parser = argparse.ArgumentParser(description="JP Sports Enriched RSS generator")
    parser.add_argument("--demo", action="store_true", help="Generate demo items (no network fetch) for quick testing")
    parser.add_argument("--per-sport", type=int, default=3, help="Demo items per sport when --demo is used")
    args = parser.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    cfg = load_config(os.path.join(root, "config.json"))
    emoji_by_sport = cfg.get("emoji_by_sport", {})

    if args.demo:
        all_items = collect_demo_items(cfg, per_sport=args.per_sport)
    else:
        all_items = collect_items(cfg)

    outdir = os.path.join(root, "dist")
    os.makedirs(outdir, exist_ok=True)

    # Combined
    write_feed(
        os.path.join(outdir, "feed.xml"),
        cfg.get("feed_title", "JP Sports Betting Digest"),
        cfg.get("feed_link","https://example.com/feed.xml"),
        cfg.get("feed_description",""),
        all_items,
        emoji_by_sport
    )

    # Per-sport
    by_sport = {}
    for it in all_items:
        by_sport.setdefault(it["sport"], []).append(it)

    sport_files = {"npb": "npb.xml", "jleague": "jleague.xml", "keiba": "keiba.xml", "mlb": "mlb.xml"}
    base_link = cfg.get("feed_link","https://example.com/feed.xml").rsplit("/",1)[0]

    for sport, items in by_sport.items():
        fn = sport_files.get(sport, f"{sport}.xml")
        title = f"{cfg.get('feed_title','JP Sports Betting Digest')} - {sport.upper()}"
        link = f"{base_link}/{fn}"
        desc = f"{cfg.get('feed_description','')}（{sport.upper()}のみ）"
        write_feed(os.path.join(outdir, fn), title, link, desc, items, emoji_by_sport)

if __name__ == "__main__":
    main()
