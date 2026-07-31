import json
from pathlib import Path

# Replace this with the actual filename you downloaded
JSON_FILE = r"C:\Users\chuas\Desktop\readtap-3693168bccc4.json"

with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

print("[gcp_service_account]")

for key, value in data.items():
    if key == "private_key":
        # Convert \n into real line breaks
        value = value.replace("\\n", "\n")
        print(f'{key} = """{value}"""')
    else:
        print(f'{key} = "{value}"')