# FlyClaw - Flight Information Aggregation CLI Tool

**FlyClaw** is a lightweight command-line tool that aggregates flight information (dynamics, prices, schedules, etc.) using a multi-source aggregation architecture powered by open-source libraries and free public APIs, with native Chinese/English query support and native OpenClaw skill integration, covering both Chinese domestic and international flights.

Core value: A single data source is unreliable, incomplete, and limited in coverage -- FlyClaw's value lies in **aggregation, deduplication, gap-filling, and presentation**.

**Author**: nuaa02@gmail.com  Xiaohongshu @深度连接
**GitHub**: [https://github.com/AI4MSE/FlyClaw](https://github.com/AI4MSE/FlyClaw)
**License**: [Apache-2.0](LICENSE)

## Features

- **Multi-source aggregation**: Multi-source architecture (FR24, Google Flights, airplaneslive, extensible) powered by open-source libraries and free public APIs for flight dynamics, prices, and real-time positions
- **Advanced search**: Round-trip, multi-passenger (adults/children/infants), cabin class (economy/premium/business/first), sorting, stop control (`--stops 0/1/2/any`), result limits
- **Smart route relay**: Automatically queries Google Flights for prices using routes discovered from FR24/ADS-B, solving the cold-start no-price problem
- **Smart return time**: Returns early when results are available, without waiting for slow sources (`query.return_time` config)
- **Priority-based merging**: Higher-priority source fields take precedence; lower-priority sources fill gaps
- **City-level search**: City name input automatically searches all airports in that city ("Shanghai"→PVG+SHA, "New York"→JFK+EWR+LGA); IATA codes/aliases resolve to a single airport
- **Chinese/English input support**: Accepts Chinese city names ("上海", "浦东"), English names ("Shanghai", "New York"), and IATA codes ("PVG", "JFK") interchangeably
- **7,912 airports cached**: Covers 99% of airports with IATA codes worldwide, including Chinese/English names and alias mappings (100% Chinese translation coverage, AI-verified; corrections welcome)
- **Multi-source fault tolerance**: ADSB.lol transparent backup, user-friendly degradation warnings on source failure
- **Field-complement merging**: Multi-source results for the same flight number are automatically merged — existing fields are not overwritten, missing fields are filled from other sources
- **Concurrent queries**: ThreadPoolExecutor for simultaneous multi-source queries with global timeout; returns partial results on timeout
- **Airport data updates**: Supports scheduled auto-update, manual update, and permanent disable (interface only; auto-update not yet supported, manual update available)
- **Dual output formats**: Table (terminal-friendly) and JSON (programmatic integration)
- **Single config file**: `config.yaml` controls source toggles, timeouts, priorities, and output format
- **Zero API key dependency**: No registration or API key required for all core features

## Quick Start

### Installation (OpenClaw)

Skill files: SKILL.md (Chinese) / SKILL_EN.md (English)
Install from the skill marketplace:

```bash
clawclub install flyclaw
```
Or share this GitHub URL with your OpenClaw assistant to install automatically.

### Installation (Non-OpenClaw)

```bash
# Create conda environment
conda create -n flyclaw python=3.11 -y
conda activate flyclaw

# Install dependencies
pip install -r requirements.txt

# Optional: install fli library for Google Flights data source
pip install flights
```

### Requirements

- Python 3.11+
- conda environment (recommended)

### Configuration

The default `config.yaml` includes recommended values and works out of the box:

```yaml
sources:
  fr24:
    enabled: true
    priority: 1
    timeout: 10
  google_flights:
    enabled: true
    priority: 2
    timeout: 15
    serpapi_key: ""  # Leave empty to skip SerpAPI; fill in key to enable
  airplanes_live:
    enabled: true
    priority: 3
    timeout: 8

cache:
  dir: cache
  airport_update_days: 99999  # Auto-update interval (days); 99999 = off; 0 = disable
  airport_update_url: ""      # Custom update URL; empty = use built-in default

query:
  timeout: 20      # Global query timeout (seconds)
  return_time: 12  # Smart return time (seconds); 0 = disable
  route_relay: true           # Route relay toggle: auto-fetch prices
  relay_timeout_factor: 2     # Timeout multiplier

output:
  format: table  # table / json
  language: both  # cn / en / both
```

### Usage Examples

```bash
# Query by flight number (multi-source concurrent)
conda run -n flyclaw python flyclaw.py query --flight CA981

# Search by route (with prices) — city-level search covers all airports automatically
conda run -n flyclaw python flyclaw.py search --from Shanghai --to "New York" --date 2026-04-01
# Shanghai(PVG+SHA) → New York(JFK+EWR+LGA) all airport combinations

# Round-trip search
conda run -n flyclaw python flyclaw.py search --from PVG --to LAX --date 2026-04-15 --return 2026-04-25

# Business class + 2 adults
conda run -n flyclaw python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --cabin business -a 2

# Nonstop + sort by price + JSON output
conda run -n flyclaw python flyclaw.py search --from PVG --to NRT --date 2026-04-15 --stops 0 --sort cheapest -o json

# Include connecting flights
conda run -n flyclaw python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --stops any

# Disable route relay
conda run -n flyclaw python flyclaw.py query --flight CA981 --no-relay

# Chinese input is also supported
conda run -n flyclaw python flyclaw.py search --from 上海 --to 纽约 --date 2026-04-01

# Verbose mode (show data sources and cabin info)
conda run -n flyclaw python flyclaw.py query --flight CA981 -v

# Custom timeout
conda run -n flyclaw python flyclaw.py query --flight CA981 --timeout 10 --return-time 5

# Update airport data
conda run -n flyclaw python flyclaw.py update-airports --url http://example.com/airports.json
```

### Search Parameters

| Parameter | Short | Default | Description |
|-----------|-------|---------|-------------|
| `--from` | — | (required) | Origin (IATA/Chinese/English) |
| `--to` | — | (required) | Destination |
| `--date` | `-d` | — | Travel date YYYY-MM-DD |
| `--return` | `-r` | — | Return date (enables round-trip) |
| `--adults` | `-a` | 1 | Number of adult passengers |
| `--children` | — | 0 | Number of children |
| `--infants` | — | 0 | Number of infants |
| `--cabin` | `-C` | economy | Cabin: economy/premium/business/first |
| `--limit` | `-l` | Smart | Maximum results (99 nonstop, 20 with-stops, user override) |
| `--sort` | `-s` | — | Sort: cheapest/fastest/departure/arrival |
| `--stops` | — | 0 | Stop control: 0=nonstop/1/2/any |

### Sample Output

```
  CA981  (Air China)
  Beijing(PEK) -> New York(JFK)
  Departure: 2026-04-01 13:00    Arrival: 2026-04-01 14:30
  Price: $856 | Stops: 0 | Duration: 840min
```

Round-trip output:
```
  CA981  (Air China)
  Shanghai(PVG) -> Los Angeles(LAX)
  Departure: 2026-04-15 10:00    Arrival: 2026-04-15 14:00
  Price: $2400 (round-trip) | Stops: 0 | Duration: 840min
  ── Return ──
  CA982  (Air China)
  Departure: 2026-04-25 18:00    Arrival: 2026-04-26 22:00
  Stops: 0 | Duration: 900min
```

## Data Sources

FlyClaw uses a multi-source aggregation architecture powered by open-source libraries and free public APIs. No API key required. Please comply with local laws when using the data.

## Dependencies and Licenses

| Dependency | Version | License | Purpose |
|-----------|---------|---------|---------|
| requests | >=2.28.0 | Apache-2.0 | HTTP requests |
| pyyaml | >=6.0 | MIT | YAML config parsing |
| flights (fli) | latest | MIT | Google Flights queries (optional) |

Python: 3.11+

## Disclaimer

- Multi-source aggregation powered by open-source libraries and free public APIs
- **No API key required** for all core features
- For study and research purposes only. Please comply with local laws
- Google Flights may not be available in some regions (e.g. mainland China)
- Chinese domestic flight coverage may be incomplete due to free public data source limitations
- No personal data is collected, stored, or transmitted

## License

[Apache-2.0](LICENSE) | nuaa02@gmail.com
