import os
import sqlite3
import uuid
import threading
import requests
import json
import time
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from database import init_db
from url_discovery import discover_urls
from urllib.parse import urlparse

def get_domain_from_url(url):
    """Extracts the domain from a URL."""
    parsed_url = urlparse(url)
    return parsed_url.netloc

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Use environment variables for credentials
OXYLABS_USERNAME = os.environ.get('OXYLABS_USERNAME')
OXYLABS_PASSWORD = os.environ.get('OXYLABS_PASSWORD')

if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
    raise ValueError("OXYLABS_USERNAME and OXYLABS_PASSWORD must be set in .env file")

# In-memory store for task progress
task_status = {}
task_lock = threading.Lock()
# Store for running threads to allow stopping
running_threads = {}
thread_lock = threading.Lock()

@app.route('/')
@app.route('/<session_id>')
def index(session_id=None):
    return render_template('index.html', session_id=session_id)

@app.route('/discover', methods=['POST'])
def discover():
    data = request.get_json()
    start_urls = data.get('urls')
    target_count = data.get('count')
    url_regex = data.get('regex')

    if not start_urls or not target_count:
        return jsonify({'error': 'Missing urls or count'}), 400

    session_id = str(uuid.uuid4())
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO discovery_sessions (id) VALUES (?)", (session_id,))
    conn.commit()
    conn.close()

    task_ids = []
    for start_url in start_urls:
        task_id = str(uuid.uuid4())
        with task_lock:
            task_status[task_id] = {
                'status': 'pending',
                'progress': 0,
                'total': target_count,
                'url': start_url,
                'session_id': session_id
            }
        task_ids.append(task_id)

        def run_discovery(start_url, task_id, url_regex, session_id):
            try:
                discover_urls(start_url, target_count, OXYLABS_USERNAME, OXYLABS_PASSWORD, task_id, task_status, task_lock, url_regex, session_id)
            except Exception as e:
                with task_lock:
                    task_status[task_id]['status'] = 'failed'
                    task_status[task_id]['error'] = str(e)
            finally:
                with thread_lock:
                    if task_id in running_threads:
                        del running_threads[task_id]

        thread = threading.Thread(target=run_discovery, args=(start_url, task_id, url_regex, session_id))
        with thread_lock:
            running_threads[task_id] = thread
        thread.start()

    return jsonify({'task_ids': task_ids, 'session_id': session_id})

@app.route('/status/<task_id>', methods=['GET'])
def get_status(task_id):
    with task_lock:
        task = task_status.get(task_id).copy()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)

@app.route('/domains', methods=['GET'])
def get_domains():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT domain_name FROM domains")
    domains = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(domains)

@app.route('/urls/<domain>', methods=['GET'])
def get_urls(domain):
    session_id = request.args.get('session_id')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM domains WHERE domain_name = ?", (domain,))
    domain_id = c.fetchone()
    if not domain_id:
        return jsonify({'error': 'Domain not found'}), 404

    domain_id = domain_id[0]

    if session_id:
        c.execute("SELECT url FROM urls WHERE domain_id = ? AND session_id = ?", (domain_id, session_id))
    else:
        c.execute("SELECT url FROM urls WHERE domain_id = ?", (domain_id,))

    urls = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(urls)

@app.route('/urls/session/<session_id>', methods=['GET'])
def get_session_urls(session_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT url FROM urls WHERE session_id = ?", (session_id,))
    urls = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(urls)

@app.route('/discovery-logs', methods=['GET'])
def get_discovery_logs():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT domain_name, error_message, timestamp FROM discovery_logs ORDER BY timestamp DESC")
    logs = [{'domain': row[0], 'error': row[1], 'timestamp': row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(logs)


import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/create-jobs', methods=['POST'])
def create_jobs():
    logging.info("Received request to create jobs")
    data = request.get_json()
    urls = data.get('urls')
    logging.info(f"Processing {len(urls)} URLs")
    target_count = data.get('target_count')
    rate_limit = data.get('rate_limit', 10)
    custom_params_str = data.get('custom_params', '{}')

    if not urls or not target_count:
        return jsonify({'error': 'Missing urls or target_count'}), 400

    if target_count > len(urls):
        urls_to_process = random.choices(urls, k=target_count)
    else:
        urls_to_process = urls

    urls_by_domain = {}
    for url in urls_to_process:
        domain = get_domain_from_url(url)
        if domain not in urls_by_domain:
            urls_by_domain[domain] = []
        urls_by_domain[domain].append(url)

    task_ids = []
    for domain, domain_urls in urls_by_domain.items():
        task_id = str(uuid.uuid4())
        with task_lock:
            task_status[task_id] = {
                'status': 'pending',
                'progress': 0,
                'total': len(domain_urls),
                'domain': domain
            }
        task_ids.append(task_id)

        def run_job_creation(domain_urls, task_id):
            logging.info(f"Starting job creation for domain {domain} with {len(domain_urls)} URLs")
            try:
                custom_params = json.loads(custom_params_str) if custom_params_str else {}
            except json.JSONDecodeError:
                with task_lock:
                    task_status[task_id]['status'] = 'failed'
                    task_status[task_id]['error'] = 'Invalid custom JSON parameters'
                return

            payload = {"url": []}
            payload.update(custom_params)
            successful_creations = 0

            while successful_creations < len(domain_urls):
                with task_lock:
                    if task_status[task_id]['status'] == 'stopped':
                        return

                remaining_target = len(domain_urls) - successful_creations
                current_batch_size = min(100, remaining_target)
                batch_urls = domain_urls[successful_creations:successful_creations + current_batch_size]
                payload['url'] = batch_urls
                interval = len(batch_urls) / rate_limit if rate_limit > 0 else 0

                try:
                    response = requests.post(
                        'https://data.oxylabs.io/v1/queries/batch',
                        auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
                        json=payload
                    )
                    response.raise_for_status()
                    successful_creations += len(response.json().get('queries', []))
                except requests.exceptions.RequestException as e:
                    with task_lock:
                        task_status[task_id]['status'] = 'failed'
                        task_status[task_id]['error'] = f"Failed to create a batch of jobs: {e}"
                    return

                with task_lock:
                    task_status[task_id]['progress'] = successful_creations
                time.sleep(interval)

            with task_lock:
                if task_status[task_id]['status'] != 'stopped':
                    task_status[task_id]['status'] = 'completed'
            logging.info(f"Job creation complete for domain {domain}")
            with thread_lock:
                if task_id in running_threads:
                    del running_threads[task_id]

        thread = threading.Thread(target=run_job_creation, args=(domain_urls, task_id))
        with thread_lock:
            running_threads[task_id] = thread
        thread.start()

    return jsonify({'task_ids': task_ids})

@app.route('/stop/<task_id>', methods=['POST'])
def stop_task(task_id):
    """Stop a running task"""
    with task_lock:
        if task_id not in task_status:
            return jsonify({'error': 'Task not found'}), 404
        
        if task_status[task_id]['status'] in ['completed', 'failed', 'stopped']:
            return jsonify({'error': 'Task is not running'}), 400
        
        task_status[task_id]['status'] = 'stopped'
    
    with thread_lock:
        if task_id in running_threads:
            # Note: We can't forcefully stop Python threads, but we've marked the task as stopped
            # The thread will check this status and exit gracefully
            pass
    
    return jsonify({'message': 'Task stop requested'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
