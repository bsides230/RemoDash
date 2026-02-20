from http.server import SimpleHTTPRequestHandler, HTTPServer
import json

PORT = 8000
WEB_DIR = "modules/mod_xtts/web"
current_state = "stopped_files_exist"

class MockHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        global current_state
        if self.path == "/" or self.path == "/index.html":
            with open(f"{WEB_DIR}/index.html", 'rb') as f:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f.read())
            return
        if self.path.startswith("/api/modules/mod_xtts/status"):
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            resp = {"loaded": False, "loading": False, "error": None, "dependency_missing": False, "files_exist": False}
            if current_state == "loaded": resp["loaded"] = True; resp["files_exist"] = True
            elif current_state == "stopped_files_exist": resp["files_exist"] = True
            self.wfile.write(json.dumps(resp).encode())
            return
        if self.path.startswith("/control/set_state"):
            current_state = self.path.split("=")[1]
            self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
            return
        self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({}).encode()) # Mock others

httpd = HTTPServer(('localhost', PORT), MockHandler)
httpd.serve_forever()
