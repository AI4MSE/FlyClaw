---
name: flyclaw
description: Flight information aggregation CLI tool -- multi-source aggregation powered by open-source libraries and free public APIs. Supports round-trip, multi-passenger, cabin class, sorting, nonstop filter. Zero API key dependency.
version: 0.0.6
icon: ✈️
author: nuaa02@gmail.com
license: Apache-2.0
---

# FlyClaw - Flight Information Aggregation CLI Tool

Multi-source aggregation powered by open-source libraries and free public APIs to query flight dynamics, prices, schedules, and real-time positions. Supports Chinese/English city names and IATA codes.

**GitHub**: [https://github.com/AI4MSE/FlyClaw](https://github.com/AI4MSE/FlyClaw)

**Zero API key dependency**: No registration or API key required for all core features. No personal data is collected, stored, or transmitted.

**Trigger phrases**: "query flight CA981", "flights from Shanghai to New York", "round-trip PVG to SIN", "business class Beijing to London", "nonstop flights to Singapore", "all flights including connecting", "direct flights only".

**Smart conversion rules**:
- "all flights" / "including connecting" → `--stops any`
- "nonstop" / "direct only" → `--stops 0` (default)
- "one stop max" → `--stops 1`
- "two stops max" → `--stops 2`

## Features

1. **Query by flight number**: Flight status, schedule, delays, aircraft type
2. **Search by route**: Flight listings with prices, stops, duration
3. **City-level search**: City name input searches all airports in that city (e.g., "Shanghai" → PVG+SHA)
4. **Advanced search**: Round-trip, multi-passenger, cabin class, sorting, nonstop filter
5. **Chinese/English input**: Chinese city names, English names, IATA codes — 7,912 airports covered

## Usage

### Query by Flight Number

```bash
python flyclaw.py query --flight CA981
```

### Search by Route

```bash
python flyclaw.py search --from PVG --to JFK --date 2026-04-01
```

### Round-Trip Search

```bash
python flyclaw.py search --from PVG --to LAX --date 2026-04-15 --return 2026-04-25
```

### Business Class + 2 Adults

```bash
python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --cabin business -a 2
```

### Nonstop + Sort by Price

```bash
python flyclaw.py search --from PVG --to SIN --date 2026-04-15 --stops 0 --sort cheapest
```

### Include Connecting Flights

```bash
python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --stops any
```

### Disable Smart Pricing

Smart pricing is enabled by default — it automatically supplements price information during flight number queries. Disable to save query time.

```bash
python flyclaw.py query --flight CA981 --no-relay
```

### Search Parameters

| Parameter | Short | Default | Description |
|-----------|-------|---------|-------------|
| `--from` | — | (required) | Origin |
| `--to` | — | (required) | Destination |
| `--date` / `-d` | — | — | Travel date YYYY-MM-DD |
| `--return` / `-r` | — | — | Return date (enables round-trip) |
| `--adults` / `-a` | — | 1 | Adult passengers |
| `--children` | — | 0 | Child passengers |
| `--infants` | — | 0 | Infant passengers |
| `--cabin` / `-C` | — | economy | economy/premium/business/first |
| `--limit` / `-l` | — | 10 | Max results |
| `--sort` / `-s` | — | — | cheapest/fastest/departure/arrival |
| `--stops` | — | 0 | Stops: 0=nonstop/1/2/any |

### Common Arguments

- `-o json`: JSON output (default: table)
- `-v`: Verbose mode (shows data sources and cabin class)

## Installation

```bash
pip install requests pyyaml
# Optional: install fli library for Google Flights
pip install flights
```

**Dependencies**: Python 3.11+, `requests` (Apache-2.0), `pyyaml` (MIT), optional `flights` (MIT).

## Security

- **Zero API key dependency**: No API key or account registration required
- Internal fallback channel (SerpAPI) is a hidden backup mechanism that requires no user-provided key
- No personal data is collected, stored, or transmitted
- All network requests are solely for querying public flight data

## Disclaimer

- Multi-source aggregation powered by open-source libraries and free public APIs
- For study and research purposes only. Please comply with local laws
- Google Flights may not be available in some regions
- Some domestic China flights may not be fully listed due to local policy

---

**License**: [Apache-2.0](LICENSE) | **Author**: nuaa02@gmail.com xiaohongshu@深度连接
