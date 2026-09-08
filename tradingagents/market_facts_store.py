"""
market_facts_store.py
SQLite FTS5 store for trade scientist market facts with in-memory caching,
multi-vocabulary synonym expansion, and live context auto-fallback.
"""

import sqlite3
import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(r"C:\Trading\Alpha\data\live", "market_facts.db")

# In-memory cached catalog for ultra-fast thread-safe queries (< 0.05 ms)
_IN_MEMORY_FACTS: List[Dict[str, Any]] = []
_FACT_MAP: Dict[str, Dict[str, Any]] = {}

CORE_FACTS = [
    {
        "fact_id": "predatory_stop_hunt",
        "canonical_name": "Predatory Liquidity Hunting at Clustered Stops",
        "trade_scientists": "Markus Brunnermeier & Lasse Pedersen (2005), Larry Harris (2003)",
        "synonyms": "equal lows equal highs stop hunt sweep raid double bottom break double top break ssl bsl fakeout support pierce resting stops liquidation spike stop cascade trap",
        "microstructure_reality": "Resting stop clusters are predatory liquidity magnets. Strategic algorithms intentionally drive price through equal lows/highs to trigger forced market orders, unlocking zero-slippage counterparty volume for large institutional absorption.",
        "crowd_implication": "When crowd plans show stops clustered tightly under equal lows or above equal highs, the breakdown/breakout is a planned predatory raid. Price will overshoot into the stops before mean-reverting sharply.",
        "evidence_required": "Price pierces the stop cluster, CVD delta shows positive absorption or volume stalls, and tape velocity drops from >90 down to <40 t/m.",
        "invalidation_boundary": "If velocity stays >80 t/m with expanding directional delta (>3000 pts) and H1 closure beyond the level, this is INITIATIVE EXPANSION, NOT a trap. DO NOT FADE.",
        "literature": "Brunnermeier & Pedersen (2005) 'Predatory Trading', Journal of Finance"
    },
    {
        "fact_id": "latent_order_book_vacuum",
        "canonical_name": "Latent Order Book Fragility and Air Pocket Vacuums",
        "trade_scientists": "Jean-Philippe Bouchaud et al. (2018), Albert Pete Kyle (1985)",
        "synonyms": "air pocket vacuum thin book low liquidity void freefall fast drop slippage zone spread widening low depth illiquid gap",
        "microstructure_reality": "Visible limit order book depth represents <1% of true market intent. In air pocket zones, Kyle's Lambda (price sensitivity) spikes exponentially, allowing modest aggressive volume to displace price frictionless through empty books.",
        "crowd_implication": "Price traversing an air pocket is not displaying strong permanent trend volume; it is simply sliding through an empty book. Do not chase inside the pocket.",
        "evidence_required": "Telemetry reports air pocket zone; tick velocity is high but volume profile shows low traded volume per price tick.",
        "invalidation_boundary": "Once price reaches the opposing high-volume shelf (POC or Value Area boundary), Kyle's Lambda collapses and normal quote depth replenishes. Never hold an air-pocket momentum trade into a high-volume node.",
        "literature": "Bouchaud et al. (2018) 'Trades, Quotes and Prices', Cambridge University Press; Kyle (1985) Econometrica"
    },
    {
        "fact_id": "delta_absorption_exhaustion",
        "canonical_name": "Passive Limit Order Absorption and OFI Directional Flip",
        "trade_scientists": "Joel Hasbrouck (2007), Maureen O'Hara (1995), Rama Cont (2014)",
        "synonyms": "delta absorption trapped buyers trapped sellers cvd divergence limit wall ask wall bid wall ofi flip exhaustion wick pin bar reversal mitigation change of character choch",
        "microstructure_reality": "A surge in aggressive market orders (large positive or negative CVD) failing to advance price proves that large passive institutional limit orders are absorbing all aggressive flow. The moment market orders exhaust, Order Flow Imbalance (OFI) violently inverts.",
        "crowd_implication": "When crowd plans chase green/red momentum bars at extremes, they are buying directly into institutional limit walls. When delta exhausts, price snaps violently in the opposite direction.",
        "evidence_required": "Cumulative Volume Delta (CVD) makes an extreme print while price forms a rejection wick, followed by delta slope flattening.",
        "invalidation_boundary": "If CVD keeps accelerating and price continuously prints new ticks without rejection wicks, passive limit walls have been pulled or breached. Do not fight continuous order flow imbalance.",
        "literature": "Hasbrouck (2007) 'Empirical Market Microstructure'; Cont et al. (2014) Journal of Financial Econometrics"
    },
    {
        "fact_id": "long_memory_initiative_trend",
        "canonical_name": "Long-Memory Order Flow Persistence and Initiative Trend Discovery",
        "trade_scientists": "J. Doyne Farmer & Fabrizio Lillo (2004), J. Peter Steidlmayer (1986)",
        "synonyms": "initiative selling initiative buying strong trend momentum run breakdown continuation displacement bos market structure break expansion leg heavy volume",
        "microstructure_reality": "Order flow is not a random walk; trade signs exhibit power-law long-memory autocorrelation. High-velocity departure from the Point of Control with expanding one-sided delta exhibits self-exciting persistence. This is Initiative Discovery seeking new balance.",
        "crowd_implication": "Retail crowd attempts to buy dips or fade back to the POC during an initiative drive are fighting a multi-million dollar liquidation wave. They provide trapped exit liquidity for trend continuation.",
        "evidence_required": "Price departs Value Area with velocity >80 t/m, one-sided CVD expansion with zero divergence, and clean candle closes outside range.",
        "invalidation_boundary": "Initiative persistence is exhausted only when a high-volume absorption node prints with tape velocity falling <40 t/m and delta slope reversing.",
        "literature": "Farmer & Lillo (2004) 'Power-law tails in financial prices'; Steidlmayer (1986) 'Auction Market Theory'"
    },
    {
        "fact_id": "auction_excess_and_poc_reversion",
        "canonical_name": "Auction Market Excess and Responsive Mean Reversion to POC",
        "trade_scientists": "J. Peter Steidlmayer & James Dalton (1986, 1993), Marco Avellaneda (2008)",
        "synonyms": "auction excess responsive activity mean reversion poc magnet value area rejection return to range range bound fade excess unfair price vah rejection val rejection",
        "microstructure_reality": "The market's primary function is to facilitate trade. Price testing outside the Value Area (VAH/VAL) without institutional volume acceptance is an 'unfair auction' (excess). The market responds by rotating price back to the highest liquidity node: the Point of Control (POC).",
        "crowd_implication": "When crowd plans attempt breakout continuation outside Value Area during low velocity (<50 t/m), the auction rejects. Smart capital responds by fading price back into the volume center.",
        "evidence_required": "Price tests outside VAH/VAL on low tick volume, prints an elongated rejection tail, and rotates back inside the value boundary.",
        "invalidation_boundary": "If volume and delta surge outside value and establish a 30-minute value bracket above/below VAH/VAL, the move is accepted. Responsive fade is immediately invalidated.",
        "literature": "Steidlmayer & Dalton (1986, 1993) 'Mind Over Markets'; Avellaneda & Stoikov (2008)"
    },
    {
        "fact_id": "adverse_selection_retail_momentum",
        "canonical_name": "Sequential Adverse Selection and Flow Toxicity (VPIN)",
        "trade_scientists": "Lawrence Glosten & Paul Milgrom (1985), David Easley & Marcos Lopez de Prado (2012)",
        "synonyms": "adverse selection toxic flow vpin retail momentum chasing green buying top selling bottom spread widening quote withdrawal dealer shading",
        "microstructure_reality": "The bid-ask spread is an insurance premium against toxic order flow. When retail traders pile into market orders simultaneously, market makers widen spreads and withdraw passive quotes, allowing price to drop straight into retail stop clusters.",
        "crowd_implication": "Retail traders buying breakouts at market pay maximum spread and receive the worst fill right at the top from resting institutional limit asks.",
        "evidence_required": "Spread widens, retail crowd sentiment >80% biased, green candles stall at resistance with high volume.",
        "invalidation_boundary": "If institutional block buy orders enter behind the retail flow (permanent impact), price will break cleanly. Verify whether macro yield or DXY confirms the move.",
        "literature": "Glosten & Milgrom (1985) JFE; Easley, Lopez de Prado, O'Hara (2012) RFS"
    },
    {
        "fact_id": "temporary_impact_decay",
        "canonical_name": "Temporary Impact Decay and Square-Root Law Mean Reversion",
        "trade_scientists": "Robert Almgren & Neil Chriss (2000), Jean-Philippe Bouchaud (2018)",
        "synonyms": "temporary impact impact decay mean reversion bounce square root law snap back wick rejection snap back wick recovery counter sweep",
        "microstructure_reality": "Aggressive market sweeps displace price non-linearly (I ~ sqrt(Q/V)), but this displacement is overwhelmingly temporary impact. Once the stop-liquidation volume is satisfied, temporary impact decays exponentially, snapping price back to equilibrium.",
        "crowd_implication": "Do not trail stop losses into the sweep zone or move take-profit targets further away. The snap-back decay happens rapidly; bank profit at fair value before opposing quote replenishment.",
        "evidence_required": "Price spikes 3-8 points outside a key level on stop trigger, then immediately prints a counter-bar with falling velocity.",
        "invalidation_boundary": "If price holds beyond the level for more than 3 consecutive 5-minute candles with expanding volume, temporary impact has converted into permanent informational drift.",
        "literature": "Almgren & Chriss (2000) Journal of Risk; Bouchaud et al. (2018)"
    },
    {
        "fact_id": "volatility_clustering_leverage_asymmetry",
        "canonical_name": "Volatility Clustering and Post-Sweep Variance Compression",
        "trade_scientists": "Robert F. Engle (1982 Nobel), Benoit Mandelbrot (1963)",
        "synonyms": "volatility clustering garch shock variance compression post sweep calm quiet after storm range expansion range contraction",
        "microstructure_reality": "Volatility is not Gaussian; high volatility clusters after high volatility shocks (ARCH/GARCH dynamics). A violent stop-hunt raid temporarily spikes variance before condensing into quiet structural consolidation.",
        "crowd_implication": "Do not enter new breakout trades immediately after a high-volatility sweep. Wait for variance compression and the first structural pause before positioning.",
        "evidence_required": "Tick velocity spikes >120 t/m, followed by steady drop to <50 t/m over 2-3 bars.",
        "invalidation_boundary": "If high-impact macroeconomic news is actively breaking, volatility will not compress; it will chain into secondary shock waves.",
        "literature": "Engle (1982) Econometrica; Mandelbrot (1963) Journal of Business"
    }
]


def init_market_facts_db():
    """Initializes the SQLite FTS5 database and in-memory cache."""
    global _IN_MEMORY_FACTS, _FACT_MAP
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        
        # Create FTS5 virtual table
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS market_facts_fts USING fts5(
                fact_id UNINDEXED,
                canonical_name,
                trade_scientists,
                synonyms,
                microstructure_reality,
                crowd_implication,
                evidence_required,
                invalidation_boundary,
                literature,
                prefix='2 3'
            );
        """)
        
        # Check if table already populated
        cursor = conn.execute("SELECT COUNT(*) FROM market_facts_fts")
        count = cursor.fetchone()[0]
        
        if count == 0:
            for f in CORE_FACTS:
                conn.execute("""
                    INSERT INTO market_facts_fts (
                        fact_id, canonical_name, trade_scientists, synonyms,
                        microstructure_reality, crowd_implication, evidence_required,
                        invalidation_boundary, literature
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f["fact_id"], f["canonical_name"], f["trade_scientists"], f["synonyms"],
                    f["microstructure_reality"], f["crowd_implication"], f["evidence_required"],
                    f["invalidation_boundary"], f["literature"]
                ))
            conn.commit()
            
    # Load into in-memory cache
    _IN_MEMORY_FACTS = list(CORE_FACTS)
    _FACT_MAP = {f["fact_id"]: f for f in CORE_FACTS}
    logger.info(f"Market Facts DB initialized with {len(_IN_MEMORY_FACTS)} core facts (in-memory cached).")


def get_live_market_state_fact(symbol: str = "XAUUSD") -> Dict[str, Any]:
    """Fallback: Inspects live market state and returns the governing fact."""
    try:
        # Check nearest crowd plan or CVD state
        import sqlite3
        crowd_db = os.path.join(r"C:\Trading\Alpha\data\live", "crowd_trap.db")
        if os.path.exists(crowd_db):
            with sqlite3.connect(crowd_db) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT headline, bear_stops, bull_stops FROM crowd_plans ORDER BY id DESC LIMIT 1").fetchone()
                if row:
                    headline = str(row["headline"]).lower()
                    if "sweep" in headline or "low" in headline or "high" in headline:
                        return _FACT_MAP.get("predatory_stop_hunt", CORE_FACTS[0])
                    elif "poc" in headline or "reversion" in headline:
                        return _FACT_MAP.get("auction_excess_and_poc_reversion", CORE_FACTS[4])
    except Exception:
        pass
    return _FACT_MAP.get("predatory_stop_hunt", CORE_FACTS[0])


def query_market_fact(query: str = "", symbol: str = "XAUUSD") -> Dict[str, Any]:
    """
    Intelligent zero-waste search for trade scientist market facts.
    - Matches exact fact_id
    - Matches FTS5 BM25 across synonyms, names, and text
    - Never returns empty: Falls back to live market state fact if 0 hits.
    """
    if not _IN_MEMORY_FACTS:
        init_market_facts_db()
        
    cleaned_query = (query or "").strip().lower()
    
    # 1. Direct fact_id match
    if cleaned_query in _FACT_MAP:
        res = dict(_FACT_MAP[cleaned_query])
        res["match_type"] = "EXACT_FACT_ID"
        return res
        
    # 2. Empty query -> return live market state fact
    if not cleaned_query:
        fallback = get_live_market_state_fact(symbol)
        res = dict(fallback)
        res["match_type"] = "LIVE_MARKET_STATE_AUTOSELECTION"
        res["note"] = "Query was empty; automatically matched governing fact for current live market condition."
        return res
        
    # 3. Fast In-Memory Keyword / Synonym Match (< 0.05 ms)
    query_tokens = [t for t in cleaned_query.replace("-", " ").replace("_", " ").split() if len(t) > 2]
    best_fact = None
    best_score = 0
    
    for f in _IN_MEMORY_FACTS:
        score = 0
        searchable = f"{f['fact_id']} {f['canonical_name']} {f['synonyms']} {f['microstructure_reality']} {f['crowd_implication']}".lower()
        for token in query_tokens:
            if token in f["fact_id"]:
                score += 5
            elif token in f["synonyms"]:
                score += 3
            elif token in searchable:
                score += 1
        if score > best_score:
            best_score = score
            best_fact = f
            
    if best_fact and best_score >= 2:
        res = dict(best_fact)
        res["match_type"] = "SYNONYM_RELEVANCE_MATCH"
        res["match_score"] = best_score
        return res
        
    # 4. SQLite FTS5 Full-Text Search Fallback
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            fts_query = " OR ".join([f'"{t}"*' for t in query_tokens]) if query_tokens else f'"{cleaned_query}"'
            row = conn.execute("""
                SELECT fact_id, bm25(market_facts_fts) as rank
                FROM market_facts_fts
                WHERE market_facts_fts MATCH ?
                ORDER BY rank ASC
                LIMIT 1
            """, (fts_query,)).fetchone()
            if row:
                fid = row["fact_id"]
                if fid in _FACT_MAP:
                    res = dict(_FACT_MAP[fid])
                    res["match_type"] = "FTS5_BM25_MATCH"
                    return res
    except Exception as e:
        logger.warning(f"FTS5 query exception: {e}")
        
    # 5. Zero-waste fallback: return live market state fact
    fallback = get_live_market_state_fact(symbol)
    res = dict(fallback)
    res["match_type"] = "FALLBACK_LIVE_MARKET_STATE"
    res["note"] = f"No direct academic match for '{query}'; returned closest governing microstructure fact for live market state."
    return res


# Initialize on module import
init_market_facts_db()
