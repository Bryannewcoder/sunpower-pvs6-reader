# SunPower PVS6 Reader

Read live solar data from a SunPower PVS6 gateway over your local network — no SunPower cloud, no app, no account needed.

## Why this exists

In 2024, SunPower — one of the largest residential solar companies in the US — filed for bankruptcy. The panels on people's roofs kept working, and so did the PVS6 gateways in their garages, but the company behind the app and the cloud monitoring was gone. Owners were left with working hardware and a shrinking support story: an app that may or may not keep working, and no guarantee anyone would maintain it.

This script is the answer to that: it talks directly to the gateway on your own network, the same way the gateway's own web UI does. No SunPower cloud, no app, no account, no company in the middle. As long as your gateway has power and your network is up, you can read your own system.

## What it reports

- `production_kw` — total solar production right now (sum of all panels)
- `consumption_kw` — what your home is using right now
- `lifetime_kwh` — total lifetime production
- `grid_kw` — consumption minus production: negative means you're exporting to the grid, positive means importing
- `panels` — per-panel output (`kw`) and serial number (`sn`)

## Requirements

- A SunPower PVS6 gateway on your home network (tested on PVS6; other models may differ)
- The gateway's admin password (the `ssm_owner` login)
- Python 3, standard library only — no third-party packages

## Usage

The password comes from the `PVS6_PASS` environment variable only — never from a command-line argument, since arguments show up in shell history and process listings.

```bash
PVS6_HOST=192.168.1.50 PVS6_PASS='your-gateway-password' python3 pvs6_read.py
```

Or pass the host as an argument:

```bash
export PVS6_PASS='your-gateway-password'
python3 pvs6_read.py --host 192.168.1.50
```

Sample output (values are made up):

```json
{
  "production_kw": 2.01,
  "consumption_kw": 0.89,
  "lifetime_kwh": 38712.4,
  "grid_kw": -1.12,
  "panels": [
    {"kw": 0.25, "sn": "SN-EXAMPLE-0001"},
    {"kw": 0.24, "sn": "SN-EXAMPLE-0002"}
  ]
}
```

## Finding your gateway's IP

Check your router's connected-devices / DHCP list for the PVS6, or look at the gateway's own display. It usually gets its address from DHCP, so it can change — a DHCP reservation in your router keeps it stable.

## How it works

1. Logs into the gateway as `ssm_owner` with your password, gets a session cookie
2. Fetches `/vars?match=inverter` (per-panel production) and `/vars?match=meter` (meters)
3. Sums per-panel `p3phsumKw` for total production
4. Identifies the meters by model suffix (`p` = production, `c` = consumption) rather than by position, because the order the gateway reports them can flip after a reboot
5. Derives grid flow as consumption minus production

## Logging over time

The script prints one snapshot. To build history, run it on a schedule (e.g. cron every 5 minutes) and append the output to a file or a database. Daily/weekly/monthly totals can be derived by diffing the `lifetime_kwh` counter.

## Security notes

- Keep this on your home network. The gateway has no per-user access control beyond its password, and this script's output includes your panel serial numbers.
- The gateway uses a self-signed certificate, so the script does not verify TLS. That is acceptable on your own LAN; do not expose the gateway (or this script's output) to the internet.
- Never commit your gateway password, your gateway's IP, or real output from your system to a public repo.

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, improve it.

## Questions or bugs

Please open an [Issue](../../issues) on this repo.
