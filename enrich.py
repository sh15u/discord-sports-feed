#!/usr/bin/env python3
import os, json, hashlib, argparse, time
from datetime import datetime, timedelta
from dateutil import parser as dtparse
import pytz
import feedparser
from feedgen.feed import FeedGenerator

# ---------------- Tunables ----------------
TITLE_MAX = 70    # max chars shown in item title
DESC_MAX  = 120   # max chars shown in item description
PER_SPORT_CAP_DEFAULT = 3  # items per sport per run (anti-spam)
JST = pytz.timezone("Asia/Tokyo")
# ------------------------------------------

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

def collect_demo_items(cfg, per_sport=PER_SPORT_CAP_DEFAULT, run_id=""):
    """Create fake items for instant testing. Ensures unique links per run so MEE6 posts them."""
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
            demo_link = f"https://example.com/demo-article?s={sport}&r={run_id}&i={i}"  # unique per run
            items.append({
                "raw_title": t,
                "link": demo_link,
                "summary": "（デモ）これはテスト用のニュース要約です。実運用では実際の記事の概要が入ります。",
                "published": pub_dt,
                "sport": sport,
                "bet_url": target_url,
                "source_name": name
            })
    items.sort(key=lambda x: x["published"], reverse=True)
    return items

def write_feed(outpath, title, link, description, items, emoji_by_sport,
               guid_suffix="", limit_per_sport=PER_SPORT_CAP_DEFAULT, cta_text="ベットはこちら"):
    """Build a single RSS file with compact, image-free entries and a bold CTA on top."""
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

    jp_names = {"npb": "NPB", "jleague": "Jリーグ", "keiba": "競馬", "mlb": "MLB"}

    for it in capped:
        sport = it["sport"]
        sport_label = jp_names.get(sport, sport.upper())
        emoji = emoji_by_sport.get(sport, "🎲")

        # Item title: スポーツ速報｜<SPORT>｜<EMOJI> [<SPORT>] <short-title>
        display_title = f"{sport_label}｜{emoji} [{sport_label}] {shorten(it['raw_title'], TITLE_MAX)}"
        summary_short = shorten(it["summary"], DESC_MAX)

        fe = fg.add_entry()
        guid_seed = it["link"] + "||" + it["raw_title"] + "||" + guid_suffix
        fe.id(make_guid(guid_seed))
        fe.title(display_title)
        fe.link(href=it["link"])

        # One CTA at the TOP (👉 + bold+underline) as a markdown link (suppresses image previews in MEE6)
        cta_top = f"👉 __**[{cta_text}]({it['bet_url']})**__"

        # Article link as markdown (not bare URL) to avoid previews
        desc_lines = [cta_top]
        if summary_short:
            desc_lines.append(summary_short)
        desc_lines.append(f"📰 [記事を読む]({it['link']})")

        fe.description("\n\n".join(desc_lines))
        fe.pubDate(it["published"])

    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    fg.rss_file(outpath, pretty=True, encoding="utf-8")
    print(f"Wrote {outpath} ({len(capped)} items)")

def main():
    p = argparse.ArgumentParser(description="JP Sports Enriched RSS")
    p.add_argument("--demo", action="store_true", help="Generate demo items")
    p.add_argument("--per-sport", type=int, default=PER_SPORT_CAP_DEFAULT, help="Max items per sport (anti-spam)")
    args = p.parse_args()

    root = os.path.dirname(os.path.abspath(__file__))
    cfg = load_config(os.path.join(root, "config.json"))
    emoji_by_sport = cfg.get("emoji_by_sport", {})
    cta_cfg = cfg.get("cta", {})
    cta_text = cta_cfg.get("text", "ベットはこちら")

    # Demo runs get a unique GUID suffix & link salt so MEE6 treats them as new
    if args.demo:
        run_id = str(int(time.time()))
        guid_suffix = run_id
        all_items = collect_demo_items(cfg, per_sport=args.per_sport, run_id=run_id)
    else:
        guid_suffix = ""
        all_items = collect_items(cfg)

    outdir = os.path.join(root, "dist")
    os.makedirs(outdir, exist_ok=True)

    # Combined feed (Japanese title by default)
    feed_title = cfg.get("feed_title", "スポーツ速報")
    feed_link  = cfg.get("feed_link", "https://example.com/feed.xml")
    feed_desc  = cfg.get("feed_description", "")

    write_feed(
        os.path.join(outdir, "feed.xml"),
        feed_title,
        feed_link,
        feed_desc,
        all_items, emoji_by_sport, guid_suffix, args.per_sport, cta_text
    )

    # Per-sport feeds (always emit files)
    by_sport = {}
    for it in all_items:
        by_sport.setdefault(it["sport"], []).append(it)

    sport_files = {"npb": "npb.xml", "jleague": "jleague.xml", "keiba": "keiba.xml", "mlb": "mlb.xml"}
    jp_names = {"npb": "NPB", "jleague": "Jリーグ", "keiba": "競馬", "mlb": "MLB"}
    base_link = feed_link.rsplit("/", 1)[0] if "/" in feed_link else feed_link

    for sport, filename in sport_files.items():
        items = by_sport.get(sport, [])
        title = f"{feed_title}｜{jp_names.get(sport, sport.upper())}"
        link  = f"{base_link}/{filename}"
        desc  = f"{feed_desc}（{jp_names.get(sport, sport.upper())}のみ）"
        write_feed(os.path.join(outdir, filename), title, link, desc, items,
                   emoji_by_sport, guid_suffix, args.per_sport, cta_text)

if __name__ == "__main__":
    main()
