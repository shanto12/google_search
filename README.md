# Email Crawler

This script searches Google for specific keywords and crawls the results to find email addresses.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Environment variables are already set up in the `.env` file with your:
   - Google API Key
   - Custom Search Engine ID

## Usage

Run the script:
```bash
python email_crawler.py
```

The script will:
1. Prompt for your search query
2. Search Google using the Custom Search API
3. Crawl each result and its contact pages
4. Extract and deduplicate email addresses
5. Display results with source URLs

## Features

- Parallel crawling for faster results
- Smart contact page detection
- Rate limiting to respect website policies
- Progress bar for crawling status
- Error handling for invalid URLs and timeouts
- Email deduplication
- Source URL tracking

## Note

Please use responsibly and in accordance with websites' terms of service and robots.txt files.