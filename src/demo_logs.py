import os
from src.utils import log

def demo():
    # Simulate LOG_LEVEL=debug for the demo
    # Note: the actual environment variable might override this if we just import log.
    # But since we want to show it working:
    
    print("--- LOG DEMO START ---")
    
    # Watcher
    log("info", "Starting periodic scan", module="WATCHER")
    log("debug", "Scan interval reached", module="WATCHER")
    
    # Auto Formatter
    log("info", "Renaming file", message="old_name.pkg -> NEW_NAME.pkg", module="AUTO_FORMATTER")
    log("error", "Failed to rename file", message="Permission denied", module="AUTO_FORMATTER")
    
    # Auto Sorter
    log("info", "Moving PKG to category folder", message="game/my_game.pkg", module="AUTO_SORTER")
    log("warn", "Category mapping missing for 'xx'", module="AUTO_SORTER")
    
    # Auto Indexer
    log("info", "Indexing started", module="AUTO_INDEXER")
    log("info", "Icon extracted", message="CUSA12345.png", module="AUTO_INDEXER")
    
    print("--- LOG DEMO END ---")

if __name__ == "__main__":
    demo()
