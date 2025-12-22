import asyncio
import random
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"
    )
    page = context.new_page()
    page.goto("https://terraria.fandom.com/wiki/Terraria_Wiki")
    time.sleep(random.randint(5, 15))

    doc = BeautifulSoup(page.content(), "html.parser")
    tags = doc.find_all('li')
    time.sleep(random.randint(5, 20))
    print(tags[0])
    browser.close() 