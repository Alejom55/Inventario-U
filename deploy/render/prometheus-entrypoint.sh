#!/bin/sh
set -eu
case "${API_HOST:-}" in *.onrender.com) ;; *) exit 2;; esac
case "$API_HOST" in *[!a-z0-9.-]*) exit 2;; esac
case "${METRICS_BEARER_TOKEN:-}" in ''|*[!a-f0-9]*) exit 2;; esac
test "${#METRICS_BEARER_TOKEN}" -eq 64
case "${PORT:-10000}" in *[!0-9]*) exit 2;; esac
umask 077
printf '%s' "$METRICS_BEARER_TOKEN" >/tmp/inventory-metrics-token
cat >/tmp/prometheus.yml <<EOF
global:
  scrape_interval: 5s
scrape_configs:
  - job_name: inventory
    scheme: https
    authorization:
      type: Bearer
      credentials_file: /tmp/inventory-metrics-token
    static_configs:
      - targets: ['$API_HOST']
        labels: {track: stable, version: 2.0.0, cloud: render}
EOF
cat >/etc/nginx/conf.d/default.conf <<'EOF'
map_hash_bucket_size 256;
map $http_authorization $metrics_ok { default 0; "Bearer TOKEN_VALUE" 1; }
limit_req_zone $binary_remote_addr zone=queries:10m rate=5r/s;
server {
  listen PORT_VALUE;
  server_tokens off;
  client_max_body_size 16k;
  location = /health { proxy_pass http://127.0.0.1:9090/-/ready; }
  location ~ ^/api/v1/(query|query_range|status/buildinfo|labels|label/[a-zA-Z_][a-zA-Z0-9_]*/values|series|metadata)$ {
    if ($metrics_ok = 0) { return 401; }
    if ($request_method !~ ^(GET|POST)$) { return 405; }
    limit_req zone=queries burst=20 nodelay;
    proxy_read_timeout 10s;
    proxy_set_header Authorization "";
    proxy_pass http://127.0.0.1:9090;
  }
  location = /shared/metrics {
    if ($metrics_ok = 0) { return 401; }
    if ($request_method != GET) { return 405; }
    proxy_set_header Authorization "";
    proxy_pass http://127.0.0.1:9090/federate?match%5B%5D=%7Bjob%3D%22inventory%22%7D;
  }
  location / { return 404; }
}
EOF
sed -i "s/TOKEN_VALUE/$METRICS_BEARER_TOKEN/g; s/PORT_VALUE/${PORT:-10000}/g" /etc/nginx/conf.d/default.conf
prometheus --config.file=/tmp/prometheus.yml --storage.tsdb.path=/tmp/prom-data \
  --storage.tsdb.retention.time=3h --query.timeout=5s --query.max-concurrency=2 \
  --query.max-samples=1000000 --web.listen-address=127.0.0.1:9090 &
exec nginx -g 'daemon off;'
