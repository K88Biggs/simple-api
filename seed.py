import requests
from datetime import datetime, UTC

API_URL = "http://127.0.0.1:8000/items"
HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": "my-secret-key"
}

products = [
    ("Dell XPS 13 Laptop", "Ultrabook with Intel i7"),
    ("MacBook Pro 14", "Apple M3 Pro performance laptop"),
    ("HP Spectre x360", "Convertible touchscreen laptop"),
    ("Logitech MX Master 3S", "Ergonomic wireless mouse"),
    ("Razer DeathAdder V2", "Gaming mouse with high DPI"),
    ("Keychron K6 Keyboard", "Wireless mechanical keyboard"),
    ("Corsair K95 RGB", "Gaming mechanical keyboard"),
    ("Samsung 4K Monitor", "Ultra HD display"),
    ("LG UltraWide Monitor", "34-inch curved display"),
    ("Sony WH-1000XM5", "Noise cancelling headphones")
]

for i in range(200):
    name, desc = products[i % len(products)]

    payload = {
        "name": f"{name} {i+1}",
        "description": desc,
        "price": round(50 + (i * 3.75), 2),
        "in_stock": i % 3 != 0
    }

    response = requests.post(API_URL, json=payload, headers=HEADERS)
    print(f"Created: {payload['name']} | Status: {response.status_code}")
