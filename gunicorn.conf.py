# Gunicorn configuration for supervisor agent
bind = "0.0.0.0:8000"
workers = 1  # Single worker to prevent memory competition
worker_class = "sync"
timeout = 180  # 3 minutes for complex workflows
keepalive = 2
max_requests = 100  # Restart worker after 100 requests to prevent memory leaks
max_requests_jitter = 10
worker_connections = 1000
preload_app = False  # Don't preload to```ve memory
# worker_tmp_dir = "/dev/shm"  # Remove this line - not available on Mac
worker_tmp_dir = "/tmp"  # Use /tmp instead (works on Mac)

# Logging
loglevel = "info"
accesslog = "-"
errorlog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Memory management
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
