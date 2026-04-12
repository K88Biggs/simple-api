import json
import os
import logging
from datetime import datetime, UTC
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

HOST = "127.0.0.1"
PORT = 8000
DATA_FILE = "items.json"
API_KEY = "my-secret-key"

items = {}
next_id = 1

# ------------------ LOGGING ------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ------------------ HELPERS ------------------
def now_iso():
    return datetime.now(UTC).isoformat()

def send_json(handler, status_code, data):
    response = json.dumps(data).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(response)))
    handler.end_headers()
    handler.wfile.write(response)

def parse_json_body(handler):
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        return None
    raw_body = handler.rfile.read(content_length)
    try:
        return json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        return "INVALID_JSON"

def validate_item(body):
    errors = []

    if "name" not in body or not str(body["name"]).strip():
        errors.append("Name is required")

    if "price" not in body:
        errors.append("Price is required")
    else:
        try:
            price = float(body["price"])
            if price <= 0:
                errors.append("Price must be greater than 0")
        except (ValueError, TypeError):
            errors.append("Price must be a number")

    return errors

def is_item_detail_route(path_parts):
    return len(path_parts) == 2 and path_parts[0] == "items"

def is_authorized(handler):
    return handler.headers.get("x-api-key") == API_KEY

# ------------------ STORAGE ------------------
def save_items():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": items, "next_id": next_id}, f)

def load_items():
    global items, next_id
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            items = {int(k): v for k, v in data.get("items", {}).items()}
            next_id = data.get("next_id", 1)

# ------------------ HANDLER ------------------
class SimpleAPIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        path_parts = parsed.path.strip("/").split("/")

        if parsed.path == "/":
            send_json(self, 200, {"status": "ok"})
            return

        if parsed.path.startswith("/items"):

            # GET ALL ITEMS (with filtering)
            if parsed.path == "/items":
                results = list(items.values())

                if "name" in query_params:
                    name_filter = query_params["name"][0].lower()
                    results = [i for i in results if name_filter in i["name"].lower()]

                if "in_stock" in query_params:
                    val = query_params["in_stock"][0].lower() == "true"
                    results = [i for i in results if i["in_stock"] == val]

                send_json(self, 200, results)
                return

            # GET ONE ITEM
            if len(path_parts) == 2:
                try:
                    item_id = int(path_parts[1])
                except ValueError:
                    send_json(self, 400, {"error": "Invalid ID"})
                    return

                item = items.get(item_id)
                if not item:
                    send_json(self, 404, {"error": "Item not found"})
                    return

                send_json(self, 200, item)
                return

        send_json(self, 404, {"error": "Route not found"})

    def do_POST(self):
        global next_id

        if self.path != "/items":
            send_json(self, 404, {"error": "Route not found"})
            return

        if not is_authorized(self):
            send_json(self, 401, {"error": "Unauthorized"})
            return

        body = parse_json_body(self)

        if body == "INVALID_JSON":
            send_json(self, 400, {"error": "Invalid JSON"})
            return

        if body is None:
            body = {}

        errors = validate_item(body)
        if errors:
            send_json(self, 400, {"errors": errors})
            return

        item = {
            "id": next_id,
            "name": body["name"],
            "description": body.get("description"),
            "price": float(body["price"]),
            "in_stock": body.get("in_stock", True),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        items[next_id] = item
        next_id += 1
        save_items()

        logging.info(f"Created item {item['id']}")
        send_json(self, 201, item)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip("/").split("/")

        if not is_item_detail_route(path_parts):
            send_json(self, 404, {"error": "Route not found"})
            return

        if not is_authorized(self):
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            item_id = int(path_parts[1])
        except ValueError:
            send_json(self, 400, {"error": "Invalid ID"})
            return

        if item_id not in items:
            send_json(self, 404, {"error": "Item not found"})
            return

        body = parse_json_body(self)

        if body == "INVALID_JSON":
            send_json(self, 400, {"error": "Invalid JSON"})
            return

        if body is None:
            body = {}

        errors = validate_item(body)
        if errors:
            send_json(self, 400, {"errors": errors})
            return

        updated = {
            "id": item_id,
            "name": body["name"],
            "description": body.get("description"),
            "price": float(body["price"]),
            "in_stock": body.get("in_stock", True),
            "created_at": items[item_id]["created_at"],
            "updated_at": now_iso(),
        }

        items[item_id] = updated
        save_items()

        logging.info(f"Updated item {item_id}")
        send_json(self, 200, updated)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path_parts = parsed.path.strip("/").split("/")

        if not is_item_detail_route(path_parts):
            send_json(self, 404, {"error": "Route not found"})
            return

        if not is_authorized(self):
            send_json(self, 401, {"error": "Unauthorized"})
            return

        try:
            item_id = int(path_parts[1])
        except ValueError:
            send_json(self, 400, {"error": "Invalid ID"})
            return

        if item_id not in items:
            send_json(self, 404, {"error": "Item not found"})
            return

        del items[item_id]
        save_items()

        logging.info(f"Deleted item {item_id}")
        send_json(self, 200, {"message": "Deleted successfully"})

    def log_message(self, format, *args):
        return

# ------------------ RUN ------------------
def run():
    load_items()
    server = HTTPServer((HOST, PORT), SimpleAPIHandler)
    print(f"Server running at http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()

