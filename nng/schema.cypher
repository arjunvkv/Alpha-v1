// nng/schema.cypher - Cypher Schema for Neo4j / Property Graph Engine

// 1. Constraints (Uniqueness)
CREATE CONSTRAINT tool_name_unique IF NOT EXISTS FOR (t:Tool) REQUIRE t.name IS UNIQUE;
CREATE CONSTRAINT condition_id_unique IF NOT EXISTS FOR (c:Condition) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT usage_id_unique IF NOT EXISTS FOR (u:Usage) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT literature_domain_unique IF NOT EXISTS FOR (l:Literature) REQUIRE l.name IS UNIQUE;

// 2. Indexes for High-Speed Lookups
CREATE INDEX tool_type_idx IF NOT EXISTS FOR (t:Tool) ON (t.type);
CREATE INDEX condition_regime_idx IF NOT EXISTS FOR (c:Condition) ON (c.regime);
CREATE INDEX theorem_name_idx IF NOT EXISTS FOR (th:Theorem) ON (th.name);

// 3. Vector Similarity Index (Cosine metric for condition embeddings)
CREATE VECTOR INDEX condition_embeddings_idx IF NOT EXISTS
FOR (c:Condition) ON (c.embedding)
OPTIONS {indexConfig: {
  ector.dimensions: 384,
  ector.similarity_function: 'cosine'
}};
