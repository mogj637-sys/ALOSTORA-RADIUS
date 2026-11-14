#!/usr/bin/env python3
import ipaddress
import json
import sys


def quoted(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> None:
    payload = json.load(sys.stdin)
    clients = payload.get("clients", [])
    for index, item in enumerate(clients, start=1):
        address = item["ipaddr"]
        address_attribute = "ipaddr" if ipaddress.ip_network(address, strict=False).version == 4 else "ipv6addr"
        secret = item["secret"]
        shortname = item.get("shortname") or item["nas_identifier"]
        print(f"client alostora_{index} {{")
        print(f"    {address_attribute} = {address}")
        print(f"    secret = {quoted(secret)}")
        print(f"    shortname = {quoted(shortname)}")
        print("    nastype = mikrotik")
        print("}")


if __name__ == "__main__":
    main()
