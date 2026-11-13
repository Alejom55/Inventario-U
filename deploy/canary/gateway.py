"""Generate one auditable Nginx split; stage changes use atomic replacement."""

import re


def render(percent, api_key):
    if type(percent) is not int or percent not in {0, 10, 50, 100}:
        raise ValueError("Supported stages: 0, 10, 50, 100")
    if not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", api_key):
        raise ValueError("Invalid API key")
    split = f"{percent}% canary; * stable;" if percent in {10, 50} else f"* {'canary' if percent == 100 else 'stable'};"
    return f'''# Generated stage {percent}; change with rollout.py only.
map_hash_bucket_size 256;
upstream stable {{ server stable:8000; keepalive 16; }}
upstream canary {{ server canary:8000; keepalive 16; }}
map $http_x_api_key $authorized {{ default 0; "{api_key}" 1; }}
split_clients "$request_id" $public_track {{ {split} }}
map "$authorized:$http_x_canary" $selected {{ default $public_track; "1:true" canary; "1:baseline" stable; }}
map $selected $api_prefix {{ stable /api/v2; canary /api/v3; }}
server {{
    listen 8000;
    server_tokens off;
    client_max_body_size 2m;
    proxy_connect_timeout 3s;
    proxy_read_timeout 10s;
    proxy_next_upstream off;
    proxy_set_header Host $host;
    proxy_set_header X-Trace-Id $request_id;
    location = /metrics {{ return 404; }}
    location /api/live/ {{
        rewrite ^/api/live/(.*)$ $api_prefix/$1 break;
        proxy_pass http://$selected;
    }}
    location /api/v3/ {{
        if ($authorized = 0) {{ return 403; }}
        proxy_pass http://canary;
    }}
    location /grafana/ {{
        proxy_pass http://grafana:3000;
    }}
    location / {{ proxy_pass http://stable; }}
}}
'''
