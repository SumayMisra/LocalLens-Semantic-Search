"""One shared model, threaded requests; no request-body/access logging."""
import os
bind = f"{os.environ.get('BIND_HOST', '127.0.0.1')}:{os.environ.get('PORT', '5000')}"
workers = 1
threads = 4
timeout = 120
accesslog = None
errorlog = '-'
