# nng/globe_queries.py - Graph Query & Navigation Interface for OpenCode CIO
import json
from .graph_store import NNGPropertyGraph
from .condition_encoder import ConditionEncoder
from .nearest_trade_engine import NearestTradeEngine, safe_dict

class GlobeQueries:
    def __init__(self):
        self.graph = NNGPropertyGraph()
        self.encoder = ConditionEncoder()
        self.trade_engine = NearestTradeEngine()

    def globe_consult(self, condition_id):
        cond = self.graph.query_condition(condition_id)
        if not cond:
            return {'status': 'NOT_FOUND', 'condition_id': condition_id}
        
        # Pull associated tools
        tools_info = {}
        for t_id in cond.get('mandatory_tools', []):
            tools_info[t_id] = self.graph.query_tool(t_id)

        # Pull relevant synergies
        synergies = [e for e in self.graph.edges if e.get('source') in cond.get('mandatory_tools', []) and e.get('relation') == 'CONFIRMS']

        return {
            'status': 'SUCCESS',
            'condition_id': condition_id,
            'chapter_name': cond.get('name'),
            'description': cond.get('description'),
            'mandatory_tools': tools_info,
            'noise_to_ignore': cond.get('noise_to_ignore'),
            'action_blueprint': cond.get('action_blueprint'),
            'active_synergies': synergies
        }

    def globe_full_book(self):
        return {
            'status': 'SUCCESS',
            'total_nodes': len(self.graph.nodes),
            'total_edges': len(self.graph.edges),
            'nodes': self.graph.nodes,
            'edges': self.graph.edges
        }

    def globe_lookup_tool(self, tool_id):
        res = self.graph.query_tool(tool_id.upper())
        if not res:
            return {'status': 'NOT_FOUND', 'tool_id': tool_id}
        return {'status': 'SUCCESS', 'tool': res}

    def globe_conditions_now(self, mcp_server, symbol='XAUUSD'):
        profile = safe_dict(mcp_server.get_full_institutional_profile(symbol))
        fvg_data = safe_dict(mcp_server.get_fvg_matrix(symbol))
        cvd_data = safe_dict(mcp_server.get_measured_cvd(symbol))
        micro_data = safe_dict(mcp_server.get_live_microstructure(symbol))
        conviction = safe_dict(mcp_server.get_symbol_conviction(symbol))

        state = self.encoder.encode_live_state(profile, fvg_data, cvd_data, micro_data, conviction)
        primary = state['primary_condition']
        consultation = self.globe_consult(primary)
        
        return {
            'status': 'SUCCESS',
            'live_state': state,
            'active_chapter': consultation
        }

    def globe_get_nearest_trade(self, mcp_server, symbol='XAUUSD'):
        return self.trade_engine.resolve_nearest_trade(mcp_server, symbol=symbol)

queries = GlobeQueries()
print('GlobeQueries initialized successfully!')
