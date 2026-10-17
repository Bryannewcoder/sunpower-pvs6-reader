#!/usr/bin/env python3
"""Read live solar data from a SunPower PVS6 gateway over the local network.

No SunPower cloud, no app, no account needed -- this talks directly to
the gateway on your LAN, the same way the gateway's own web UI does.

Usage:
    PVS6_HOST=192.168.1.50 PVS6_PASS='your-gateway-password' python3 pvs6_read.py

    python3 pvs6_read.py --host 192.168.1.50
    (with PVS6_PASS set in the environment)

Output is a single JSON object:
    {
      "production_kw": 2.01,
      "consumption_kw": 0.89,
      "lifetime_kwh": 38712.4,
      "grid_kw": -1.12,
      "panels": [{"kw": 0.25, "sn": "SN-..."}, ...]
    }

grid_kw is consumption minus production: negative means you are exporting
to the grid, positive means you are importing.

Requirements: Python 3, standard library only. No third-party packages.

Security notes:
  - The password is read ONLY from the PVS6_PASS environment variable, never
    from a command-line argument (arguments show up in shell history and
    process listings). Do not put the password in a file that gets committed.
  - The gateway uses a self-signed certificate, so this script does not verify
    TLS. That is acceptable on your own LAN; do not expose the gateway (or
    this script's output) to the internet.
  - Keep this on your home network. The gateway has no per-user access control
    beyond its password.
"""

import argparse
import base64
import json
import os
import ssl
import sys
import urllib.request


def https_get(base, path, headers, ctx):
    req = urllib.request.Request(base + path, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        return json.loads(resp.read().decode())


def read_gateway(host, password):
    # The gateway serves HTTPS with a self-signed cert; verification is
    # disabled because this runs on the local network only.
    ctx = ssl._create_unverified_context()
    base = "https://" + host

    auth = base64.b64encode(("ssm_owner:" + password).encode()).decode()
    login = https_get(base, "/auth?login", {"Authorization": "basic " + auth}, ctx)
    session = login.get("session")
    if not session:
        raise RuntimeError("login failed: gateway did not return a session")

    headers = {"Cookie": "session=" + session}
    inv_data = https_get(base, "/vars?match=inverter", headers, ctx)
    meter_data = https_get(base, "/vars?match=meter", headers, ctx)

    panels = {}
    for value in inv_data.get("values") or []:
        parts = value.get("name", "").split("/")
        if "inverter" not in parts:
            continue
        panel_id = parts[parts.index("inverter") + 1]
        panels.setdefault(panel_id, {})[parts[-1]] = value.get("value")
    panel_list = [
        {
            "kw": float(p.get("p3phsumKw") or 0),
            "sn": p.get("sn") or "",
        }
        for p in panels.values()
    ]
    production_kw = sum(p["kw"] for p in panel_list)

    meters = {}
    for value in meter_data.get("values") or []:
        parts = value.get("name", "").split("/")
        if "meter" not in parts:
            continue
        meter_id = parts[parts.index("meter") + 1]
        try:
            meters.setdefault(meter_id, {})[parts[-1]] = float(value.get("value"))
        except (TypeError, ValueError):
            meters.setdefault(meter_id, {})[parts[-1]] = value.get("value")

    # Identify meters by model suffix, not by position: the order the
    # gateway reports them can flip after a reboot.
    prod_meter = cons_meter = None
    for meter in meters.values():
        model = str(meter.get("prodMdlNm") or "")
        if model.endswith("p"):
            prod_meter = meter
        elif model.endswith("c"):
            cons_meter = meter

    consumption_kw = float((cons_meter or {}).get("p3phsumKw") or 0)
    lifetime_kwh = float((prod_meter or {}).get("netLtea3phsumKwh") or 0)
    grid_kw = consumption_kw - production_kw

    return {
        "production_kw": production_kw,
        "consumption_kw": consumption_kw,
        "lifetime_kwh": lifetime_kwh,
        "grid_kw": grid_kw,
        "panels": panel_list,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Read live data from a SunPower PVS6 gateway on your LAN."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("PVS6_HOST", ""),
        help="Gateway IP or hostname (or set PVS6_HOST)",
    )
    args = parser.parse_args()

    password = os.environ.get("PVS6_PASS", "")
    if not args.host:
        print("error: no gateway host -- pass --host or set PVS6_HOST", file=sys.stderr)
        return 2
    if not password:
        print("error: no gateway password -- set PVS6_PASS", file=sys.stderr)
        return 2

    try:
        print(json.dumps(read_gateway(args.host, password), indent=2))
    except Exception as exc:  # noqa: BLE001 -- report any gateway/parse failure plainly
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
