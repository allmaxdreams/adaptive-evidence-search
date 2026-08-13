"""
FastAPI / HTTP Async API Server for VC Due Diligence Copilot.
Exposes endpoints to trigger Due Diligence runs on startups and fetch generated reports.
Ready for deployment on Modal.com, Railway, or Netlify Functions.
"""

import asyncio
import json
import os
import sys

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.append(os.path.join(os.path.dirname(__file__), ".agents", "skills", "adaptive-ontological-search", "scripts"))

from vc_due_diligence_orchestrator import VCDueDiligenceOrchestrator, StartupProfile


class SimpleAPIServer(BaseHTTPRequestHandler):
    orchestrator = VCDueDiligenceOrchestrator()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"status": "healthy", "service": "VC Due Diligence Copilot Engine"}, 200)
        elif parsed.path == "/api/reports":
            json_path = os.path.join(os.path.dirname(__file__), "web", "public", "data", "showcase_reports.json")
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._send_json(data, 200)
            else:
                self._send_json({"error": "No reports found"}, 404)
        else:
            self._send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/analyze":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            try:
                payload = json.loads(body)
                profile = StartupProfile(
                    name=payload.get("name", "Unknown Startup"),
                    category=payload.get("category", "General Tech"),
                    website=payload.get("website", ""),
                    founders=payload.get("founders", []),
                    stated_mission=payload.get("stated_mission", ""),
                    target_market=payload.get("target_market", "")
                )
                
                # Execute due diligence asynchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                report = loop.run_until_complete(self.orchestrator.analyze_startup(profile))
                
                self._send_json(report.dict(), 200)
            except Exception as e:
                self._send_json({"error": str(e)}, 500)
        else:
            self._send_json({"error": "Endpoint not found"}, 404)

    def _send_json(self, data, status_code):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def run_server(port=8080):
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimpleAPIServer)
    print(f"=========================================================================")
    print(f"VC DUE DILIGENCE API SERVER RUNNING ON PORT {port}")
    print(f"=========================================================================\n")
    httpd.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
