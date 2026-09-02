# nng/mcp_tools.py - FastMCPTool Bindings for Node Network Globe
import json
from .globe_queries import GlobeQueries

globe_queries_instance = GlobeQueries()

def register_nng_tools(mcp_app, current_mcp_server_module):
    @mcp_app.tool()
    def globe_consult(condition: str) -> str:
        """Consult the Node Network Globe on a specific market condition (e.g. ABSORPTION_REGIME, VALUE_AREA_ROTATION_REGIME, COT_CROWDING_REGIME) to see mandatory tools, noise to ignore, and action blueprint."""
        res = globe_queries_instance.globe_consult(condition.upper().strip())
        return json.dumps(res, indent=2)

    @mcp_app.tool()
    def globe_full_book() -> str:
        """Retrieve the complete Node Network Globe Knowledge Book catalog with all tools, usages, conditions, and synergies."""
        res = globe_queries_instance.globe_full_book()
        return json.dumps(res, indent=2)

    @mcp_app.tool()
    def globe_lookup_tool(tool_name: str) -> str:
        """Lookup a single trading tool (e.g. CVD_DELTA, FVG_MATRIX, VOLUME_PROFILE, EMA_20_50, RSI_MOMENTUM, COT_REPORT) for its FOR and MUST-NOT rules."""
        res = globe_queries_instance.globe_lookup_tool(tool_name)
        return json.dumps(res, indent=2)

    @mcp_app.tool()
    def globe_conditions_now(symbol: str = 'XAUUSD') -> str:
        """Open the Node Network Globe to the exact active chapter matching current live market telemetry."""
        res = globe_queries_instance.globe_conditions_now(current_mcp_server_module, symbol=symbol)
        return json.dumps(res, indent=2)

    @mcp_app.tool()
    def globe_get_nearest_trade(symbol: str = 'XAUUSD') -> str:
        """Resolve the nearest high-conviction 1.0-lot trade trigger with exact Entry, Hard S, TP, and R:R >= 2.5:1 via the Cognitive Globe."""
        res = globe_queries_instance.globe_get_nearest_trade(current_mcp_server_module, symbol=symbol)
        return json.dumps(res, indent=2)
