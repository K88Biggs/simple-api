import json
import threading
import time
from pathlib import Path
from urllib import error, request

import pytest

import app
from http.server import HTTPServer


def make_request(method, url, data=None, headers=None):
    headers = headers or {}
    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = request.Request(url=url, data=body, headers=headers, method=method)

    try:
        with request.urlopen(req) as response:
            response_body = response.read().decode("utf-8")
            return response.status, json.loads(response_body)
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8")
        return exc.code, json.loads(response_body)


@pytest.fixture
def api_server(tmp_path):
    data_file = tmp_path / "items.json"

    # Reset app state for each test
    app.items = {}
    app.next_id = 1
    app.DATA_FILE = str(data_file)

    server = HTTPServer(("127.0.0.1", 0), app.SimpleAPIHandler)
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    time.sleep(0.1)

    yield {
        "base_url": base_url,
        "data_file": data_file,
        "headers": {
            "Content-Type": "application/json",
            "x-api-key": app.API_KEY,
        },
    }

    server.shutdown()
    server.server_close()
    thread.join(timeout=1)


def test_health_check(api_server):
    status, body = make_request("GET", f"{api_server['base_url']}/")
    assert status == 200
    assert body["status"] == "ok"


def test_create_item_success(api_server):
    payload = {
        "name": "Dell XPS 13 Laptop",
        "description": "13-inch ultrabook",
        "price": 1299.99,
        "in_stock": True,
    }

    status, body = make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=payload,
        headers=api_server["headers"],
    )

    assert status == 201
    assert body["id"] == 1
    assert body["name"] == payload["name"]
    assert body["price"] == payload["price"]
    assert body["in_stock"] is True
    assert "created_at" in body
    assert "updated_at" in body


def test_create_item_unauthorized(api_server):
    payload = {
        "name": "Monitor",
        "price": 199.99,
    }

    status, body = make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    assert status == 401
    assert body["error"] == "Unauthorized"


def test_create_item_validation_error(api_server):
    payload = {
        "name": "",
        "price": -10,
    }

    status, body = make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=payload,
        headers=api_server["headers"],
    )

    assert status == 400
    assert "errors" in body
    assert "Name is required" in body["errors"]
    assert "Price must be greater than 0" in body["errors"]


def test_get_all_items(api_server):
    payload = {
        "name": "Mouse",
        "description": "Wireless mouse",
        "price": 49.99,
        "in_stock": False,
    }

    make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=payload,
        headers=api_server["headers"],
    )

    status, body = make_request("GET", f"{api_server['base_url']}/items")

    assert status == 200
    assert len(body) == 1
    assert body[0]["name"] == "Mouse"


def test_get_single_item(api_server):
    payload = {
        "name": "Keyboard",
        "description": "Mechanical keyboard",
        "price": 89.99,
        "in_stock": True,
    }

    make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=payload,
        headers=api_server["headers"],
    )

    status, body = make_request("GET", f"{api_server['base_url']}/items/1")

    assert status == 200
    assert body["id"] == 1
    assert body["name"] == "Keyboard"


def test_get_missing_item(api_server):
    status, body = make_request("GET", f"{api_server['base_url']}/items/999")

    assert status == 404
    assert body["error"] == "Item not found"


def test_filter_items_by_name(api_server):
    items = [
        {"name": "Mouse", "description": "Wireless mouse", "price": 49.99, "in_stock": True},
        {"name": "Laptop", "description": "Work laptop", "price": 999.99, "in_stock": True},
        {"name": "Gaming Mouse", "description": "High DPI mouse", "price": 79.99, "in_stock": False},
    ]

    for item in items:
        make_request(
            "POST",
            f"{api_server['base_url']}/items",
            data=item,
            headers=api_server["headers"],
        )

    status, body = make_request("GET", f"{api_server['base_url']}/items?name=mouse")

    assert status == 200
    assert len(body) == 2
    assert all("mouse" in item["name"].lower() for item in body)


def test_filter_items_by_stock(api_server):
    items = [
        {"name": "Monitor", "description": "4K monitor", "price": 349.99, "in_stock": True},
        {"name": "Dock", "description": "USB-C dock", "price": 129.99, "in_stock": False},
    ]

    for item in items:
        make_request(
            "POST",
            f"{api_server['base_url']}/items",
            data=item,
            headers=api_server["headers"],
        )

    status, body = make_request("GET", f"{api_server['base_url']}/items?in_stock=true")

    assert status == 200
    assert len(body) == 1
    assert body[0]["name"] == "Monitor"


def test_update_item(api_server):
    create_payload = {
        "name": "Headset",
        "description": "Noise cancelling headset",
        "price": 149.99,
        "in_stock": True,
    }

    make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=create_payload,
        headers=api_server["headers"],
    )

    update_payload = {
        "name": "Updated Headset",
        "description": "Updated description",
        "price": 159.99,
        "in_stock": False,
    }

    status, body = make_request(
        "PUT",
        f"{api_server['base_url']}/items/1",
        data=update_payload,
        headers=api_server["headers"],
    )

    assert status == 200
    assert body["name"] == "Updated Headset"
    assert body["price"] == 159.99
    assert body["in_stock"] is False


def test_delete_item(api_server):
    payload = {
        "name": "Printer",
        "description": "Office printer",
        "price": 249.99,
        "in_stock": True,
    }

    make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=payload,
        headers=api_server["headers"],
    )

    status, body = make_request(
        "DELETE",
        f"{api_server['base_url']}/items/1",
        headers={"x-api-key": app.API_KEY},
    )

    assert status == 200
    assert body["message"] == "Deleted successfully"

    status, body = make_request("GET", f"{api_server['base_url']}/items/1")
    assert status == 404
    assert body["error"] == "Item not found"


def test_data_persists_to_json_file(api_server):
    payload = {
        "name": "Webcam",
        "description": "HD webcam",
        "price": 69.99,
        "in_stock": True,
    }

    make_request(
        "POST",
        f"{api_server['base_url']}/items",
        data=payload,
        headers=api_server["headers"],
    )

    assert Path(api_server["data_file"]).exists()

    saved_data = json.loads(Path(api_server["data_file"]).read_text(encoding="utf-8"))
    assert "items" in saved_data
    assert "1" in saved_data["items"]
    assert saved_data["items"]["1"]["name"] == "Webcam"
