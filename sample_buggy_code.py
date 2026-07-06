def get_orders_for_users(user_ids):
    orders = []
    for uid in user_ids:
        result = db.execute(f"SELECT * FROM orders WHERE user_id = {uid}")
        orders.append(result)
    return orders


def fetch_remote_config():
    response = requests.get("https://config.example.com/settings.json")
    return response.json()


def last_n_items(items, n):
    return items[len(items) - n - 1:]