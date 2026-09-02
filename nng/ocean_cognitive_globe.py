# ocean_cognitive_globe.py - Pure Python Total O.C.E.A.N. Cognitive Knowledge Graph
from .master_literature_corpus import MASTER_LITERATURE

class CognitiveGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.reverse_edges = {}

    def add_node(self, node_id, **attributes):
        self.nodes[node_id] = attributes
        if node_id not in self.edges:
            self.edges[node_id] = []
        if node_id not in self.reverse_edges:
            self.reverse_edges[node_id] = []

    def add_edge(self, source, target, **attributes):
        if source not in self.nodes:
            self.add_node(source)
        if target not in self.nodes:
            self.add_node(target)
        self.edges[source].append({'target': target, 'attrs': attributes})
        self.reverse_edges[target].append({'source': source, 'attrs': attributes})

    def number_of_nodes(self):
        return len(self.nodes)

    def number_of_edges(self):
        return sum(len(e) for e in self.edges.values())

    def get_neighbors(self, node_id):
        return [e['target'] for e in self.edges.get(node_id, [])]


class OceanCognitiveGlobe:
    def __init__(self):
        self.graph = CognitiveGraph()
        self._build_ocean_graph()

    def _build_ocean_graph(self):
        G = self.graph
        
        # 1. Literature Domain Nodes
        for domain, data in MASTER_LITERATURE.items():
            G.add_node(domain, type='LITERATURE_DOMAIN', authors=data['authors'], texts=data['texts'])
            for th_id, th_desc in data['theorems'].items():
                G.add_node(th_id, type='THEOREM', description=th_desc, domain=domain)
                G.add_edge(domain, th_id, relation='DEFINES_THEOREM')

        # 2. [O] Order Flow & Microstructure Nodes
        G.add_node('ORDER_FLOW_DIMENSION', type='OCEAN_PILLAR', pillar='O', name='Order Flow & Microstructure')
        G.add_node('MCP_GET_MEASURED_CVD', type='MCP_TOOL', tool_name='get_measured_cvd')
        G.add_node('MCP_GET_LIVE_MICROSTRUCTURE', type='MCP_TOOL', tool_name='get_live_microstructure')
        G.add_node('TICK_CVD_DELTA', type='METRIC', pillar='O', description='M5 Cumulative Volume Delta')
        G.add_node('TICK_VELOCITY_TPM', type='METRIC', pillar='O', description='Ticks per minute execution arrival rate')
        G.add_node('PASSIVE_LIMIT_ABSORPTION', type='MARKET_BEHAVIOR', pillar='O', description='Limit orders absorbing aggressive sweeps')
        G.add_node('SPREAD_CROSSING_COST', type='METRIC', pillar='O', description='Bid-Ask spread in points')

        G.add_edge('ORDER_FLOW_DIMENSION', 'MCP_GET_MEASURED_CVD', relation='QUERIED_BY')
        G.add_edge('ORDER_FLOW_DIMENSION', 'MCP_GET_LIVE_MICROSTRUCTURE', relation='QUERIED_BY')
        G.add_edge('MCP_GET_MEASURED_CVD', 'TICK_CVD_DELTA', relation='EXTRACTS')
        G.add_edge('MCP_GET_LIVE_MICROSTRUCTURE', 'TICK_VELOCITY_TPM', relation='EXTRACTS')
        G.add_edge('TICK_VELOCITY_TPM', 'LIMIT_ORDER_ABSORPTION', relation='VALIDATES')
        G.add_edge('TICK_CVD_DELTA', 'LIMIT_ORDER_ABSORPTION', relation='VALIDATES')
        G.add_edge('LIMIT_ORDER_ABSORPTION', 'PASSIVE_LIMIT_ABSORPTION', relation='PROVES')

        # 3. [C] Confluence & 4TF Fractals
        G.add_node('CONFLUENCE_DIMENSION', type='OCEAN_PILLAR', pillar='C', name='4TF Structural Confluence')
        G.add_node('MCP_GET_SYMBOL_CONVICTION', type='MCP_TOOL', tool_name='get_symbol_conviction')
        G.add_node('H4_MACRO_FLOW', type='TIMEFRAME', tf='H4')
        G.add_node('H1_SWING_STRUCTURE', type='TIMEFRAME', tf='H1')
        G.add_node('M15_EXECUTION_PD_ARRAY', type='TIMEFRAME', tf='M15')
        G.add_node('M5_TRIGGER_INVALIDATION', type='TIMEFRAME', tf='M5')
        G.add_node('EMA20_50_GRADIENTS', type='INDICATOR', pillar='C')
        G.add_node('RSI_MOMENTUM_EXHAUSTION', type='INDICATOR', pillar='C')
        G.add_node('DISPLACEMENT_BOS_CHOCH', type='GEOMETRY', pillar='C')

        G.add_edge('CONFLUENCE_DIMENSION', 'MCP_GET_SYMBOL_CONVICTION', relation='QUERIED_BY')
        G.add_edge('MCP_GET_SYMBOL_CONVICTION', 'EMA20_50_GRADIENTS', relation='EXTRACTS')
        G.add_edge('MCP_GET_SYMBOL_CONVICTION', 'RSI_MOMENTUM_EXHAUSTION', relation='EXTRACTS')

        # 4. [E] Economic & Macro Lifecycle
        G.add_node('ECONOMIC_DIMENSION', type='OCEAN_PILLAR', pillar='E', name='Macroeconomic Transmission')
        G.add_node('MCP_GET_LIVE_WORLD_EVENTS', type='MCP_TOOL', tool_name='get_live_world_events')
        G.add_node('US10Y_REAL_YIELDS_TIPS', type='MACRO_DRIVER', beta=-0.85)
        G.add_node('DXY_DOLLAR_INDEX', type='MACRO_DRIVER')
        G.add_node('MACRO_PHASE3_EXHAUSTION', type='MACRO_PHASE', description='News fully priced in, auction takes over')

        G.add_edge('ECONOMIC_DIMENSION', 'MCP_GET_LIVE_WORLD_EVENTS', relation='QUERIED_BY')
        G.add_edge('MCP_GET_LIVE_WORLD_EVENTS', 'US10Y_REAL_YIELDS_TIPS', relation='EXTRACTS')
        G.add_edge('US10Y_REAL_YIELDS_TIPS', 'GOLD_REAL_YIELD_BETA', relation='SUPPORTED_BY')

        # 5. [A] Asset Positioning & Intelligence
        G.add_node('ASSET_POSITIONING_DIMENSION', type='OCEAN_PILLAR', pillar='A', name='Institutional Asset Positioning')
        G.add_node('MCP_ASK_LIBRARIAN', type='MCP_TOOL', tool_name='ask_librarian')
        G.add_node('MCP_QUERY_ANALYST_DESK', type='MCP_TOOL', tool_name='query_analyst_desk')
        G.add_node('MCP_BACKTEST_THESIS', type='MCP_TOOL', tool_name='backtest_thesis')
        G.add_node('COT_100TH_PERCENTILE_CROWDING', type='POSITIONING_TRAP')
        G.add_node('ULM_PATTERN_REALITY_CHECK', type='MEMORY_STORE', patterns_count=499)

        G.add_edge('ASSET_POSITIONING_DIMENSION', 'MCP_ASK_LIBRARIAN', relation='QUERIED_BY')
        G.add_edge('ASSET_POSITIONING_DIMENSION', 'MCP_QUERY_ANALYST_DESK', relation='QUERIED_BY')
        G.add_edge('ASSET_POSITIONING_DIMENSION', 'MCP_BACKTEST_THESIS', relation='QUERIED_BY')
        G.add_edge('COT_100TH_PERCENTILE_CROWDING', 'COT_100TH_PERCENTILE_TRAP', relation='SUPPORTED_BY')

        # 6. [N] Narrative, Volume Profile & Smart Money PD Arrays
        G.add_node('NARRATIVE_VP_DIMENSION', type='OCEAN_PILLAR', pillar='N', name='Volume Profile & PD Arrays')
        G.add_node('MCP_GET_FULL_PROFILE', type='MCP_TOOL', tool_name='get_full_institutional_profile')
        G.add_node('MCP_GET_FVG_MATRIX', type='MCP_TOOL', tool_name='get_fvg_matrix')
        G.add_node('VOLUME_PROFILE_POC', type='AUCTION_LEVEL')
        G.add_node('VALUE_AREA_HIGH_VAH', type='AUCTION_LEVEL')
        G.add_node('VALUE_AREA_LOW_VAL', type='AUCTION_LEVEL')
        G.add_node('FVG_50PCT_CONSEQUENT_ENCROACHMENT', type='PD_ARRAY_ANCHOR')
        G.add_node('ASIAN_SESSION_SWEEP', type='LIQUIDITY_EVENT')

        G.add_edge('NARRATIVE_VP_DIMENSION', 'MCP_GET_FULL_PROFILE', relation='QUERIED_BY')
        G.add_edge('NARRATIVE_VP_DIMENSION', 'MCP_GET_FVG_MATRIX', relation='QUERIED_BY')
        G.add_edge('MCP_GET_FULL_PROFILE', 'VALUE_AREA_HIGH_VAH', relation='EXTRACTS')
        G.add_edge('MCP_GET_FULL_PROFILE', 'VOLUME_PROFILE_POC', relation='EXTRACTS')
        G.add_edge('MCP_GET_FULL_PROFILE', 'VALUE_AREA_LOW_VAL', relation='EXTRACTS')
        G.add_edge('MCP_GET_FVG_MATRIX', 'FVG_50PCT_CONSEQUENT_ENCROACHMENT', relation='EXTRACTS')

        # Cross-Domain Synergistic Causal Links (The Neural Wiring)
        G.add_edge('PASSIVE_LIMIT_ABSORPTION', 'FVG_50PCT_CONSEQUENT_ENCROACHMENT', weight=0.96, relation='ANCHORS_AT')
        G.add_edge('FVG_50PCT_CONSEQUENT_ENCROACHMENT', 'VALUE_AREA_HIGH_VAH', weight=0.91, relation='ROTATES_TOWARD')
        G.add_edge('FVG_50PCT_CONSEQUENT_ENCROACHMENT', 'VOLUME_PROFILE_POC', weight=0.88, relation='ROTATES_TOWARD')
        G.add_edge('COT_100TH_PERCENTILE_CROWDING', 'PASSIVE_LIMIT_ABSORPTION', weight=0.93, relation='CONFIRMS_REVERSAL')
        G.add_edge('US10Y_REAL_YIELDS_TIPS', 'FVG_50PCT_CONSEQUENT_ENCROACHMENT', weight=0.89, relation='MACRO_SUPPORTS_SELL')

    def get_graph_summary(self):
        return {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'pillars': ['O', 'C', 'E', 'A', 'N']
        }
