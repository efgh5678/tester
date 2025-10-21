import os
import sqlite3
import uuid
import threading
import requests
import json
import time
from flask import Flask, render_template, request, jsonify
from url_discovery import discover_urls

app = Flask(__name__)

# Use environment variables for credentials
OXYLABS_USERNAME = os.environ.get('OXYLABS_USERNAME')
OXYLABS_PASSWORD = os.environ.get('OXYLABS_PASSWORD')

if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
    raise ValueError("OXYLABS_USERNAME and OXYLABS_PASSWORD environment variables must be set")

# In-memory store for task progress
task_status = {}
task_lock = threading.Lock()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/discover', methods=['POST'])
def discover():
    data = request.get_json()
    start_url = data.get('url')
    target_count = data.get('count')

    if not start_url or not target_count:
        return jsonify({'error': 'Missing url or count'}), 400

    task_id = str(uuid.uuid4())
    with task_lock:
        task_status[task_id] = {'status': 'pending', 'progress': 0, 'total': target_count}

    def run_discovery():
        try:
            discover_urls(start_url, target_count, OXYLABS_USERNAME, OXYLABS_PASSWORD, task_id, task_status, task_lock)
        except Exception as e:
            with task_lock:
                task_status[task_id]['status'] = 'failed'
                task_status[task_id]['error'] = str(e)

    thread = threading.Thread(target=run_discovery)
    thread.start()

    return jsonify({'task_id': task_id})

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
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM domains WHERE domain_name = ?", (domain,))
    domain_id = c.fetchone()
    if not domain_id:
        return jsonify({'error': 'Domain not found'}), 404

    c.execute("SELECT url FROM urls WHERE domain_id = ?", (domain_id[0],))
    urls = [row[0] for row in c.fetchall()]
    conn.close()
    return jsonify(urls)


@app.route('/create-jobs', methods=['POST'])
def create_jobs():
    data = request.get_json()
    urls = data.get('urls')
    target_count = data.get('target_count')
    rate_limit = data.get('rate_limit', 10)
    custom_params_str = data.get('custom_params', '{}')

    if not urls or not target_count:
        return jsonify({'error': 'Missing urls or target_count'}), 400

    task_id = str(uuid.uuid4())
    with task_lock:
        task_status[task_id] = {'status': 'pending', 'progress': 0, 'total': target_count}

    def run_job_creation():
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

        urls_to_process = urls

        while successful_creations < target_count and urls_to_process:
            remaining_target = target_count - successful_creations
            current_batch_size = min(100, remaining_target, len(urls_to_process))

            batch_urls = urls_to_process[:current_batch_size]
            urls_to_process = urls_to_process[current_batch_size:]
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
                print(f"Error creating batch jobs: {e}")
                with task_lock:
                    task_status[task_id]['status'] = 'failed'
                    task_status[task_id]['error'] = f"Failed to create a batch of jobs: {e}"
                return

            with task_lock:
                task_status[task_id]['progress'] = successful_creations
            time.sleep(interval)

        with task_lock:
            task_status[task_id]['status'] = 'completed'

    thread = threading.Thread(target=run_job_creation)
    thread.start()

    return jsonify({'task_id': task_id})

if __name__ == '__main__':
    app.run(debug=True)
