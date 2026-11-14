#!/usr/bin/env python3
import json
import sys


def quote(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\r", "").replace("\n", "")
    return f'"{escaped}"'


def main() -> None:
    with open(sys.argv[1], "r", encoding="utf-8") as source:
        payload = json.load(source)

    clients = payload.get("clients", [])
    if not clients:
        print("# No active RADIUS clients are configured yet.")
        return

    for index, client in enumerate(clients, start=1):
        address = str(client["ipaddr"]).strip()
        secret = str(client["secret"])
        shortname = str(client.get("shortname") or f"router-{index}")
        print(f"client alostora_router_{index} {{")
        print(f"    ipaddr = {address}")
        print(f"    secret = {quote(secret)}")
        print(f"    shortname = {quote(shortname)}")
        print("}")


if __name__ == "__main__":
    main()
