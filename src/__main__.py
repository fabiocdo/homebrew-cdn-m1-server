from src.modules import AutoFormatter, AutoIndexer

def start():
    indexer = AutoIndexer()

    # indexer.dry_run()
    indexer.run()

if __name__ == "__main__":
    start()
