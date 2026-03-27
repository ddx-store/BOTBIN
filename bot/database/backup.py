import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
USERS_JSON = DATA_DIR / "users.json"
BACKUP_DIR = Path("./backups")
BACKUP_DIR.mkdir(exist_ok=True)


def local_register_user(user_id, username, first_name):
    try:
        users = {}
        if USERS_JSON.exists():
            try:
                users = json.loads(USERS_JSON.read_text(encoding="utf-8"))
            except Exception:
                pass

        str_id = str(user_id)
        if str_id not in users:
            users[str_id] = {
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            USERS_JSON.write_text(
                json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            timestamp = datetime.now().strftime("%Y%m%d")
            daily_backup = BACKUP_DIR / f"users_backup_{timestamp}.json"
            if not daily_backup.exists():
                daily_backup.write_text(
                    json.dumps(users, ensure_ascii=False), encoding="utf-8"
                )
    except Exception:
        pass


def get_local_user_count():
    try:
        if USERS_JSON.exists():
            data = json.loads(USERS_JSON.read_text(encoding="utf-8"))
            return len(data)
    except Exception:
        pass
    return 0


def get_local_user_ids():
    try:
        if USERS_JSON.exists():
            data = json.loads(USERS_JSON.read_text(encoding="utf-8"))
            return [int(uid) for uid in data.keys()]
    except Exception:
        pass
    return []


def get_local_user_info(user_id: int) -> dict | None:
    try:
        if USERS_JSON.exists():
            data = json.loads(USERS_JSON.read_text(encoding="utf-8"))
            info = data.get(str(user_id))
            if info:
                return {
                    "user_id":       user_id,
                    "username":      info.get("username"),
                    "first_name":    info.get("first_name"),
                    "is_banned":     False,
                    "is_premium":    False,
                    "premium_until": None,
                    "request_count": 0,
                    "gen_count":     0,
                    "joined_at":     info.get("joined_at", ""),
                }
    except Exception:
        pass
    return None


def get_all_local_users() -> list:
    try:
        if USERS_JSON.exists():
            data = json.loads(USERS_JSON.read_text(encoding="utf-8"))
            result = []
            for uid, info in data.items():
                result.append((
                    int(uid),
                    info.get("username"),
                    info.get("first_name"),
                    info.get("joined_at", ""),
                ))
            return sorted(result, key=lambda x: x[3], reverse=True)
    except Exception:
        pass
    return []
