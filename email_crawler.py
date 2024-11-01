import os
import re
import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urljoin
from dotenv import load_dotenv
from tqdm import tqdm
from typing import Set, Dict, List
import concurrent.futures
import time


class EmailCrawler:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('GOOGLE_API_KEY')
        self.cse_id = os.getenv('GOOGLE_CSE_ID')
        self.found_emails: Dict[str, Set[str]] = {}
        self.sites_visited = 0
        self.google_pages_crawled = 0

        if not self.api_key or not self.cse_id:
            raise ValueError("Missing API key or Search Engine ID in .env file")

    def extract_emails(self, text: str) -> Set[str]:
        """Extract email addresses from text using regex."""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return set(re.findall(email_pattern, text))

    def get_page_content(self, url: str) -> str:
        """Fetch page content with error handling."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            self.sites_visited += 1
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return ""

    def find_contact_pages(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Find potential contact page URLs."""
        contact_links = []
        contact_keywords = ['contact', 'about', 'team', 'staff', 'directory', 'about-us']

        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.text.lower()

            if any(keyword in href or keyword in text for keyword in contact_keywords):
                full_url = urljoin(base_url, href)
                if full_url.startswith(('http://', 'https://')):
                    contact_links.append(full_url)

        return list(set(contact_links))

    def crawl_page(self, url: str) -> None:
        """Crawl a single page and its contact pages for email addresses."""
        content = self.get_page_content(url)
        if not content:
            return

        soup = BeautifulSoup(content, 'html.parser')
        emails = self.extract_emails(content)

        if emails:
            self.found_emails[url] = emails

        # Find and crawl contact pages
        contact_pages = self.find_contact_pages(soup, url)
        for contact_url in contact_pages:
            if contact_url not in self.found_emails:
                contact_content = self.get_page_content(contact_url)
                if contact_content:
                    contact_emails = self.extract_emails(contact_content)
                    if contact_emails:
                        self.found_emails[contact_url] = contact_emails

    def google_search(self, query: str, num_pages: int = 2) -> List[str]:
        """Perform Google search and return URLs."""
        try:
            service = build("customsearch", "v1", developerKey=self.api_key)
            urls = []

            for i in range(num_pages):
                self.google_pages_crawled += 1
                start_index = i * 10 + 1
                result = service.cse().list(
                    q=query,
                    cx=self.cse_id,
                    start=start_index
                ).execute()

                if 'items' in result:
                    urls.extend([item['link'] for item in result['items']])

                time.sleep(1)  # Respect rate limits

            return urls
        except HttpError as e:
            print(f"Error performing Google search: {str(e)}")
            return []

    def search_and_crawl(self, query: str) -> Dict[str, Set[str]]:
        """Main method to search Google and crawl results for emails."""
        print(f"Searching for: {query}")
        urls = self.google_search(query)

        if not urls:
            print("No URLs found in search results")
            return {}

        print(f"Found {len(urls)} URLs to crawl")

        # Use ThreadPoolExecutor for parallel crawling
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            list(tqdm(executor.map(self.crawl_page, urls), total=len(urls)))

        return self.found_emails

    def print_summary(self):
        """Print summary statistics of the crawl."""
        total_emails = set()
        for emails in self.found_emails.values():
            total_emails.update(emails)

        print("\n=== CRAWL SUMMARY ===")
        print(f"Google pages crawled: {self.google_pages_crawled}")
        print(f"Total sites visited: {self.sites_visited}")
        print(f"Sites with emails found: {len(self.found_emails)}")
        print(f"Total unique emails found: {len(total_emails)}")

        print("\nAll unique emails:")
        print(", ".join(sorted(total_emails)))


def main():
    try:
        crawler = EmailCrawler()
        query = input("Enter your search query: ")

        results = crawler.search_and_crawl(query)

        if results:
            print("\nFound email addresses:")
            for i, (url, emails) in enumerate(results.items(), 1):
                print(f"\n{i}. URL: {url}")
                print(f"   Emails: {', '.join(emails)}")

            crawler.print_summary()
        else:
            print("No email addresses found.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()