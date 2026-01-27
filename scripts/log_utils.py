import settings

def log(action, message):
    if action == "created":
        color = settings.LOG_COLORS["green"]
        prefix = "[+]"
    elif action == "modified":
        color = settings.LOG_COLORS["yellow"]
        prefix = "[*]"
    elif action == "deleted":
        color = settings.LOG_COLORS["red"]
        prefix = "[-]"
    elif action == "error":
        color = settings.LOG_COLORS["pink"]
        prefix = "[!]"
    elif action == "info":
        color = settings.LOG_COLORS["reset"]
        prefix = "[·]"
    else:
        color = settings.LOG_COLORS["reset"]
        prefix = "[*]"
    print(f"{color}{prefix} {message}{settings.LOG_COLORS['reset']}")
