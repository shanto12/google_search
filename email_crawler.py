import os
import re
import requests
import logging
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from urllib.parse import urljoin
from dotenv import load_dotenv
from tqdm import tqdm
from typing import Set, Dict, List, Tuple
import concurrent.futures
import time
from dataclasses import dataclass, field
from datetime import datetime

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Set up logging
log_filename = f"logs/email_crawler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# File handler for logging to file
file_handler = logging.FileHandler(log_filename)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)


@dataclass
class PageDebugInfo:
    url: str
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    main_page_crawled: bool = False
    emails_found: Set[str] = field(default_factory=set)
    contact_pages_found: List[str] = field(default_factory=list)
    contact_pages_crawled: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class EmailCrawler:
    def __init__(self, debug_mode: bool = False):
        load_dotenv()
        self.api_key = os.getenv('GOOGLE_API_KEY')
        self.cse_id = os.getenv('GOOGLE_CSE_ID')
        self.found_emails: Dict[str, Set[str]] = {}
        self.sites_visited = 0
        self.google_pages_crawled = 0
        self.debug_mode = debug_mode
        self.debug_info: Dict[str, PageDebugInfo] = {}

        if not self.api_key or not self.cse_id:
            raise ValueError("Missing API key or Search Engine ID in .env file")

    def extract_emails(self, text: str) -> Set[str]:
        """Extract email addresses from text using regex."""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return set(re.findall(email_pattern, text))

    def get_page_content(self, url: str) -> Tuple[str, bool]:
        """Fetch page content with error handling."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            self.sites_visited += 1
            logger.info(f"Successfully fetched content from: {url}")
            return response.text, True
        except Exception as e:
            error_msg = f"Error fetching {url}: {str(e)}"
            logger.error(error_msg)
            if self.debug_mode and url in self.debug_info:
                self.debug_info[url].errors.append(error_msg)
            return "", False

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
        logger.info(f"Starting crawl for: {url}")
        if self.debug_mode:
            self.debug_info[url] = PageDebugInfo(url=url)

        content, success = self.get_page_content(url)
        if not success:
            return

        if self.debug_mode:
            self.debug_info[url].main_page_crawled = True

        soup = BeautifulSoup(content, 'html.parser')
        emails = self.extract_emails(content)

        if emails:
            self.found_emails[url] = emails
            logger.info(f"Found {len(emails)} emails on {url}")
            if self.debug_mode:
                self.debug_info[url].emails_found.update(emails)

        contact_pages = self.find_contact_pages(soup, url)
        logger.info(f"Found {len(contact_pages)} contact pages on {url}")
        if contact_pages:
            for i, contact_url in enumerate(contact_pages, 1):
                logger.info(f"  {i}. {contact_url}")

        if self.debug_mode:
            self.debug_info[url].contact_pages_found = contact_pages

        for contact_url in contact_pages:
            if contact_url not in self.found_emails:
                contact_content, success = self.get_page_content(contact_url)
                if self.debug_mode:
                    self.debug_info[url].contact_pages_crawled[contact_url] = success

                if success and contact_content:
                    contact_emails = self.extract_emails(contact_content)
                    if contact_emails:
                        self.found_emails[contact_url] = contact_emails
                        logger.info(f"Found {len(contact_emails)} emails on contact page: {contact_url}")
                        if self.debug_mode:
                            self.debug_info[url].emails_found.update(contact_emails)

    def google_search(self, query: str, num_pages: int) -> List[str]:
        """Perform Google search and return URLs."""
        try:
            service = build("customsearch", "v1", developerKey=self.api_key)
            urls = []

            for i in range(num_pages):
                self.google_pages_crawled += 1
                start_index = i * 10 + 1
                print(f"Searching Google page {i + 1}")
                logger.info(f"Searching Google page {i + 1}")
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
            error_msg = f"Error performing Google search: {str(e)}"
            print(error_msg)
            logger.error(error_msg)
            return []

    def search_and_crawl(self, query: str, num_pages: int) -> Dict[str, Set[str]]:
        """Main method to search Google and crawl results for emails."""
        print(f"Searching for: {query}")
        logger.info(f"Starting search for query: {query}")
        urls = self.google_search(query, num_pages)

        if not urls:
            print("No URLs found in search results")
            logger.warning("No URLs found in search results")
            return {}

        print(f"Found {len(urls)} URLs to crawl")
        logger.info(f"Found {len(urls)} URLs to crawl")

        # Use ThreadPoolExecutor for parallel crawling
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            list(tqdm(executor.map(self.crawl_page, urls), total=len(urls)))

        return self.found_emails

    def log_debug_info(self):
        """Log detailed debug information."""
        logger.info("\n=== DEBUG INFORMATION ===")
        for url, info in self.debug_info.items():
            logger.info(f"\nPage: {url}")
            logger.info(f"Timestamp: {info.timestamp}")
            logger.info(f"Main page successfully crawled: {info.main_page_crawled}")
            logger.info(f"Emails found: {len(info.emails_found)}")
            if info.emails_found:
                logger.info(f"  - {', '.join(sorted(info.emails_found))}")

            logger.info(f"Contact pages found: {len(info.contact_pages_found)}")
            if info.contact_pages_found:
                for i, contact_url in enumerate(info.contact_pages_found, 1):
                    status = info.contact_pages_crawled.get(contact_url, "Not crawled")
                    logger.info(f"  {i}. {contact_url} (Crawled: {status})")

            if info.errors:
                logger.info("Errors encountered:")
                for error in info.errors:
                    logger.info(f"  - {error}")
            logger.info("-" * 80)

    def print_summary(self):
        """Print summary statistics of the crawl."""
        total_emails = set()
        for emails in self.found_emails.values():
            total_emails.update(emails)

        summary = [
            "\n=== CRAWL SUMMARY ===",
            f"Google pages crawled: {self.google_pages_crawled}",
            f"Total sites visited: {self.sites_visited}",
            f"Sites with emails found: {len(self.found_emails)}",
            f"Total unique emails found: {len(total_emails)}",
            "\nAll unique emails:",
            ", ".join(sorted(total_emails))
        ]

        # Print to console
        print("\n".join(summary))

        # Log to file
        logger.info("\n".join(summary))


def main():
    try:
        query = input("Enter your search query: ")
        pages_input = input("Enter number of pages to crawl [default=2]: ").strip()
        debug_input = input("Enable debug mode? (True/False) [default=False]: ").strip().lower()

        num_pages = int(pages_input) if pages_input else 2
        debug_mode = debug_input in ('true', 't', 'yes', 'y', '1')

        logger.info(f"Starting crawler with query: {query}, pages: {num_pages}, debug: {debug_mode}")

        crawler = EmailCrawler(debug_mode=debug_mode)
        results = crawler.search_and_crawl(query, num_pages)

        if results:
            print("\nFound email addresses:")
            for i, (url, emails) in enumerate(results.items(), 1):
                result_line = f"\n{i}. URL: {url}\n   Emails: {', '.join(emails)}"
                print(result_line)
                logger.info(result_line)

            crawler.print_summary()

            if debug_mode:
                crawler.log_debug_info()
                print(f"\nDetailed debug information has been saved to: {log_filename}")
        else:
            print("No email addresses found.")
            logger.warning("No email addresses found.")

    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        print(error_msg)
        logger.error(error_msg)


if __name__ == "__main__":
    main()