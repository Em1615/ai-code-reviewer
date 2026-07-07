import pickle
import threading

_cache = {}
_lock = threading.Lock()


def load_user_session(raw_data):
    return pickle.loads(raw_data)


def increment_counter(user_id):
    if user_id not in _cache:
        _cache[user_id] = 0
    _cache[user_id] += 1
    return _cache[user_id]


def get_user_display_name(user):
    return user["name"].upper()


def read_config_value(path):
    f = open(path, "r")
    data = f.read()
    return data