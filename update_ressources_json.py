#!/usr/bin/env python3
"""
Met a jour ressources.json en combinant :
  - ressources_base.json  : ressources stables de la gare centrale (143 entrees)
                            Ce fichier ne change que si vous ajoutez manuellement
                            de nouvelles ressources au wiki.
  - Flux RSS              : actualites des 7 derniers jours (genere automatiquement)

Usage :
  pip install feedparser
  python update_ressources_json.py
  -> genere ressources.json a pousser sur GitHub (ou commit auto via Actions)
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

BASE_FILE   = Path("ressources_base.json")
OUTPUT_FILE = Path("ressources.json")
MAX_AGE_DAYS = 7
MAX_PER_FEED = 5

RSS_SOURCES = [
    {
        "name":      "CEREMA",
        "categorie": "Transitions",
        "urls": [
            "https://www.cerema.fr/fr/rss/news/feed",
            "https://doc.cerema.fr/Portal/Recherche/Search.svc/SearchRss"
            "?key=4517a4fa103f7f4b081f437a4830c82d&useSearchSort=false&useSearchResultSize=true",
        ],
    },
    {
        "name":      "ADEME - Librairie",
        "categorie": "Transitions",
        "urls": [
            "https://librairie.ademe.fr/rss/nouveautes.xml",
            "https://librairie.ademe.fr/rss/actualites.xml",
        ],
    },
    {
        "name":      "Banque des Territoires",
        "categorie": "Finances",
        "urls": [
            "https://www.banquedesterritoires.fr/flux/localtis.xml",
        ],
    },
]


def strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def fetch_rss_articles():
    cutoff   = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    articles = []
    seen     = set()

    for source in RSS_SOURCES:
        for url in source["urls"]:
            try:
                feed = feedparser.parse(
                    url,
                    request_headers={"User-Agent": "Mozilla/5.0 FranceTerritoriale"},
                )
                count = 0
                for entry in feed.entries:
                    if count >= MAX_PER_FEED:
                        break
                    pub = None
                    for attr in ("published_parsed", "updated_parsed"):
                        val = getattr(entry, attr, None)
                        if val:
                            pub = datetime(*val[:6], tzinfo=timezone.utc)
                            break
                    if pub and pub < cutoff:
                        continue
                    title = (entry.get("title") or "").strip()
                    link  = (entry.get("link") or "").strip()
                    if not title or not link or link in seen:
                        continue
                    seen.add(link)
                    desc = strip_html(entry.get("summary", entry.get("description", "")))[:300]
                    articles.append({
                        "bf_titre":       title,
                        "bf_lien":        link,
                        "bf_categorie":   source["categorie"],
                        "bf_description": desc,
                        "bf_tags":        source["name"],
                        "bf_type":        "Actualite",
                        "bf_formulaire":  "actu",
                    })
                    print(f"    OK  {title[:65]}")
                    count += 1
            except Exception as e:
                print(f"    ERREUR {url[:60]} : {e}")

    return articles


def main():
    # 1. Charger la base stable
    if not BASE_FILE.exists():
        print(f"ERREUR : {BASE_FILE} introuvable.")
        raise SystemExit(1)

    with open(BASE_FILE, encoding="utf-8") as f:
        base = json.load(f)
    print(f"Base chargee : {len(base)} ressources")

    # 2. Recuperer les actus RSS
    print("\nActualites RSS...")
    articles = fetch_rss_articles()
    print(f"  -> {len(articles)} articles")

    # 3. Assembler : base d'abord, actus ensuite
    result = base + articles
    print(f"\nTotal : {len(result)} entrees")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"OK -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
