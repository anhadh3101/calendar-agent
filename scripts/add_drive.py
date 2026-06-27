import os
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

API_KEY = os.getenv("XPANDER_API_KEY")
AGENT_ID = os.getenv("XPANDER_AGENT_ID")

if not API_KEY or not AGENT_ID:
    missing = [
        name
        for name, value in (
            ("XPANDER_API_KEY", API_KEY),
            ("XPANDER_AGENT_ID", AGENT_ID),
        )
        if not value
    ]
    raise KeyError(f"Missing required environment variables: {', '.join(missing)}")

# ==========================
# Configuration
# ==========================
CONNECTOR_NAME = "Google Drive"
SEARCH_QUERY = "drive"

BASE_URL = "https://api.xpander.ai/v1"

HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

# ==========================
# Step 1: Find the connector
# ==========================
print(f"Searching for {CONNECTOR_NAME} connector...")

url = f"{BASE_URL}/tools?page=1&per_page=20&type=connector&query={SEARCH_QUERY}"

response = requests.get(url, headers=HEADERS)
response.raise_for_status()

data = response.json()

connector = None

for item in data.get("items", []):
    if item["name"] == CONNECTOR_NAME:
        connector = item
        break

if connector is None:
    raise Exception(f"Connector '{CONNECTOR_NAME}' not found.")

connector_id = connector["id"]

connections = connector.get("connections", [])
if not connections:
    raise Exception(f"No connections found for '{CONNECTOR_NAME}'.")

connection_id = connections[0]["id"]

print(f"Connector ID : {connector_id}")
print(f"Connection ID: {connection_id}")

# ==========================
# Step 2: Get all operations
# ==========================
print("\nFetching operations...")

url = f"{BASE_URL}/tools/connectors/{connector_id}/operations?connection_id={connection_id}"

response = requests.get(url, headers=HEADERS)
response.raise_for_status()

operations = response.json()

operation_ids = [op["id"] for op in operations]

if not operation_ids:
    raise Exception("No operations found.")

print(f"Found {len(operation_ids)} operations.")

# Uncomment if you want to see them
# for op in operations:
#     print(op["pretty_name"], "->", op["id"])

# ==========================
# Step 3: Attach all tools
# ==========================
print("\nAttaching tools to agent...")

url = f"{BASE_URL}/agents/{AGENT_ID}/tools?deploy=true"

payload = {
    "connection_id": connection_id,
    "operation_ids": operation_ids,
    "type": "action"
}

response = requests.post(
    url,
    json=payload,
    headers=HEADERS
)
response.raise_for_status()

attached_tools = response.json()

print("\n===================================")
print(f"Successfully attached {len(attached_tools)} tools!")
print("===================================\n")

for tool in attached_tools:
    print(f"✓ {tool['operation_name']} ({tool['operation_id']})")