import time
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"
    )

    page.goto(
        "https://terraria.fandom.com/wiki/Terraria_Wiki",
        wait_until="domcontentloaded",
        timeout=60000
    )

    # wait for wiki content, not ads
    page.wait_for_selector("div.mw-parser-output", timeout=60000)

    time.sleep(random.uniform(2, 5))

    soup = BeautifulSoup(page.content(), "lxml")

    content = soup.find("div", class_="mw-parser-output")
    
    # clean junk
    for tag in content.find_all([
        "aside", "nav", "table", "script", "style", "figure"
    ]):
        tag.decompose()
        
    contentLinks = content.find_all("a")
    contentToScrape = []
    contentToScrapeLinks = []
    for a in contentLinks:
        # contentToScrape.append(a.get_text("\n", strip=True))
        if a.get('href') and a.get('href').startswith("/wiki/") or a.get('href').startswith('/wiki/Guide:'):
            contentToScrapeLinks.append(a.get('href'))
    
    # print(contentToScrape)
    # print(contentToScrapeLinks)
    # text = content.get_text("\n", strip=True)

    # print(text)
    page.close()
    page = browser.new_page(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"
        )
    
    for links in range(0, len(contentToScrapeLinks)):
        try: 
            page.goto(
                f'https://terraria.fandom.com{contentToScrapeLinks[links]}'
                )
            time.sleep(random.uniform(2, 10))
            
            soup = BeautifulSoup(page.content(), "lxml")
            content = soup.find("div", class_="mw-parser-output")
            with open("scraped_pages\\" + contentToScrapeLinks[links].replace("/wiki/", "").replace("/", "_") + ".html", "w", encoding="utf-8") as f:
                f.write(str(content))
        except TimeoutError:
            print(f"Skipped (timeout): {links}")
            continue

    browser.close()
