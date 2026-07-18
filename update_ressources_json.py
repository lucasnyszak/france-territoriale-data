#!/usr/bin/env python3
"""
Met a jour ressources.json avec :
  - Les 142 ressources de la gare centrale (formulaire 8)
  - Les documents prets a l'emploi (formulaire 6)
  - Les actualites recentes des flux RSS (formulaire "actu")

Usage :
  pip install feedparser requests
  python update_ressources_json.py
  -> genere ressources.json a pousser sur GitHub
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import requests

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

WIKI_API      = "https://france-territoriale.yeswiki.pro/?api/forms/{id}/entries"
OUTPUT_FILE   = Path("ressources.json")
MAX_AGE_DAYS  = 7       # Articles plus vieux que N jours ignores
MAX_PER_FEED  = 5       # Articles max par flux RSS

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


# ---------------------------------------------------------------------------
# RESSOURCES WIKI
# ---------------------------------------------------------------------------

def fetch_wiki_form(form_id):
    print(f"  Chargement formulaire {form_id}...")
    try:
        resp = requests.get(
            WIKI_API.format(id=form_id),
            headers={"User-Agent": "FranceTerritoriale-Bot/1.0"},
            timeout=20,
        )
        entries = resp.json()
        print(f"    -> {len(entries)} entrees")
        return entries
    except Exception as e:
        print(f"    ERREUR : {e}")
        return []


def normalize_wiki_entry(entry, form_id):
    return {
        "bf_titre":       entry.get("bf_titre", ""),
        "bf_lien":        entry.get("bf_lien", ""),
        "bf_categorie":   entry.get("bf_categorie", ""),
        "bf_description": entry.get("bf_description", ""),
        "bf_tags":        entry.get("bf_tags", ""),
        "bf_type":        entry.get("bf_type", ""),
        "bf_formulaire":  str(form_id),
    }


# ---------------------------------------------------------------------------
# FLUX RSS
# ---------------------------------------------------------------------------

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
                    # Date
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
                    raw  = entry.get("summary", entry.get("description", ""))
                    desc = strip_html(raw)[:300]
                    articles.append({
                        "bf_titre":       title,
                        "bf_lien":        link,
                        "bf_categorie":   source["categorie"],
                        "bf_description": desc,
                        "bf_tags":        "",
                        "bf_type":        "Actualite",
                        "bf_formulaire":  "actu",
                        "bf_source":      source["name"],
                    })
                    print(f"    OK  {title[:65]}")
                    count += 1
            except Exception as e:
                print(f"    ERREUR {url[:60]} : {e}")

    return articles


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    result = []

    print("\n1. Ressources de la gare centrale (form 8)...")
    for entry in fetch_wiki_form(8):
        if entry.get("bf_titre"):
            result.append(normalize_wiki_entry(entry, 8))
    print(f"   -> {len(result)} ressources")

    count_before = len(result)
    print("\n2. Documents prets a l'emploi (form 6)...")
    for entry in fetch_wiki_form(6):
        if entry.get("bf_titre"):
            result.append(normalize_wiki_entry(entry, 6))
    print(f"   -> {len(result) - count_before} documents")

    print("\n3. Actualites RSS (7 derniers jours)...")
    articles = fetch_rss_articles()
    result.extend(articles)
    print(f"   -> {len(articles)} articles")

    print(f"\nTotal : {len(result)} entrees")
    print(f"Ecriture dans {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"OK -> {OUTPUT_FILE}")
    print("\nPousser sur GitHub :")
    print("  git add ressources.json && git commit -m 'update: ressources + actus' && git push")


if __name__ == "__main__":
    main()
