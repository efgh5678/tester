import requests
import time
import sqlite3
import re
from urllib.parse import urlparse

def get_domain_from_url(url):
    """Extracts the domain from a URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def discover_urls(start_url, target_count, username, password, task_id, task_status, task_lock, url_regex=None):
    """
    Discovers URLs from a given starting URL up to a target count.
    Updates the task_status dictionary with the progress and persists state in the DB.
    """
    logging.info(f"Starting URL discovery for {start_url} with target count {target_count}")
    if not start_url.startswith('http'):
        start_url = f"https://{start_url}"

    target_domain = get_domain_from_url(start_url)

    compiled_regex = []
    if url_regex:
        try:
            compiled_regex = [re.compile(pattern) for pattern in url_regex.splitlines() if pattern]
        except re.error as e:
            logging.error(f"Invalid regex pattern: {e}")
            # Decide how to handle this - fail the task or proceed without regex?
            # For now, let's proceed without regex filtering on error.
            compiled_regex = []

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    domain_id = None

    try:
        # Get or create domain and set status to in_progress
        c.execute("INSERT OR IGNORE INTO domains (domain_name, target_url_count) VALUES (?, ?)", (target_domain, target_count))
        c.execute("UPDATE domains SET target_url_count = ?, discovery_status = 'in_progress' WHERE domain_name = ?", (target_count, target_domain))
        c.execute("SELECT id FROM domains WHERE domain_name = ?", (target_domain,))
        domain_id = c.fetchone()[0]

        # Add starting url if it's not there
        c.execute("INSERT OR IGNORE INTO urls (domain_id, starting_url, url) VALUES (?, ?, ?)", (domain_id, start_url, start_url))
        conn.commit()

        while True:
            # Check if task was stopped
            with task_lock:
                if task_status[task_id]['status'] == 'stopped':
                    c.execute("UPDATE domains SET discovery_status = 'stopped' WHERE id = ?", (domain_id,))
                    return
            
            c.execute("SELECT COUNT(id) FROM urls WHERE domain_id = ?", (domain_id,))
            discovered_count = c.fetchone()[0]
            with task_lock:
                task_status[task_id]['progress'] = discovered_count

            c.execute("SELECT target_url_count FROM domains WHERE id = ?", (domain_id,))
            current_target = c.fetchone()[0]
            if discovered_count >= current_target:
                break

            # Process up to 50 URLs per loop to increase crawl breadth
            c.execute("SELECT url FROM urls WHERE domain_id = ? AND has_been_used_to_find_more_urls = 0 LIMIT 50", (domain_id,))
            urls_to_process = [row[0] for row in c.fetchall()]

            if not urls_to_process:
                break

            for url in urls_to_process:
                # Check if task was stopped before processing each URL
                with task_lock:
                    if task_status[task_id]['status'] == 'stopped':
                        c.execute("UPDATE domains SET discovery_status = 'stopped' WHERE id = ?", (domain_id,))
                        return
                
                logging.info(f"Processing {url} for discovery.")
                payload = {"url": url, "parse": True, "parser_preset": "link_parser"}
                try:
                    response = requests.post('https://data.oxylabs.io/v1/queries', auth=(username, password), json=payload)
                    response.raise_for_status()
                    result_pages = [link['href_list'] for link in response.json()['_links'] if link['rel'] == 'results-content-parsed'][0]

                    for page_url in result_pages:
                        # Oxylabs links may be returned as http; enforce https for auth endpoints
                        if page_url.startswith('http://data.oxylabs.io'):
                            page_url = page_url.replace('http://', 'https://', 1)
                        time.sleep(5)
                        backoff_time = 1
                        while True:
                            # Poll Oxylabs results endpoint (requires auth and https)
                            results_response = requests.get(page_url, auth=(username, password))
                            if results_response.status_code == 200:
                                break
                            time.sleep(backoff_time)
                            backoff_time *= 2

                        results_json = results_response.json()

                        # Helper to process a list of links
                        def process_links(links_list):
                            if not links_list:
                                return
                            new_urls_found = 0
                            for link in links_list:
                                # Normalize link to a string URL
                                if isinstance(link, str):
                                    candidate_url = link
                                else:
                                    candidate_url = link.get('url') if isinstance(link, dict) else str(link)
                                if not candidate_url:
                                    continue
                                # Resolve relative URLs against the current page URL
                                from urllib.parse import urljoin, urlparse
                                absolute_url = urljoin(url, candidate_url)
                                # Skip non-http(s) schemes like mailto:, javascript:, etc.
                                parsed = urlparse(absolute_url)
                                if parsed.scheme not in ('http', 'https'):
                                    continue
                                # Filter by target domain (allow subdomains)
                                if get_domain_from_url(absolute_url).endswith(target_domain):
                                    # If regex patterns are provided, check if the URL matches any of them
                                    if compiled_regex:
                                        if not any(p.match(absolute_url) for p in compiled_regex):
                                            continue  # Skip if no regex matches

                                    c.execute("INSERT OR IGNORE INTO urls (domain_id, starting_url, url) VALUES (?, ?, ?)", (domain_id, url, absolute_url))
                                    if c.rowcount > 0:
                                        new_urls_found += 1
                            logging.info(f"Found {new_urls_found} new URLs from {url}")

                        # Shape A: content links returned directly at top level
                        if isinstance(results_json, dict) and 'links' in results_json:
                            process_links(results_json.get('links', []))
                        else:
                            # Shape B: envelope with results[] each containing content.links
                            results = results_json.get('results', [])
                            if results:
                                for result in results:
                                    content = result.get('content', {})
                                    process_links(content.get('links', []))

                    c.execute("UPDATE urls SET has_been_used_to_find_more_urls = 1 WHERE url = ?", (url,))
                    conn.commit()

                except requests.exceptions.RequestException as e:
                    error_message = f"Error processing {url}: {e}"
                    print(error_message)
                    c.execute("INSERT INTO discovery_logs (domain_name, error_message) VALUES (?, ?)", (target_domain, error_message))
                    conn.commit()
                    with task_lock:
                        task_status[task_id]['status'] = 'failed'
                        task_status[task_id]['error'] = str(e)
                    c.execute("UPDATE urls SET has_been_used_to_find_more_urls = 1 WHERE url = ?", (url,))
                    conn.commit()
                    return

        c.execute("UPDATE domains SET discovery_status = 'completed' WHERE id = ?", (domain_id,))
        with task_lock:
            task_status[task_id]['status'] = 'completed'
        logging.info(f"URL discovery complete for {start_url}.")

    except Exception as e:
        error_message = f"A critical error occurred during discovery for {target_domain}: {e}"
        print(error_message)
        c.execute("INSERT INTO discovery_logs (domain_name, error_message) VALUES (?, ?)", (target_domain, error_message))
        conn.commit()
        if domain_id:
            c.execute("UPDATE domains SET discovery_status = 'failed' WHERE id = ?", (domain_id,))
        raise
    finally:
        conn.commit()
        conn.close()
