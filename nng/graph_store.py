# nng/graph_store.py - Property Graph Store & Persistence
import json, os
from .config import GRAPH_PERSISTENCE_PATH
from .book_content import TOOLS_CATALOG, CONDITIONS_CATALOG, SYNERGIES_CATALOG
from .master_literature_corpus import MASTER_LITERATURE

class NNGPropertyGraph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self._initialize_from_catalogs()

    def _initialize_from_catalogs(self):
        # 1. Add Literature Domains & Theorems
        for domain, data in MASTER_LITERATURE.items():
            self.nodes[domain] = {'type': 'LITERATURE_DOMAIN', 'authors': data['authors'], 'texts': data['texts']}
            for th_id, th_desc in data['theorems'].items():
                self.nodes[th_id] = {'type': 'THEOREM', 'description': th_desc, 'domain': domain}
                self.edges.append({'source': domain, 'target': th_id, 'relation': 'DEFINES'})

        # 2. Add Tools
        for t_id, t_data in TOOLS_CATALOG.items():
            self.nodes[t_id] = {'type': 'TOOL', 'name': t_data['name'], 'category': t_data['type'], 'literature': t_data['literature']}
            # Add FOR usages
            for r in t_data['for_rules']:
                u_id = f'FOR_{t_id}_{hash(r)%10000}'
                self.nodes[u_id] = {'type': 'USAGE_FOR', 'rule': r, 'tool': t_id}
                self.edges.append({'source': t_id, 'target': u_id, 'relation': 'FOR'})
            # Add MUST_NOT usages
            for r in t_data['must_not_rules']:
                m_id = f'MUST_NOT_{t_id}_{hash(r)%10000}'
                self.nodes[m_id] = {'type': 'USAGE_MUST_NOT', 'warning': r, 'tool': t_id}
                self.edges.append({'source': t_id, 'target': m_id, 'relation': 'MUST_NOT'})
            # Add APPLIES_TO conditions
            for c in t_data['applies_to']:
                self.edges.append({'source': t_id, 'target': c, 'relation': 'APPLIES_TO'})

        # 3. Add Conditions
        for c_id, c_data in CONDITIONS_CATALOG.items():
            self.nodes[c_id] = {
                'type': 'CONDITION',
                'name': c_data['name'],
                'description': c_data['description'],
                'mandatory_tools': c_data['mandatory_tools'],
                'noise_to_ignore': c_data['noise_to_ignore'],
                'action_blueprint': c_data['action_blueprint']
            }

        # 4. Add Synergies
        for syn in SYNERGIES_CATALOG:
            self.edges.append({
                'source': syn['source'],
                'target': syn['target'],
                'relation': syn['relation'],
                'description': syn['desc']
            })

    def save_to_disk(self, path=GRAPH_PERSISTENCE_PATH):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = {'nodes': self.nodes, 'edges': self.edges}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def query_tool(self, tool_id):
        t = self.nodes.get(tool_id)
        if not t:
            return None
        for_rules = [self.nodes[e['target']]['rule'] for e in self.edges if e['source'] == tool_id and e['relation'] == 'FOR']
        must_not_rules = [self.nodes[e['target']]['warning'] for e in self.edges if e['source'] == tool_id and e['relation'] == 'MUST_NOT']
        return {
            'tool_id': tool_id,
            'metadata': t,
            'for_rules': for_rules,
            'must_not_rules': must_not_rules
        }

    def query_condition(self, cond_id):
        return self.nodes.get(cond_id)

graph_store = NNGPropertyGraph()
graph_store.save_to_disk()
print('NNGPropertyGraph initialized and saved with nodes:', len(graph_store.nodes), 'edges:', len(graph_store.edges))
