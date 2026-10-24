# Reflection

I drew the lines between the tools by **which side effect each one owns**. `get_weather_forecast` is the only tool that reaches the outside world, and it never writes anything. `save_trip` is the only tool that writes, and it never touches the network or decides anything about the weather. `plan_trip` owns neither effect. It sequences the other two through `mcp.call_tool` and combines their results, building the summary and packing list with pure functions.

That rule made the "and" test easy to apply. Geocoding was the hardest call. "Forecast for a city" needs the city's coordinates, and a separate `geocode_city` tool would have been a fourth tool and would have made the LLM pass coordinates around. I kept geocoding inside the Data tool, because from the caller's point of view it is one purpose. To handle ambiguity, the tool accepts a "City, Country" qualifier: "Tripoli" alone resolves to Libya, while "Tripoli, Lebanon" does not.

Calling the *registered* tools from the orchestrator, instead of shared helper functions, mattered more than I expected. The orchestrator inherits the same validation and the same clear errors, so its failures chain naturally ("stopped at step 1 … Nothing was saved"). The tests check that a failed forecast leaves the trip store untouched. Two real failures during development shaped the error handling:
- My planned "unknown city" example, *Atlantis*, turned out to be a real town in South Africa.
- Open-Meteo timed out on one live call, which is why the Data tool now retries once before reporting the outage.

Three tools were right for the core flow, but tight at the edges. Each tool earns its place, the orchestrator does real work, and three distinct descriptions with matching MCP annotations kept the LLM's routing simple.

Viewing saved trips is a pure lookup, so I exposed it as resources (`trips://saved`, `trips://{trip_id}`), not as a fourth tool. That revealed a gap: the Agents SDK does not hand resources to the model, so the agent cannot answer "what trips have I saved?" on its own. Only the host's `/trips` command can read them.

Next steps:
- Add a read-only `list_trips` Data tool.
- Add a `delete_trip` Action tool marked `destructiveHint=True` and gated behind the SDK's `require_approval`.
- Cache forecasts to ride out API hiccups.
- Deploy over Streamable HTTP with authentication.
- Add routing between cities. This was the mapping theme I set aside because free routing and points-of-interest APIs proved unreliable.
- Build a small evaluation set of prompts to measure how often the agent picks the right tool.
