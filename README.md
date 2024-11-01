# Email Crawler

A Python script that crawls websites to find email addresses using Google Custom Search API.

## Features

- Uses Google Custom Search API to find relevant websites
- Crawls main pages and contact pages
- Extracts email addresses using regex pattern matching
- Supports multithreaded crawling
- Includes detailed logging and debug mode
- Progress bar for crawling status

## Prerequisites

- Python 3.7+
- Google API Key
- Google Custom Search Engine ID

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your credentials:
   ```bash
   cp .env.example .env
   ```
4. Edit `.env` file with your Google API credentials:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   GOOGLE_CSE_ID=your_custom_search_engine_id_here
   ```

## Usage

Run the script:
```bash
python email_crawler.py
```

You will be prompted to:
1. Enter your search query
2. Specify number of pages to crawl (default: 2)
3. Enable/disable debug mode (default: False)

## Output

- Console output shows progress and found email addresses
- Detailed logs are saved in the `logs` directory
- Debug information (if enabled) includes:
  - Pages crawled
  - Contact pages found
  - Emails discovered
  - Any errors encountered

## License

MIT License