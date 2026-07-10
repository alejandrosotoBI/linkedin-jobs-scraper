# LinkedIn Jobs Scraper 🎯

A Python CLI tool that scrapes public LinkedIn job listings — including **full job descriptions** — and exports them to a clean Excel file. No LinkedIn account or login required: it uses LinkedIn's public guest endpoints via a headless browser.

## Features

- 🔍 **Keyword + location search** with interactive location disambiguation (picks the exact `geoId` from LinkedIn's autocomplete, so "Springfield" means *your* Springfield)
- 📄 **Full job descriptions**, not just titles — title, company, exact location, and complete description text for every posting
- 📊 **Excel output** (`.xlsx`) chosen through a native save-file dialog
- 💾 **Crash-safe**: results stream to a temporary CSV as they're scraped, so partial progress is never lost
- 🐢 **Rate-limit friendly**: randomized 5–10 second delays between requests to avoid being blocked
- 🥊 **Sign-in wall busting**: automatically removes LinkedIn's modals and overlays that block guest browsing
- 🔢 Scrapes up to LinkedIn's guest limit of ~1,000 jobs per search

## Requirements

- Python 3.8+
- Windows, macOS, or Linux (the file-save dialog uses Tkinter, which ships with most Python installs)

## Installation

```bash
git clone https://github.com/<your-username>/linkedin-jobs-scraper.git
cd linkedin-jobs-scraper

pip install -r requirements.txt

# Install the headless browser used by Playwright
playwright install chromium
```

## Usage

```bash
python linkedin_jobs_scraper.py
```

You'll be walked through it interactively:

1. **Pick a save location** for the Excel file (a file dialog opens).
2. **Enter a job keyword** — e.g. `Power BI`, `Data Engineer`.
3. **Enter a location** — e.g. `Chicago`.
4. If LinkedIn suggests multiple matching locations, **pick the exact one** from the numbered list.
5. Wait. ☕ The scraper paginates through all results to collect job IDs (Phase 1), then fetches each job's full description one by one (Phase 2). With the built-in safety delays, large searches can take a while — that's intentional.

### Output

An Excel workbook with one row per job:

| Job ID | Company | Exact Location | Title | Description |
|--------|---------|----------------|-------|-------------|

If the Excel export fails for any reason, your raw data is preserved in `temp_linkedin_jobs_backup.csv`.

## How it works

1. **Search setup** — a headless Chromium browser (Playwright) opens LinkedIn's guest job search, fills in your keyword and location, and grabs the precise `geoId` from the location typeahead.
2. **Phase 1: ID harvesting** — paginates LinkedIn's public `seeMoreJobPostings` endpoint in batches of 25, deduplicating job IDs until results run out or the ~1,000-job guest cap is hit.
3. **Phase 2: Detail scraping** — fetches each job's public posting page and parses title, company, location, and description with BeautifulSoup, appending each row to a backup CSV.
4. **Phase 3: Export** — pandas converts the CSV to `.xlsx` (job IDs kept as text so Excel doesn't mangle them into scientific notation).

## Troubleshooting

- **`ModuleNotFoundError: No module named 'tkinter'`** — on some Linux distros install it with `sudo apt install python3-tk`.
- **Playwright errors on first run** — make sure you ran `playwright install chromium`.

## Disclaimer

This tool is for **personal and educational use** (e.g., researching your own job search). Automated scraping may violate [LinkedIn's User Agreement](https://www.linkedin.com/legal/user-agreement). Use responsibly, keep the built-in delays, don't hammer their servers, and don't redistribute scraped data. You are solely responsible for how you use this tool.
