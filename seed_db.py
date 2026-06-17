from web_dashboard import initialize_database, ensure_seed_data

if __name__ == '__main__':
    initialize_database()
    ensure_seed_data()
    print('[+] Seed complete: ecoshield.db created with demo users.')
