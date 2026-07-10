import asyncio
import random
import sys
import urllib.parse
import csv
import os
import tkinter as tk
from tkinter import filedialog
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import pandas as pd  # Make sure to run: pip install pandas openpyxl

# --- CONFIGURATION ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
TEMP_CSV = "temp_linkedin_jobs_backup.csv"

async def destroy_popups(page):
    """BERSERKER MODE: Hunts down and destroys LinkedIn modals, overlays, and sign-in walls"""
    try:
        await page.evaluate("""
            const selectors = [
                '.modal__main', 
                '.contextual-sign-in-modal',
                '#base-contextual-sign-in-modal',
                '.artdeco-modal-overlay',
                '#artdeco-modal-outlet',
                'div[data-id="sign-in-form"]',
                '.fixed.inset-0', 
                'div[role="dialog"]'
            ];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => el.remove());
            });
            document.body.style.overflow = 'auto';
            document.body.classList.remove('modal-open');
        """)
    except Exception:
        pass


async def scrape_linkedin(output_excel_path):
    print("\n" + "="*80)
    print(" 🎯 LINKEDIN SCRAPER: DEEP SCRAPE BERSERKER MODE")
    print("="*80)
    
    keyword = input("Enter job keyword (e.g., Power BI): ")
    location = input("Enter location (e.g., Chicago): ")

    # Setup Temporary CSV File (Added Exact Location column)
    with open(TEMP_CSV, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Job ID', 'Company', 'Exact Location', 'Title', 'Description'])

    async with async_playwright() as p:
        print("\n[*] Launching browser (HEADLESS MODE)...")
        browser = await p.chromium.launch(headless=True) 
        context = await browser.new_context(user_agent=HEADERS["User-Agent"])
        page = await context.new_page()

        # Step 1: Go to the base job search page
        print("[*] Navigating to LinkedIn Job Search...")
        await page.goto("https://www.linkedin.com/jobs/search/", wait_until="domcontentloaded", timeout=60000)
        
        await asyncio.sleep(2)
        await destroy_popups(page)

        # Step 2: Fill out Keyword explicitly in the JOBS panel
        print(f"[*] Entering keyword: '{keyword}'")
        await page.locator('input#job-search-bar-keywords').fill(keyword)

        # Step 3: Fill out Location SLOWLY to trigger the dropdown
        print(f"[*] Entering location: '{location}' to fetch suggestions...")
        await page.locator('input#job-search-bar-location').fill("") 
        await page.locator('input#job-search-bar-location').press_sequentially(location, delay=150)

        # Wait for dropdown
        try:
            await page.wait_for_selector('ul#job-search-bar-location-typeahead-list li', timeout=7000)
            await asyncio.sleep(1.5) 
            
            loc_elements = await page.locator('ul#job-search-bar-location-typeahead-list li').all()
            loc_options = []
            
            for el in loc_elements:
                text = await el.inner_text()
                if text.strip():
                    loc_options.append((el, text.strip()))
            
            if loc_options:
                print("\n" + "-"*40)
                print(" 📍 MULTIPLE LOCATIONS FOUND")
                print("-"*40)
                for i, (el, text) in enumerate(loc_options):
                    print(f"  [{i + 1}] {text}")
                print("-"*40)
                
                choice_idx = -1
                while True:
                    try:
                        choice = int(input("\nEnter the number of the exact location you want: "))
                        if 1 <= choice <= len(loc_options):
                            choice_idx = choice - 1
                            break
                        else:
                            print("[!] Invalid number.")
                    except ValueError:
                        print("[!] Enter a valid number.")
                
                selected_text = loc_options[choice_idx][1]
                print(f"\n[*] Selecting '{selected_text}'...")
                await loc_options[choice_idx][0].click(force=True)
                await asyncio.sleep(1)
            else:
                selected_text = location
                
        except Exception:
            selected_text = location

        await destroy_popups(page)

        # Step 4: Extract geoId for precision targeting
        geo_id = await page.locator('section#jobs-search-panel input[name="geoId"]').get_attribute('value')
        safe_kw = urllib.parse.quote(keyword)
        safe_loc = urllib.parse.quote(selected_text)
        
        # --- PHASE 1: PAGINATION & GATHERING ALL JOB IDS ---
        all_job_ids = []
        seen_ids = set() 
        start_offset = 0
        
        print("\n[*] Starting Pagination to gather Job IDs (Batching by 25)...")
        
        while True:
            batch_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={safe_kw}&location={safe_loc}&start={start_offset}"
            if geo_id:
                batch_url += f"&geoId={geo_id}"

            print(f"    -> Fetching jobs {start_offset} to {start_offset + 25}...")
            
            delay = random.uniform(5.0, 10.0)
            await asyncio.sleep(delay)
            
            try:
                await page.goto(batch_url, wait_until="domcontentloaded")
                
                content = await page.content()
                soup = BeautifulSoup(content, 'lxml')
                cards = soup.find_all('div', class_='base-search-card')
                
                if not cards:
                    print(f"[*] No more jobs found at offset {start_offset}. Reached the end!")
                    break
                    
                new_ids = 0
                for card in cards:
                    urn = card.get('data-entity-urn')
                    if urn:
                        j_id = urn.split(':')[-1]
                        
                        if j_id not in seen_ids:
                            seen_ids.add(j_id)
                            all_job_ids.append(j_id)
                            new_ids += 1
                
                if new_ids == 0:
                    print("[*] No new IDs found. LinkedIn might be capping results. Moving to scrape descriptions.")
                    break
                    
                start_offset += 25
                
                if start_offset >= 1000:
                    print("[*] Reached LinkedIn's guest limit of 1000 jobs.")
                    break
                    
            except Exception as e:
                print(f"[!] Error paginating at offset {start_offset}: {e}")
                break

        print(f"\n[*] SUCCESSFULLY FOUND {len(all_job_ids)} UNIQUE JOB IDs!")
        print(f"[*] Commencing slow, safe extraction of descriptions.\n")

        # --- PHASE 2: FETCHING INDIVIDUAL DESCRIPTIONS ---
        for index, j_id in enumerate(all_job_ids):
            print(f"[{index + 1}/{len(all_job_ids)}] Fetching description for ID: {j_id}...", end=" ")
            detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{j_id}"
            
            try:
                await page.goto(detail_url, wait_until="domcontentloaded")
                detail_content = await page.content()
                detail_soup = BeautifulSoup(detail_content, 'lxml')
                
                # Using the actual classes from your HTML snippet
                title_elem = detail_soup.find('h2', class_='top-card-layout__title')
                company_elem = detail_soup.find('a', class_='topcard__org-name-link')
                # Grab the location which is stored in a span bullet point next to company name
                exact_loc_elem = detail_soup.select_one('.topcard__flavor-row .topcard__flavor--bullet')
                desc_elem = detail_soup.find('div', class_='show-more-less-html__markup')
                
                title = title_elem.get_text(strip=True) if title_elem else "N/A"
                company = company_elem.get_text(strip=True) if company_elem else "N/A"
                exact_location = exact_loc_elem.get_text(strip=True) if exact_loc_elem else "N/A"
                
                # Using '\n' separator so bullet points and paragraphs format cleanly in Excel
                description = desc_elem.get_text(separator='\n', strip=True) if desc_elem else "N/A"
                
                if title == "N/A" and company == "N/A":
                    print("Blocked or Invalid Job.")
                else:
                    print(f"Success! ({company} - {exact_location})")
                    
                    with open(TEMP_CSV, mode='a', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow([j_id, company, exact_location, title, description])

                delay = random.uniform(5.0, 10.0)
                await asyncio.sleep(delay)

            except Exception as e:
                print("Failed!")
                await asyncio.sleep(10)

        await browser.close()
        
    # --- PHASE 3: CONVERT TO EXCEL ---
    print("\n[*] SCRAPING COMPLETE!")
    print(f"[*] Converting backup data to Excel format...")
    try:
        # dtype={'Job ID': str} forces Pandas to treat the ID as text, avoiding scientific notation
        df = pd.read_csv(TEMP_CSV, dtype={'Job ID': str})
        df.to_excel(output_excel_path, index=False)
        os.remove(TEMP_CSV) 
        print(f"[✅] Successfully exported jobs to: {output_excel_path}")
    except Exception as e:
        print(f"[!] Error exporting to Excel: {e}")
        print(f"[*] Don't worry! Your raw CSV data was preserved at: {TEMP_CSV}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    root = tk.Tk()
    root.withdraw() 
    root.attributes('-topmost', True) 
    
    print("\n[*] Please select where you want to save the Excel file...")
    output_excel_path = filedialog.asksaveasfilename(
        title="Save LinkedIn Jobs As...",
        defaultextension=".xlsx",
        filetypes=[("Excel Workbook", "*.xlsx")],
        initialfile="linkedin_jobs.xlsx"
    )
    
    if not output_excel_path:
        print("[!] No save location selected. Exiting...")
        sys.exit()
        
    asyncio.run(scrape_linkedin(output_excel_path))