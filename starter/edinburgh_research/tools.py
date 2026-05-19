"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolError, ToolRegistry, ToolResult, _RegisteredTool

from .integrity import _TOOL_CALL_LOG, record_tool_call

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    venue_file = _SAMPLE_DATA / "venues.json"
    if not venue_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "venues.json is missing")

    with open(venue_file) as f:
        venues = json.load(f)

    results = []
    for v in venues:
        if v.get("open_now"):
            area = v.get("area", "").lower()
            search_term = near.lower()
            if search_term in area or (area and area in search_term):
                if v.get("seats_available_evening", 0) >= party_size:
                    if (v.get("hire_fee_gbp", 0) + v.get("min_spend_gbp", 0)) <= budget_max_gbp:
                        results.append(v)

    output = {"near": near, "party_size": party_size, "results": results, "count": len(results)}
    summary = f"venue_search({near}, party={party_size}): {len(results)} result(s)"
    if len(results) == 0:
        summary += "\nHint: Ensure you are using the EXACT party_size and area specified in your context. Do NOT call handoff_to_structured."

    record_tool_call(
        "venue_search",
        {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp},
        output,
    )

    search_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "venue_search")
    if search_count > 3:
        useful_venues = []
        for r in _TOOL_CALL_LOG:
            if r.tool_name == "venue_search" and isinstance(r.output, dict):
                if r.output.get("count", -1) > 0 and r.output.get("results"):
                    for v in r.output["results"]:
                        useful_venues.append(v.get("id", "unknown"))
        useful_message = f"Found: {', '.join(set(useful_venues))}"

        summary = f"""{summary if len(results) == 0 else ""}

        STOP calling venue_search. Use the results you already have
        from previous calls. {useful_message}.
        Do NOT call complete_task until generate_flyer has run. Next step: get_weather or calculate_cost."""

    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 2 — get_weather
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    weather_file = _SAMPLE_DATA / "weather.json"
    if not weather_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "weather.json is missing")

    with open(weather_file) as f:
        weather_data = json.load(f)

    city_key = city.lower()
    if city_key not in weather_data or date not in weather_data[city_key]:
        err = ToolError("SA_TOOL_INVALID_INPUT", f"Weather for {city} on {date} not found")
        output = {"error": str(err)}
        record_tool_call("get_weather", {"city": city, "date": date}, output)
        summary = f"get_weather failed: {city} on {date} not found."
        if city_key in weather_data:
            summary += f" Available dates: {', '.join(weather_data[city_key].keys())}."

        weather_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "get_weather")
        if weather_count > 2:
            summary += "\nSTOP calling get_weather. Use the correct date from the context. Do NOT call complete_task until generate_flyer has run."
            return ToolResult(success=True, output=output, summary=summary)
        return ToolResult(success=False, output=output, summary=summary, error=err)

    day_weather = weather_data[city_key][date]
    output = {
        "city": city,
        "date": date,
        "condition": day_weather["condition"],
        "temperature_c": day_weather["temperature_c"],
        "precip_mm": day_weather.get("precip_mm", 0.0),
        "wind_kph": day_weather.get("wind_kph", 0),
    }
    summary = (
        f"get_weather({city}, {date}): {day_weather['condition']}, {day_weather['temperature_c']}C"
    )

    record_tool_call("get_weather", {"city": city, "date": date}, output)

    weather_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "get_weather")
    if weather_count > 3:
        summary = f"""{summary}
        STOP calling get_weather. Use the results you already have.
        Do NOT call complete_task until generate_flyer has run."""

    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + <venue's hire_fee_gbp + min_spend_gbp>
      deposit_rule  = per deposit_policy thresholds

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    catering_file = _SAMPLE_DATA / "catering.json"
    if not catering_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "catering.json is missing")

    with open(catering_file) as f:
        catering = json.load(f)

    venues_file = _SAMPLE_DATA / "venues.json"
    if not venues_file.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", "venues.json is missing")

    with open(venues_file) as f:
        venues = json.load(f)

    venue = next((v for v in venues if v["id"] == venue_id), None)
    if not venue:
        err = ToolError("SA_TOOL_INVALID_INPUT", f"Venue {venue_id} not found")
        output = {"error": str(err)}
        record_tool_call(
            "calculate_cost",
            {
                "venue_id": venue_id,
                "party_size": party_size,
                "duration_hours": duration_hours,
                "catering_tier": catering_tier,
            },
            output,
        )
        summary = "calculate_cost failed"
        if sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "calculate_cost") > 3:
            summary += "\nSTOP calling calculate_cost. Do NOT call complete_task until generate_flyer has run."
        return ToolResult(success=False, output=output, summary=summary, error=err)

    base_rates = catering["base_rates_gbp_per_head"]
    if catering_tier not in base_rates:
        err = ToolError("SA_TOOL_INVALID_INPUT", f"Catering tier {catering_tier} not found")
        output = {"error": str(err)}
        record_tool_call(
            "calculate_cost",
            {
                "venue_id": venue_id,
                "party_size": party_size,
                "duration_hours": duration_hours,
                "catering_tier": catering_tier,
            },
            output,
        )
        summary = "calculate_cost failed"
        if sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "calculate_cost") > 3:
            summary += "\nSTOP calling calculate_cost. Do NOT call complete_task until generate_flyer has run."
        return ToolResult(success=False, output=output, summary=summary, error=err)

    base_per_head = base_rates[catering_tier]
    venue_mult = catering["venue_modifiers"].get(venue_id, 1.0)

    subtotal = base_per_head * venue_mult * party_size * max(1, duration_hours)
    service = subtotal * catering["service_charge_percent"] / 100.0
    total = subtotal + service + venue["hire_fee_gbp"] + venue["min_spend_gbp"]

    deposit_policy = catering["deposit_policy"]
    if total < 300:
        deposit_rule = deposit_policy.get("under_gbp_300", "no_deposit_required")
    elif total <= 1000:
        deposit_rule = deposit_policy.get("gbp_300_to_1000", "deposit_20_percent")
    else:
        deposit_rule = deposit_policy.get("over_gbp_1000", "deposit_30_percent")

    if deposit_rule == "deposit_20_percent":
        deposit_required = total * 0.2
    elif deposit_rule == "deposit_30_percent":
        deposit_required = total * 0.3
    else:
        deposit_required = 0

    total_gbp = int(round(total))
    deposit_required_gbp = int(round(deposit_required))
    subtotal_gbp = int(round(subtotal))
    service_gbp = int(round(service))

    output = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": subtotal_gbp,
        "service_gbp": service_gbp,
        "total_gbp": total_gbp,
        "deposit_required_gbp": deposit_required_gbp,
    }
    summary = f"calculate_cost({venue_id}, {party_size}): total £{total_gbp}, deposit £{deposit_required_gbp}"

    record_tool_call(
        "calculate_cost",
        {
            "venue_id": venue_id,
            "party_size": party_size,
            "duration_hours": duration_hours,
            "catering_tier": catering_tier,
        },
        output,
    )

    cost_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "calculate_cost")
    if cost_count > 3:
        summary = f"""{summary}
        STOP calling calculate_cost. Use the results you already have.
        Do NOT call complete_task until generate_flyer has run. Next: generate_flyer."""

    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce a markdown flyer and write it to workspace/flyer.md.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a formatted markdown flyer with an H1 title, the event
    facts, a weather summary, and the cost breakdown.

    Returns:
      output: {"path": "workspace/flyer.md", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    workspace_dir = Path(session.workspace_dir)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    flyer_path = workspace_dir / "flyer.md"

    venue_name = event_details.get("venue_name", "Unknown Venue")
    address = event_details.get("venue_address", "Unknown Address")
    date = event_details.get("date", "Unknown Date")
    time = event_details.get("time", "Unknown Time")
    party_size = event_details.get("party_size", 0)
    condition = event_details.get("condition", "Unknown Condition")
    temperature_c = event_details.get("temperature_c", 0)
    total_gbp = event_details.get("total_gbp", 0)
    deposit_required_gbp = event_details.get("deposit_required_gbp", 0)

    md_content = f"""# Booking Flyer

* **Venue:** {venue_name}
* **Address:** {address}
* **Date:** {date}
* **Time:** {time}
* **Party Size:** {party_size}
* **Condition:** {condition}
* **Temperature:** {temperature_c}C
* **Total:** £{total_gbp}
* **Deposit Required:** £{deposit_required_gbp}
"""

    flyer_path.write_text(md_content, encoding="utf-8")
    bytes_written = len(md_content.encode("utf-8"))

    output = {"path": "workspace/flyer.md", "bytes_written": bytes_written}
    summary = f"generate_flyer: wrote {flyer_path} ({len(md_content)} chars)"

    record_tool_call("generate_flyer", {"event_details": event_details}, output)

    flyer_count = sum(1 for r in _TOOL_CALL_LOG if r.tool_name == "generate_flyer")
    if flyer_count > 3:
        summary = f"""{summary}
        STOP calling generate_flyer. Call complete_task now!"""

    return ToolResult(success=True, output=output, summary=summary)


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description=inspect.getdoc(venue_search)
            or "Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description=inspect.getdoc(get_weather)
            or "Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description=inspect.getdoc(calculate_cost)
            or "Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description=inspect.getdoc(generate_flyer)
            or "Write a markdown flyer for the event to workspace/flyer.md.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.md"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]
