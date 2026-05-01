"""Minimal HTTP server that mimics nginx autoindex JSON for testing."""
import http.server
import json
import os

class AutoindexHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve /workflows/ as nginx autoindex JSON
        if self.path.rstrip('/') == '/workflows':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            wf_dir = os.path.join(os.path.dirname(__file__), 'workflows')
            files = []
            for f in os.listdir(wf_dir):
                if f.endswith('.json'):
                    fp = os.path.join(wf_dir, f)
                    files.append({
                        "name": f,
                        "type": "file",
                        "mtime": "",
                        "size": os.path.getsize(fp)
                    })
            self.wfile.write(json.dumps(files).encode())
            return
        super().do_GET()

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = http.server.HTTPServer(('0.0.0.0', 8888), AutoindexHandler)
    print("Serving on http://localhost:8888")
    server.serve_forever()
