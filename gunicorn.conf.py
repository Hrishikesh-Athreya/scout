# Add settings one by one to identify what breaks logging
bind = "0.0.0.0:8000"
workers = 1
timeout = 180
worker_tmp_dir = "/tmp"

# Core logging (keep these)
loglevel = "info"
accesslog = "-"
errorlog = "-"

# Add these back gradually:
# max_requests = 100
# max_requests_jitter = 10
# preload_app = False
# worker_connections = 1000
