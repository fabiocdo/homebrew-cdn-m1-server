from homebrew_cdn_m1_server.application.app import WorkerApp

if __name__ == "__main__":
    raise SystemExit(WorkerApp.run_from_env())
