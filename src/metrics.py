"""Lightweight Prometheus metrics server for the pipeline producer."""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Simple counters (no external dependency needed)
_metrics = {
    "pipeline_records_produced_total": 0,
    "pipeline_batches_sent_total": 0,
    "pipeline_errors_total": 0,
}
_lock = threading.Lock()


def inc(name: str, value: int = 1) -> None:
    with _lock:
        _metrics[name] = _metrics.get(name, 0) + value


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        with _lock:
            lines = []
            for k, v in _metrics.items():
                lines.append(f"# TYPE {k} counter")
                lines.append(f"{k} {v}")
            self.wfile.write("\n".join(lines).encode())

    def log_message(self, format, *args):
        pass  # suppress request logs


def start_metrics_server(port: int = 9309) -> None:
    """Start a background HTTP server exposing Prometheus metrics."""
    server = HTTPServer(("0.0.0.0", port), _MetricsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
