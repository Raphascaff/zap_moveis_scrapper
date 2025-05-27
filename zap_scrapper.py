from playwright.sync_api import sync_playwright
import json
import pandas as pd
import time
import re
import random

class ZapImoveisScraper:
    def __init__(self, headless=False):
        self.headless = headless
        self.all_listings = []
        
    def setup_browser(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )
        self.context = self.browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = self.context.new_page()

        self.page.set_extra_http_headers({
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Referer': 'https://www.zapimoveis.com.br/',
            'Origin': 'https://www.zapimoveis.com.br'
    })

        
    def human_like_delay(self, min_seconds=1, max_seconds=3):
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        
    def extract_listing_data(self, listing_element):
        try:
            data = {}
            link = listing_element.get_attribute('href')
            data['url'] = f"https://www.zapimoveis.com.br{link}" if link and not link.startswith('http') else link
            full_text = listing_element.inner_text().strip()
            data['full_text'] = full_text
            
            price_selector = "div > div.flex.flex-col.grow.min-w-0.content-stretch.border-neutral-90.min-\\[1280px\\]\\:border-l.pb-2.gap-2 > div.px-2.flex.flex-col.gap-2.md\\:flex-row.md\\:justify-end.md\\:items-end > div > p.text-2-25.text-neutral-120.font-semibold"
            price_element = listing_element.query_selector(price_selector)
            if price_element:
                data['price'] = price_element.inner_text().strip()
            else:
                price_fallback = listing_element.query_selector('p:has-text("R$")')
                data['price'] = price_fallback.inner_text().strip() if price_fallback else 'N/A'
            
            match_condo = re.search(r'Lote/Terreno para comprar em\n([^\n]+)', full_text)
            data['condominium_name'] = match_condo.group(1).strip() if match_condo else 'N/A'
            
            area_selector = "div > div.flex.flex-col.grow.min-w-0.content-stretch.border-neutral-90.min-\\[1280px\\]\\:border-l.pb-2.gap-2 > div.grow.min-h-4.px-2 > ul > li > h3"
            area_element = listing_element.query_selector(area_selector)
            if area_element:
                data['area'] = area_element.inner_text().strip().replace('Tamanho do imóvel\n', '')
            else:
                area_fallback = listing_element.query_selector('li:has-text("m²")')
                data['area'] = area_fallback.inner_text().strip() if area_fallback else 'N/A'

            match = re.search(
                r'Lote/Terreno para comprar em\n(.*?)\n\n(.*?)\n\nTamanho do imóvel', 
                full_text, 
                re.DOTALL
            )
            possible_address = match.group(2).strip() if match else 'N/A'
            if possible_address.lower().startswith('tamanho do imóvel'):
                data['address'] = 'N/A'
            else:
                data['address'] = possible_address
                
            return data
            
        except Exception as e:
            print(f"Error extracting listing data: {e}")
            return None
    
    def scrape_current_page(self):
        print("Extracting listings from current page...")
        self.page.wait_for_timeout(3000)
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
        self.human_like_delay(1, 2)
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        self.human_like_delay(2, 3)
        
        listing_selector = "body > section > div > div.Result_result__5E_aw > div:nth-child(4) > div.listings-wrapper.flex.flex-col.gap-3 > ul > li > a"
        alternative_selectors = [
            "li > a[href*='/imovel/']",
            "a[href*='/terreno/']",
            "a[href*='/lote/']",
            "[data-testid='listing-item'] a",
            ".listing-item a"
        ]
        
        listings = self.page.query_selector_all(listing_selector)
        if not listings:
            print("Main selector didn't find listings, trying alternatives...")
            for alt_selector in alternative_selectors:
                listings = self.page.query_selector_all(alt_selector)
                if listings:
                    print(f"Found {len(listings)} listings with selector: {alt_selector}")
                    break
        if not listings:
            print("No listings found on this page!")
            return []
        
        print(f"Found {len(listings)} listings on this page")
        page_listings = []
        for i, listing in enumerate(listings):
            print(f"Processing listing {i+1}/{len(listings)}")
            data = self.extract_listing_data(listing)
            if data:
                page_listings.append(data)
            self.human_like_delay(0.5, 1)
        return page_listings
    
    def scrape_all_pages(self, start_url, max_pages=None):
        self.setup_browser()
        try:
            print("Starting scraping process...")
            print("Visiting Google first...")
            self.page.goto("https://www.google.com")
            self.human_like_delay(2, 4)
            
            base_url = re.sub(r'([&?])pagina=\d+', '', start_url)
            page_number = 1

            while True:
                current_url = f"{base_url}"
                print(f"\n=== SCRAPING PAGE {page_number}: {current_url} ===")
                response = self.page.goto(current_url, wait_until='domcontentloaded')
                if response.status != 200:
                    print(f"Failed to load page: HTTP {response.status}")
                    break

                page_listings = self.scrape_current_page()
                if page_listings:
                    self.all_listings.extend(page_listings)
                    print(f"Added {len(page_listings)} listings from page {page_number}")
                    print(f"Total listings so far: {len(self.all_listings)}")
                else:
                    print("No listings found on this page - assuming end of results")
                    break
                
                if max_pages and page_number >= max_pages:
                    print(f"Reached maximum pages limit ({max_pages})")
                    break
                page_number += 1
                base_url = re.sub(r'([&?])pagina=\d+', '', start_url)
                self.human_like_delay(2, 4)
                
            print(f"\n=== SCRAPING COMPLETED ===")
            print(f"Total listings collected: {len(self.all_listings)}")
            return self.all_listings
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            return self.all_listings
        finally:
            self.cleanup()
    
    def cleanup(self):
        if hasattr(self, 'browser'):
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
    
    def save_data(self, filename_prefix="zapimoveis_listings"):
        if not self.all_listings:
            print("No data to save!")
            return
        json_filename = f"{filename_prefix}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(self.all_listings, f, indent=2, ensure_ascii=False)
        print(f"Data saved as JSON: {json_filename}")
        
        try:
            df = pd.DataFrame(self.all_listings)
            csv_filename = f"{filename_prefix}.csv"
            df.to_csv(csv_filename, index=False, encoding='utf-8')
            print(f"Data saved as CSV: {csv_filename}")
        except Exception as e:
            print(f"Error saving CSV: {e}")
        
        print(f"\nData Summary:")
        print(f"Total listings: {len(self.all_listings)}")
        if self.all_listings:
            print(f"Sample listing keys: {list(self.all_listings[0].keys())}")

# Uso
if __name__ == "__main__":
    url = '' ## zapmoveis URL com a busca
    
    scraper = ZapImoveisScraper(headless=False)
    listings = scraper.scrape_all_pages(url)  # ou max_pages=N para limitar
    scraper.save_data("boituva_terrenos")
    
    if listings:
        print(json.dumps(listings[0], indent=2, ensure_ascii=False))