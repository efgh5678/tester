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

def discover_urls(start_url, target_count, username, password, task_id, task_status, task_lock, url_regex=None, session_id=None, rate_limit=10):
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
        c.execute("INSERT OR IGNORE INTO urls (domain_id, starting_url, url, session_id) VALUES (?, ?, ?, ?)", (domain_id, start_url, start_url, session_id))
        conn.commit()

        while True:
            with task_lock:
                if task_status[task_id]['status'] == 'stopped':
                    c.execute("UPDATE domains SET discovery_status = 'stopped' WHERE id = ?", (domain_id,))
                    conn.commit()
                    return

            c.execute("SELECT COUNT(id) FROM urls WHERE domain_id = ? AND session_id = ?", (domain_id, session_id))
            discovered_count = c.fetchone()[0]

            with task_lock:
                task_status[task_id]['progress'] = discovered_count

            if discovered_count >= target_count:
                logging.info(f"Target count of {target_count} reached for {start_url}.")
                break

            c.execute("SELECT url FROM urls WHERE domain_id = ? AND session_id = ? AND has_been_used_to_find_more_urls = 0 LIMIT 1", (domain_id, session_id))
            row = c.fetchone()
            if not row:
                logging.info(f"No more URLs to process for {start_url}.")
                break

            url_to_process = row[0]
            logging.info(f"Processing {url_to_process} for discovery.")
            payload = {"url": url_to_process, "parse": True, "parser_preset": "link_parser"}

            try:
                interval = 1.0 / rate_limit if rate_limit > 0 else 0
                time.sleep(interval)

                response = requests.post('https://data.oxylabs.io/v1/queries', auth=(username, password), json=payload)
                response.raise_for_status()
                result_pages = [link['href_list'] for link in response.json()['_links'] if link['rel'] == 'results-content-parsed'][0]

                for page_url in result_pages:
                    if page_url.startswith('http://data.oxylabs.io'):
                        page_url = page_url.replace('http://', 'https://', 1)

                    backoff_time = 1
                    while True:
                        results_response = requests.get(page_url, auth=(username, password))
                        if results_response.status_code == 200:
                            break
                        time.sleep(backoff_time)
                        backoff_time *= 2

                    results_json = results_response.json()
                    new_urls_found_count = 0

                    def process_links(links_list):
                        nonlocal new_urls_found_count
                        if not links_list: return

                        for link in links_list:
                            candidate_url = link.get('url') if isinstance(link, dict) else str(link)
                            if not candidate_url: continue

                            from urllib.parse import urljoin, urlparse
                            absolute_url = urljoin(url_to_process, candidate_url)
                            parsed = urlparse(absolute_url)
                            if parsed.scheme not in ('http', 'https'): continue

                            if get_domain_from_url(absolute_url).endswith(target_domain):
                                if compiled_regex and not any(p.match(absolute_url) for p in compiled_regex):
                                    continue

                                c.execute("INSERT OR IGNORE INTO urls (domain_id, starting_url, url, session_id) VALUES (?, ?, ?, ?)", (domain_id, start_url, absolute_url, session_id))
                                if c.rowcount > 0:
                                    new_urls_found_count += 1

                    if 'links' in results_json:
                        process_links(results_json.get('links', []))
                    elif 'results' in results_json:
                        for result in results_json.get('results', []):
                            process_links(result.get('content', {}).get('links', []))

                    if new_urls_found_count > 0:
                        logging.info(f"Found {new_urls_found_count} new URLs from {url_to_process}")
                        conn.commit()

                c.execute("UPDATE urls SET has_been_used_to_find_more_urls = 1 WHERE url = ?", (url_to_process,))
                conn.commit()

            except requests.exceptions.RequestException as e:
                error_message = f"Error processing {url_to_process}: {e}"
                logging.error(error_message)
                c.execute("INSERT INTO discovery_logs (domain_name, error_message) VALUES (?, ?)", (target_domain, error_message))
                c.execute("UPDATE urls SET has_been_used_to_find_more_urls = 1 WHERE url = ?", (url_to_process,))
                conn.commit()

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
