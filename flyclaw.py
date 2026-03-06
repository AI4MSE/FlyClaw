"""FlyClaw - Flight information aggregation CLI tool.

Usage:
    flyclaw query --flight CA981
    flyclaw search --from PVG --to JFK --date 2026-04-01
"""

import argparse
import json
import logging
import sys
import time as _time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

from __init__ import __version__
import config as cfg
from airport_manager import airport_manager
from route_cache import route_cache
from sources.fr24 import FR24Source
from sources.google_flights import GoogleFlightsSource
from sources.airplaneslive import AirplanesLiveSource

__version__ = __version__

logger = logging.getLogger("flyclaw")


# ---------------------------------------------------------------------------
# Field merge logic
# ---------------------------------------------------------------------------

def _get_source_priority(record: dict) -> int:
    """Return the configured priority for a record's source.

    Lower number = higher priority.  Unknown sources get 999.
    """
    source = record.get("source", "")
    conf = cfg.get_config()
    sources_cfg = conf.get("sources", {})
    for name, scfg in sources_cfg.items():
        if name == source:
            return scfg.get("priority", 999)
    return 999


def _merge_records(records: list[dict]) -> list[dict]:
    """Merge records from different sources for the same flight.

    Strategy: sort by source priority (high-priority first), then group
    by flight_number and fill missing fields from lower-priority sources.
    Records without flight_number are kept as-is.
    """
    sorted_records = sorted(records, key=_get_source_priority)

    grouped: dict[str, dict] = {}
    ungrouped: list[dict] = []

    for rec in sorted_records:
        fn = rec.get("flight_number", "")
        if not fn:
            ungrouped.append(rec)
            continue
        if fn not in grouped:
            grouped[fn] = rec.copy()
        else:
            # Fill-in: existing non-empty values take priority
            existing = grouped[fn]
            for key, val in rec.items():
                if key == "source":
                    # Combine unique sources
                    sources = set(existing.get("source", "").split(","))
                    sources.add(val)
                    sources.discard("")
                    existing["source"] = ",".join(sorted(sources))
                elif not existing.get(key) and val:
                    existing[key] = val

    return list(grouped.values()) + ungrouped


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _format_table(records: list[dict], verbose: bool = False) -> str:
    """Format records as a human-readable table."""
    if not records:
        return "No flights found."

    lines = []
    sep = "-" * 90

    for i, rec in enumerate(records):
        if i > 0:
            lines.append(sep)

        fn = rec.get("flight_number", "N/A")
        airline = rec.get("airline", "") or ""
        status = rec.get("status", "") or ""
        origin = rec.get("origin_city", rec.get("origin_iata", ""))
        dest = rec.get("destination_city", rec.get("destination_iata", ""))
        dep = _format_time(rec.get("scheduled_departure"))
        arr = _format_time(rec.get("scheduled_arrival"))
        aircraft = rec.get("aircraft_type", "") or ""
        price = rec.get("price")
        delay = rec.get("delay_minutes")
        source = rec.get("source", "")
        stops = rec.get("stops")

        header = f"  {fn}"
        if airline:
            header += f"  ({airline})"
        if status:
            header += f"  [{status}]"
        lines.append(header)

        lines.append(f"  {origin} → {dest}")
        lines.append(f"  Departure: {dep}    Arrival: {arr}")

        extras = []
        if aircraft:
            extras.append(f"Aircraft: {aircraft}")
        trip_type = rec.get("trip_type", "")
        price_label = "(round-trip)" if trip_type == "round_trip" else ""
        if price is not None:
            extras.append(f"Price: ${price} {price_label}".strip())
        if stops is not None:
            extras.append(f"Stops: {stops}")
        duration = rec.get("duration_minutes")
        if duration is not None:
            extras.append(f"Duration: {duration}min")
        if delay is not None:
            extras.append(f"Delay: {delay}min")
        altitude = rec.get("altitude_ft")
        speed = rec.get("ground_speed_kts")
        if altitude is not None:
            extras.append(f"Alt: {altitude}ft")
        if speed is not None:
            extras.append(f"Speed: {speed}kts")
        if extras:
            lines.append(f"  {' | '.join(extras)}")

        # Round-trip return flight block
        if trip_type == "round_trip":
            ret_fn = rec.get("return_flight_number", "")
            ret_airline = rec.get("return_airline", "")
            ret_dep = _format_time(rec.get("return_departure"))
            ret_arr = _format_time(rec.get("return_arrival"))
            ret_stops = rec.get("return_stops")
            ret_dur = rec.get("return_duration_minutes")

            lines.append("  ── Return ──")
            ret_header = f"  {ret_fn}" if ret_fn else "  N/A"
            if ret_airline:
                ret_header += f"  ({ret_airline})"
            lines.append(ret_header)
            lines.append(f"  Departure: {ret_dep}    Arrival: {ret_arr}")
            ret_extras = []
            if ret_stops is not None:
                ret_extras.append(f"Stops: {ret_stops}")
            if ret_dur is not None:
                ret_extras.append(f"Duration: {ret_dur}min")
            if ret_extras:
                lines.append(f"  {' | '.join(ret_extras)}")

        if verbose:
            cabin_class = rec.get("cabin_class", "")
            if cabin_class:
                lines.append(f"  Cabin: {cabin_class}")
            lines.append(f"  Source: {source}")

    return "\n".join(lines)


def _format_time(iso_str: str | None) -> str:
    """Format ISO timestamp to readable form."""
    if not iso_str:
        return "--"
    # Show date + time portion
    return iso_str.replace("T", " ")[:19]


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_update_airports(args):
    """Handle 'update-airports' subcommand: manually update airport data."""
    conf = cfg.get_config()
    cache_cfg = conf["cache"]

    # URL priority: CLI --url > config.yaml > AIRPORT_UPDATE_URL constant
    url = getattr(args, "url", None) or cache_cfg.get("airport_update_url", "") or cfg.AIRPORT_UPDATE_URL
    if not url:
        print("Error: no update URL provided. Use --url or set airport_update_url in config.yaml",
              file=sys.stderr)
        sys.exit(1)

    print(f"Updating airport data from: {url}")
    ok = airport_manager.update_from_url(url)
    if ok:
        print("Airport data updated successfully.")
    else:
        print("Airport data update failed. See log for details.", file=sys.stderr)
        sys.exit(1)


def _auto_update_airports():
    """Check and auto-update airport data at startup (silent on failure)."""
    try:
        conf = cfg.get_config()
        cache_cfg = conf["cache"]
        update_days = cache_cfg.get("airport_update_days", 30)
        url = cache_cfg.get("airport_update_url", "") or cfg.AIRPORT_UPDATE_URL

        if not url or update_days <= 0:
            return

        if airport_manager.check_staleness(update_days):
            logger.info("Airport data is stale, auto-updating...")
            airport_manager.update_from_url(url)
    except Exception as e:
        logger.debug("Auto-update check skipped: %s", e)


# ---------------------------------------------------------------------------
# Concurrent query infrastructure
# ---------------------------------------------------------------------------

def _query_fr24_flight(flight_number: str, timeout: int) -> list[dict]:
    """Wrapper: query FR24 by flight number."""
    src = FR24Source(timeout=timeout)
    return src.query_by_flight(flight_number)


def _query_fr24_route(origin: str, dest: str, date: str | None, timeout: int) -> list[dict]:
    """Wrapper: query FR24 by route."""
    src = FR24Source(timeout=timeout)
    return src.query_by_route(origin, dest, date)


def _query_gf_route(
    origin: str | list[str], dest: str | list[str], date: str,
    timeout: int, serpapi_key: str,
    *, return_date: str | None = None, adults: int = 1,
    children: int = 0, infants: int = 0,
    cabin: str = "economy", stops: int | str = 0,
    sort: str | None = None, limit: int = 10,
) -> list[dict]:
    """Wrapper: query Google Flights by route.

    origin/dest can be str or list[str] for multi-airport city searches.
    """
    src = GoogleFlightsSource(timeout=timeout, serpapi_key=serpapi_key)
    return src.query_by_route(
        origin, dest, date,
        return_date=return_date, adults=adults, children=children,
        infants=infants, cabin=cabin, stops=stops,
        sort=sort, limit=limit,
    )


def _query_gf_flight(flight_number: str, timeout: int, serpapi_key: str) -> list[dict]:
    """Wrapper: query Google Flights by flight number (via route cache)."""
    src = GoogleFlightsSource(timeout=timeout, serpapi_key=serpapi_key)
    return src.query_by_flight(flight_number)


def _query_al_flight(flight_number: str, timeout: int) -> list[dict]:
    """Wrapper: query Airplanes.live by flight number."""
    src = AirplanesLiveSource(timeout=timeout)
    return src.query_by_flight(flight_number)


def _execute_concurrent_queries(
    tasks: list[tuple],
    global_timeout: int,
    return_time: int | None = None,
) -> list[dict]:
    """Execute query tasks concurrently and collect results.

    Args:
        tasks: list of (name, callable, args_tuple) triples
        global_timeout: max seconds to wait for all tasks
        return_time: if set, return early once this many seconds have
            elapsed AND at least one result is available.  ``None`` or
            0 disables smart-return (wait for all / global timeout).

    Returns:
        Combined list of result dicts from all successful tasks.
        Partial results returned if global timeout or return_time expires.
    """
    if not tasks:
        return []

    results = []
    start = _time.monotonic()
    executor = ThreadPoolExecutor(max_workers=len(tasks))

    future_to_name = {}
    for name, fn, args in tasks:
        future = executor.submit(fn, *args)
        future_to_name[future] = name

    pending = set(future_to_name.keys())
    early_exit = False
    while pending:
        elapsed = _time.monotonic() - start
        remaining = global_timeout - elapsed
        if remaining <= 0:
            logger.warning(
                "Global timeout (%ds) reached, returning partial results",
                global_timeout,
            )
            early_exit = True
            break

        # If smart return is enabled and we already have results,
        # use a short wait so we can exit at the return_time boundary.
        wait_timeout = remaining
        if return_time and results:
            time_to_return = max(0, return_time - elapsed)
            wait_timeout = min(remaining, time_to_return) if time_to_return > 0 else 0

        if wait_timeout <= 0 and return_time and results:
            logger.info(
                "Smart return at %.1fs with %d results (%d sources pending)",
                elapsed, len(results), len(pending),
            )
            early_exit = True
            break

        done, pending = wait(pending, timeout=wait_timeout, return_when=FIRST_COMPLETED)

        for future in done:
            name = future_to_name[future]
            try:
                data = future.result()
                results.extend(data)
                logger.info("%s: %d results", name, len(data))
            except Exception as e:
                logger.warning("%s query failed: %s", name, e)

        # Smart return: if return_time reached and we have results
        if (
            return_time
            and results
            and pending
            and (_time.monotonic() - start) >= return_time
        ):
            logger.info(
                "Smart return at %.1fs with %d results (%d sources pending)",
                _time.monotonic() - start, len(results), len(pending),
            )
            early_exit = True
            break

    if early_exit:
        executor.shutdown(wait=False, cancel_futures=True)
    else:
        executor.shutdown(wait=False)

    return results


# ---------------------------------------------------------------------------
# Error / degradation warnings
# ---------------------------------------------------------------------------

def _classify_source_failures(task_names: list[str], results: list[dict]) -> dict:
    """Classify source failures for user-facing warnings.

    Args:
        task_names: list of task names submitted (e.g. ["FR24", "GoogleFlights", "AirplanesLive"])
        results: combined results from all tasks

    Returns:
        {"google_failed": bool, "all_failed": bool}
    """
    has_google_task = any("google" in n.lower() for n in task_names)
    has_google_result = any(
        "google" in r.get("source", "").lower() for r in results
    )
    google_failed = has_google_task and not has_google_result
    all_failed = len(results) == 0 and len(task_names) > 0

    return {"google_failed": google_failed, "all_failed": all_failed}


def _print_degradation_warnings(failures: dict) -> None:
    """Print user-friendly warnings to stderr based on failure classification."""
    if failures.get("all_failed"):
        print(
            "[Error] 请检查网络连接 / Please check your network connection",
            file=sys.stderr,
        )
    elif failures.get("google_failed"):
        print(
            "[Note] Google 相关服务在您所在地区可能不可用或网络不佳",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------------
# Route relay helpers
# ---------------------------------------------------------------------------

def _extract_relay_route(results: list[dict], flight_number: str) -> dict | None:
    """Extract origin/destination from Phase 1 results for relay query.

    Returns {"origin": "PVG", "destination": "JFK"} or None if route
    cannot be determined.
    """
    fn_upper = flight_number.strip().upper()
    for r in results:
        if r.get("flight_number", "").upper() == fn_upper:
            o = r.get("origin_iata", "")
            d = r.get("destination_iata", "")
            if o and d:
                return {"origin": o, "destination": d}

    # Fallback: any record with both origin and destination
    for r in results:
        o = r.get("origin_iata", "")
        d = r.get("destination_iata", "")
        if o and d:
            return {"origin": o, "destination": d}

    return None


def _has_price(results: list[dict]) -> bool:
    """Check if any result has price data."""
    return any(r.get("price") is not None for r in results)


# ---------------------------------------------------------------------------
# CLI commands (query / search)
# ---------------------------------------------------------------------------

def cmd_query(args):
    """Handle 'query' subcommand: query by flight number.

    Implements two-phase route relay:
    Phase 1: FR24 + Airplanes.live + GoogleFlights(cache) — all concurrent
    Phase 2: If relay ON + route discovered + no price → query Google Flights
             with the discovered route to get price data.
    """
    conf = cfg.get_config()
    sources_cfg = conf["sources"]
    query_cfg = conf["query"]

    # Relay config
    relay_enabled = query_cfg.get("route_relay", True)
    if getattr(args, "no_relay", False):
        relay_enabled = False
    relay_factor = query_cfg.get("relay_timeout_factor", 2)

    base_timeout = getattr(args, "timeout", None) or query_cfg["timeout"]
    return_time = getattr(args, "return_time", None)
    if return_time is None:
        return_time = query_cfg.get("return_time")

    # Phase 1: concurrent query all sources
    tasks = []

    if sources_cfg["fr24"]["enabled"]:
        timeout = sources_cfg["fr24"]["timeout"]
        tasks.append(("FR24", _query_fr24_flight, (args.flight, timeout)))

    if sources_cfg["google_flights"]["enabled"]:
        timeout = sources_cfg["google_flights"]["timeout"]
        serpapi_key = sources_cfg["google_flights"].get("serpapi_key", "")
        tasks.append(("GoogleFlights", _query_gf_flight, (args.flight, timeout, serpapi_key)))

    if sources_cfg["airplanes_live"]["enabled"]:
        timeout = sources_cfg["airplanes_live"]["timeout"]
        tasks.append(("AirplanesLive", _query_al_flight, (args.flight, timeout)))

    task_names = [t[0] for t in tasks]
    phase1_start = _time.monotonic()
    results = _execute_concurrent_queries(tasks, base_timeout, return_time)
    phase1_elapsed = _time.monotonic() - phase1_start

    # Update route cache from Phase 1 results
    route_cache.update_from_records(results)
    route_cache.save()

    # Phase 2: Route relay
    if relay_enabled and results and not _has_price(results):
        route = _extract_relay_route(results, args.flight)
        if route and sources_cfg["google_flights"]["enabled"]:
            effective_timeout = base_timeout * relay_factor
            remaining = effective_timeout - phase1_elapsed
            if remaining > 2:
                logger.info(
                    "Route relay: querying Google Flights for %s→%s (%.1fs remaining)",
                    route["origin"], route["destination"], remaining,
                )
                from datetime import date as date_type
                today = date_type.today().isoformat()
                gf_timeout = sources_cfg["google_flights"]["timeout"]
                serpapi_key = sources_cfg["google_flights"].get("serpapi_key", "")

                relay_tasks = [(
                    "GoogleFlights-Relay",
                    _query_gf_route,
                    (route["origin"], route["destination"], today,
                     gf_timeout, serpapi_key),
                )]
                task_names.append("GoogleFlights-Relay")
                relay_results = _execute_concurrent_queries(
                    relay_tasks, int(remaining)
                )
                results.extend(relay_results)

    # Degradation warnings
    failures = _classify_source_failures(task_names, results)
    _print_degradation_warnings(failures)

    merged = _merge_records(results)

    if args.output == "json":
        print(json.dumps(merged, indent=2, ensure_ascii=False, default=str))
    else:
        print(_format_table(merged, verbose=args.verbose))


def _validate_search_args(args):
    """Validate search arguments, print error and exit on failure."""
    import re
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    if args.return_date and not args.date:
        print("Error: --return requires --date", file=sys.stderr)
        sys.exit(1)

    if args.date and not date_re.match(args.date):
        print(f"Error: invalid date format '{args.date}', expected YYYY-MM-DD",
              file=sys.stderr)
        sys.exit(1)

    if args.return_date:
        if not date_re.match(args.return_date):
            print(f"Error: invalid return date format '{args.return_date}', expected YYYY-MM-DD",
                  file=sys.stderr)
            sys.exit(1)
        if args.return_date < args.date:
            print("Error: return date must be on or after departure date",
                  file=sys.stderr)
            sys.exit(1)

    if args.adults < 1:
        print("Error: --adults must be at least 1", file=sys.stderr)
        sys.exit(1)

    if args.limit is not None and args.limit < 1:
        print("Error: --limit must be at least 1", file=sys.stderr)
        sys.exit(1)


def cmd_search(args):
    """Handle 'search' subcommand: search by route."""
    _validate_search_args(args)

    # Resolve airport codes from user input (city-level: may return multiple)
    origins = airport_manager.resolve_all(args.from_station)
    dests = airport_manager.resolve_all(args.to_station)

    if not origins:
        print(f"Error: cannot resolve origin '{args.from_station}'", file=sys.stderr)
        sys.exit(1)
    if not dests:
        print(f"Error: cannot resolve destination '{args.to_station}'", file=sys.stderr)
        sys.exit(1)

    origin_str = ",".join(origins)
    dest_str = ",".join(dests)
    if len(origins) > 1 or len(dests) > 1:
        logger.info("City-level search: %s → %s", origin_str, dest_str)
    else:
        logger.info("Resolved: %s → %s", origin_str, dest_str)

    conf = cfg.get_config()
    sources_cfg = conf["sources"]
    global_timeout = getattr(args, "timeout", None) or conf["query"]["timeout"]
    return_time = getattr(args, "return_time", None)
    if return_time is None:
        return_time = conf["query"].get("return_time")

    # Smart limit: nonstop=99 (all), with-stops=20, user override takes priority
    stops_val = int(args.stops) if args.stops != "any" else "any"
    if args.limit is not None:
        effective_limit = args.limit
    else:
        effective_limit = 99 if args.stops == "0" else 20

    # Keyword arguments for Google Flights advanced search
    gf_kw = dict(
        return_date=args.return_date, adults=args.adults,
        children=args.children, infants=args.infants,
        cabin=args.cabin, stops=stops_val,
        sort=args.sort, limit=effective_limit,
    )

    # For multi-airport: pass list to Google Flights, single to FR24
    gf_origin = origins if len(origins) > 1 else origins[0]
    gf_dest = dests if len(dests) > 1 else dests[0]

    tasks = []

    # FR24 (single airport only — use primary)
    if sources_cfg["fr24"]["enabled"]:
        timeout = sources_cfg["fr24"]["timeout"]
        tasks.append(("FR24", _query_fr24_route, (origins[0], dests[0], args.date, timeout)))

    # Google Flights (supports multi-airport)
    if sources_cfg["google_flights"]["enabled"] and args.date:
        timeout = sources_cfg["google_flights"]["timeout"]
        serpapi_key = sources_cfg["google_flights"].get("serpapi_key", "")
        import functools
        gf_task = functools.partial(
            _query_gf_route, gf_origin, gf_dest, args.date, timeout, serpapi_key,
            **gf_kw,
        )
        tasks.append(("GoogleFlights", lambda: gf_task(), ()))

    task_names = [t[0] for t in tasks]
    results = _execute_concurrent_queries(tasks, global_timeout, return_time)

    # Degradation warnings
    failures = _classify_source_failures(task_names, results)
    _print_degradation_warnings(failures)

    # Update route cache from results
    route_cache.update_from_records(results)
    route_cache.save()

    merged = _merge_records(results)

    # When searching with stops (not nonstop-only) and no explicit --sort,
    # sort by stops ascending: nonstop first, then 1-stop, 2-stop...
    if args.stops != "0" and args.sort is None:
        merged.sort(key=lambda r: (
            r.get("stops") if r.get("stops") is not None else 999
        ))

    merged = merged[:effective_limit]

    if args.output == "json":
        print(json.dumps(merged, indent=2, ensure_ascii=False, default=str))
    else:
        print(_format_table(merged, verbose=args.verbose))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flyclaw",
        description=f"FlyClaw - Flight Information Aggregation CLI (v{__version__})",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Enable verbose output",
    )
    parser.add_argument(
        "-o", "--output", choices=["table", "json"], default="table",
        help="Output format (default: table)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Shared arguments for subparsers
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v", "--verbose", action="store_true", default=False,
        help="Enable verbose output",
    )
    common.add_argument(
        "-o", "--output", choices=["table", "json"], default="table",
        help="Output format (default: table)",
    )
    common.add_argument(
        "--timeout", type=int, default=None,
        help="Global query timeout in seconds (overrides config)",
    )
    common.add_argument(
        "--return-time", type=int, default=None, dest="return_time",
        help="Smart return time in seconds (overrides config; 0 = disable)",
    )

    # query subcommand
    query_p = subparsers.add_parser(
        "query", help="Query by flight number", parents=[common],
    )
    query_p.add_argument(
        "--flight", "-f", required=True,
        help="Flight number (e.g. CA981)",
    )
    query_p.add_argument(
        "--no-relay", action="store_true", default=False, dest="no_relay",
        help="Disable route relay (skip Phase 2 Google Flights price lookup)",
    )
    query_p.set_defaults(func=cmd_query)

    # search subcommand
    search_p = subparsers.add_parser(
        "search", help="Search by route", parents=[common],
    )
    search_p.add_argument(
        "--from", dest="from_station", required=True,
        help="Origin airport/city (IATA code, Chinese, or English)",
    )
    search_p.add_argument(
        "--to", dest="to_station", required=True,
        help="Destination airport/city",
    )
    search_p.add_argument(
        "--date", "-d", required=False, default=None,
        help="Travel date (YYYY-MM-DD)",
    )
    search_p.add_argument(
        "--return", "-r", dest="return_date", default=None,
        help="Return date for round-trip (YYYY-MM-DD)",
    )
    search_p.add_argument(
        "--adults", "-a", type=int, default=1,
        help="Number of adult passengers (default: 1)",
    )
    search_p.add_argument(
        "--children", type=int, default=0,
        help="Number of child passengers (default: 0)",
    )
    search_p.add_argument(
        "--infants", type=int, default=0,
        help="Number of infant passengers (default: 0)",
    )
    search_p.add_argument(
        "--cabin", "-C", default="economy",
        choices=["economy", "premium", "business", "first"],
        help="Cabin class (default: economy)",
    )
    search_p.add_argument(
        "--limit", "-l", type=int, default=None,
        help="Max results (default: 99 for nonstop, 20 for with-stops)",
    )
    search_p.add_argument(
        "--sort", "-s", default=None,
        choices=["cheapest", "fastest", "departure", "arrival"],
        help="Sort results by criteria",
    )
    search_p.add_argument(
        "--stops", type=str, default="0",
        choices=["0", "1", "2", "any"],
        help="Max stops: 0=nonstop (default), 1=one stop, 2=two stops, any=all",
    )
    search_p.set_defaults(func=cmd_search)

    # update-airports subcommand
    update_p = subparsers.add_parser(
        "update-airports", help="Update airport data from remote URL",
    )
    update_p.add_argument(
        "--url", required=False, default=None,
        help="URL to download airport data from (overrides config)",
    )
    update_p.set_defaults(func=cmd_update_airports)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if getattr(args, "verbose", False) else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Auto-update airport data (skip for update-airports command itself)
    if args.command != "update-airports":
        _auto_update_airports()

    args.func(args)


if __name__ == "__main__":
    main()
