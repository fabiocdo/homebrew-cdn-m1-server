import datetime

class Logger:
    """
    Logger class with modular tagging and color support.
    """

    def __init__(self, name=None, log_level="info"):
        self.levels = {
            "debug": 0,
            "info": 1,
            "warn": 2,
            "error": 3
        }
        self.log_level = self.levels.get(log_level.lower(), 1)
        
        # ANSI Color Codes
        self.colors = {
            "AUTO_INDEXER": "\033[0;92m",   # Green
            "AUTO_SORTER": "\033[1;93m",    # Yellow
            "AUTO_FORMATTER": "\033[1;94m", # Blue
            "WATCHER": "\033[1;97m",        # White
            "RESET": "\033[0m"
        }

        self.level_colors = {
            "debug": "\033[0;90m",  # Gray
            "info": "\033[1;97m",   # White
            "warn": "\033[0;33m",   # Orange/Yellow
            "error": "\033[0;31m"   # Red
        }

    def log(self, level, action, message=None, module=None):
        level_val = self.levels.get(level.lower(), 1)
        if level_val >= self.log_level:
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            
            module_color = self.colors.get(module, "") if module else ""
            level_color = self.level_colors.get(level.lower(), "")
            reset = self.colors["RESET"]
            
            module_str = f"{module_color}[{module}]{reset} " if module else ""
            msg_str = f": {message}" if message else ""
            
            print(f"{timestamp} | {module_str}{level_color}{action}{msg_str}{reset}")
