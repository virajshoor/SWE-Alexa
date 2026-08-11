# Publishing Alexa-Rufus-1 results online (Pages-first)

Primary public surface: **GitHub Pages** at
[`https://virajshoor.github.io/SWE-Alexa/`](https://virajshoor.github.io/SWE-Alexa/).

A public Hugging Face **model** repo is optional and **not required** (and may stay private).
Official Open LLM Leaderboard / Artificial Analysis still cannot auto-list closed Rufus web-UI scores.

## Enable public Pages

1. Make **https://github.com/virajshoor/SWE-Alexa** public.
2. **Settings → Pages → Source: GitHub Actions**.
3. Merge to `main` (or run workflow **Deploy GitHub Pages leaderboard**).
4. Confirm: `https://virajshoor.github.io/SWE-Alexa/`

## SEO package in `docs/`

| File | Purpose |
| --- | --- |
| `index.html` | Leaderboard with **static** score rows (crawler-friendly), OG/Twitter tags, JSON-LD (`WebSite`, `Dataset`, `ItemList`, `FAQPage`) |
| `methodology.html` | Indexable methodology / TechArticle |
| `alexa_rufus_1_scores.json` | Machine-readable scores |
| `og-cover.jpg` | Social preview image |
| `sitemap.xml` / `robots.txt` | Crawl hints |
| `llms.txt` | AI-crawler summary |

## After go-live (recommended)

- Google Search Console → add property `https://virajshoor.github.io/SWE-Alexa/` → submit `sitemap.xml`
- Share the canonical URL (OG tags + cover image) when linking from GitHub README / social

## Optional HF Space only

If you later want a Gradio Space **without** a public model weights repo, you can still run
`scripts/publish_to_hf.py` for the Space half — but Pages alone is enough for a public benchmark board.
