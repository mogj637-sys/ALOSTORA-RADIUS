#!/usr/bin/env python3
import json
import sys


def quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    payload = json.load(sys.stdin)
    clients = payload.get("clients", [])
    for index, item in enumerate(clients, start=1):
        address = item["ipaddr"]
        secret = item["secret"]
        shortname = item.get("shortname") or item["nas_identifier"]
        print(f"client alostora_{index} {{")
        print(f"    ipaddr = {address}")
        print(f"    secret = {quoted(secret)}")
        print(f"    shortname = {quoted(shortname)}")
        print("    nastype = mikrotik")
        print("}")


if __name__ == "__main__":
    main()
