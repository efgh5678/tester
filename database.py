import sqlite3

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Create domains table
    c.execute('''
        CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY,
            domain_name TEXT UNIQUE NOT NULL,
            target_url_count INTEGER,
            discovery_status TEXT DEFAULT 'pending'
        )
    ''')

    # Create urls table
    c.execute('''
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY,
            domain_id INTEGER,
            starting_url TEXT,
            url TEXT UNIQUE NOT NULL,
            has_been_used_to_find_more_urls BOOLEAN DEFAULT 0,
            FOREIGN KEY (domain_id) REFERENCES domains (id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
