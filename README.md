# Oxylabs Web Scraper API Testing Tool

This is a web-based tool for testing the Oxylabs Web Scraper API. It allows you to discover URLs from a website, select a subset of those URLs, and create bulk scraping jobs with a configurable rate limit.

## Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.6+
- `pip` for Python

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set the environment variables:**
    You need to provide your Oxylabs API credentials as environment variables.
    ```bash
    export OXYLABS_USERNAME='your_username'
    export OXYLABS_PASSWORD='your_password'
    ```

5.  **Initialize the database:**
    Run the following command to create the SQLite database file (`database.db`) and the necessary tables.
    ```bash
    python database.py
    ```

## Usage

1.  **Start the application:**
    ```bash
    python app.py
    ```

2.  **Open the web interface:**
    Open your web browser and navigate to `http://127.0.0.1:5000`.

3.  **Step 1: Discover URLs**
    -   Enter a domain name or a full starting URL (e.g., `example.com`).
    -   Enter the target number of URLs you want to discover.
    -   Click "Discover URLs". The application will start discovering URLs in the background. You will see a progress indicator update in real-time.

4.  **Step 2: Select URLs**
    -   Once the URL discovery is complete, the discovered domain will appear in the dropdown menu.
    -   Select a domain to view the list of discovered URLs.
    -   You can filter the URLs by typing in the filter box and sort them alphabetically.
    -   Use the checkboxes to select the URLs you want to use for creating scraping jobs. The "Select All" and "Unselect All" buttons will apply to the currently filtered view.

5.  **Step 3: Create Bulk Jobs**
    -   Enter the total number of scraping jobs you want to create.
    -   Set the desired rate limit in jobs per second.
    -   Optionally, add any custom JSON parameters to be included in each job payload.
    -   Click "Create Jobs". The application will start creating the jobs in the background, and you will see a progress indicator.
