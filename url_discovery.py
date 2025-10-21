import requests
import time
import sqlite3
from urllib.parse import urlparse

def get_domain_from_url(url):
    """Extracts the domain from a URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc

def discover_urls(start_url, target_count, username, password, task_id, task_status, task_lock):
    """
    Discovers URLs from a given starting URL up to a target count.
    Updates the task_status dictionary with the progress and persists state in the DB.
    """
    if not start_url.startswith('http'):
        start_url = f"https://{start_url}"

    target_domain = get_domain_from_url(start_url)

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
            c.execute("SELECT COUNT(id) FROM urls WHERE domain_id = ?", (domain_id,))
            discovered_count = c.fetchone()[0]
            with task_lock:
                task_status[task_id]['progress'] = discovered_count

            c.execute("SELECT target_url_count FROM domains WHERE id = ?", (domain_id,))
            current_target = c.fetchone()[0]
            if discovered_count >= current_target:
                break

            c.execute("SELECT url FROM urls WHERE domain_id = ? AND has_been_used_to_find_more_urls = 0 LIMIT 10", (domain_id,))
            urls_to_process = [row[0] for row in c.fetchall()]

            if not urls_to_process:
                break

            for url in urls_to_process:
                print(f"Processing {url}...")
                payload = {"url": url, "parse": True, "parser_preset": "link_parser"}
                try:
                    response = requests.post('https://data.oxylabs.io/v1/queries', auth=(username, password), json=payload)
                    response.raise_for_status()
                    result_pages = [link['href_list'] for link in response.json()['_links'] if link['rel'] == 'results-content-parsed'][0]

                    for page_url in result_pages:
                        time.sleep(5)
                        backoff_time = 1
                        while True:
                            results_response = requests.get(page_url)
                            if results_response.status_code == 200:
                                break
                            time.sleep(backoff_time)
                            backoff_time *= 2

                        for result in results_response.json():
                            for link in result.get('links', []):
                                discovered_url = link.get('url')
                                if discovered_url and get_domain_from_url(discovered_url).endswith(target_domain):
                                    c.execute("INSERT OR IGNORE INTO urls (domain_id, starting_url, url) VALUES (?, ?, ?)", (domain_id, url, discovered_url))

                    c.execute("UPDATE urls SET has_been_used_to_find_more_urls = 1 WHERE url = ?", (url,))
                    conn.commit()

                except requests.exceptions.RequestException as e:
                    print(f"Error processing {url}: {e}")
                    c.execute("UPDATE urls SET has_been_used_to_find_more_urls = 1 WHERE url = ?", (url,))
                    conn.commit()

        c.execute("UPDATE domains SET discovery_status = 'completed' WHERE id = ?", (domain_id,))
        with task_lock:
            task_status[task_id]['status'] = 'completed'
        print(f"URL discovery complete.")

    except Exception as e:
        print(f"A critical error occurred during discovery for {target_domain}: {e}")
        if domain_id:
            c.execute("UPDATE domains SET discovery_status = 'failed' WHERE id = ?", (domain_id,))
        raise
    finally:
        conn.commit()
        conn.close()
