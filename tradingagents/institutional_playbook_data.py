"""
Alpha Trading Desk - Institutional Playbook Seed Data
Curated from premier quantitative, auction market theory, order flow,
Wyckoff, options GEX, and macro literature.
"""

INSTITUTIONAL_CONCEPTS = [
    # -------------------------------------------------------------
    # 1. AUCTION MARKET THEORY (Dalton 1990, Steidlmayer 1986)
    # -------------------------------------------------------------
    {
        "concept_id": "AMT_80_PCT_RULE_ROTATION",
        "category": "AUCTION_MARKET_THEORY",
        "title": "The 80% Rule of Value Area Rotation",
        "author_citation": "James F. Dalton, 'Mind Over Markets' (1990); CBOT Market Profile",
        "core_law": "When price opens or probes outside the established Value Area (VAH/VAL), fails to find acceptance, and re-enters the Value Area on an M5 candle close, there is an 80% historical probability of rotating completely through to the opposing Value Area boundary.",
        "physical_trigger": "Price sweeps outside VAH or VAL -> rejected with wick -> M5 candle closes back inside Value Area -> opposing runway is clear.",
        "invalidation": "Any clean M15 close back outside the swept extreme invalidates the rotation thesis.",
        "runway_behavior": "Price accelerates through Low Volume Nodes (LVN) around Point of Control (POC) directly toward opposing Value Area edge.",
        "risk_guidance": "Target Mode A: Opposing POC or opposing Value Area boundary. SL placed beyond the rejection wick outside Value Area.",
        "tags": ["AMT", "VALUE_AREA", "ROTATION", "80_PCT_RULE", "DALTON", "POC", "DAY_LOW_SWEEP", "DAY_HIGH_SWEEP", "M5_RECLAIM", "VALUE_AREA_RECLAIM"]
    },
    {
        "concept_id": "AMT_DAY_TYPES_CLASSIFICATION",
        "category": "AUCTION_MARKET_THEORY",
        "title": "Auction Market Day Type Classification",
        "author_citation": "J. Peter Steidlmayer, 'Steidlmayer on Markets' (1986); Jim Dalton",
        "core_law": "Sessions are structurally classified by Initial Balance (IB) extension behavior into: Trend Day (directional drive, IB broken early, zero range re-entry), Normal Variation (IB extended 1-2x by other timeframe participants), and Neutral/Chop (both sides of IB tested without acceptance).",
        "physical_trigger": "Evaluate first hour IB High/Low: Single-side kinetic extension with volume = Trend Day; Symmetrical tests with absorption = Balanced Rotation.",
        "invalidation": "Attempted breakout of IB that immediately closes back inside IB shifts day type from Trend Day to Neutral/Rotation.",
        "runway_behavior": "Trend days offer open runways with single prints. Neutral days mandate fading the outer 20% extremes back toward POC.",
        "risk_guidance": "NEVER fade a verified Trend Day (Veto 7). In Neutral days, trade ONLY resting limit retests at Value Area extremes.",
        "tags": ["AMT", "DAY_TYPES", "INITIAL_BALANCE", "TREND_DAY", "STEIDLMAYER"]
    },
    {
        "concept_id": "AMT_PROFILE_SHAPES_P_B",
        "category": "AUCTION_MARKET_THEORY",
        "title": "Volume Profile Structural Shapes (P-shape, b-shape, Double Distribution)",
        "author_citation": "James F. Dalton, 'Markets in Profile' (2007)",
        "core_law": "P-shaped profiles indicate short-covering and aggressive buying higher with a thin tail below (often stalls once covering ends). b-shaped profiles indicate long liquidation and aggressive selling lower with a thin tail above. Double Distribution indicates two distinct value areas separated by a Low Volume Node (LVN) air pocket.",
        "physical_trigger": "Inspect session volume distribution: heavy volume concentrated in upper 30% = P-shape; heavy volume in lower 30% = b-shape.",
        "invalidation": "Value migrating and filling the thin volume tail invalidates the distribution shape.",
        "runway_behavior": "The thin single-print tail acts as an air pocket: if re-entered, price travels rapidly across it to the prior balance.",
        "risk_guidance": "Do not chase the head of a P-shape or b-shape; wait for retest of the LVN shelf connecting the tail to the value cluster.",
        "tags": ["AMT", "VOLUME_PROFILE", "P_SHAPE", "B_SHAPE", "DOUBLE_DISTRIBUTION", "LVN"]
    },
    {
        "concept_id": "AMT_VALUE_AREA_FAIR_PRICE",
        "category": "AUCTION_MARKET_THEORY",
        "title": "Value Area & Unfair Price Discovery Dynamics",
        "author_citation": "J. Peter Steidlmayer (1986); Chicago Board of Trade (CBOT)",
        "core_law": "Value Area represents ~70% of volume (one standard deviation of normal distribution). Prices inside Value Area represent fair value where two-sided trade is facilitated. Prices outside Value Area represent 'unfair' prices being tested by other-timeframe (OTF) buyers and sellers.",
        "physical_trigger": "Price probing above VAH (unfair high) or below VAL (unfair low). Watch whether OTF participants accept or reject.",
        "invalidation": "Sustained time and volume acceptance outside VAH/VAL establishes a new Value Area and invalidates mean-reversion.",
        "runway_behavior": "Inside Value Area, price oscillates around Point of Control (POC). Outside Value Area, price either discovers new value or snaps back violently.",
        "risk_guidance": "Zero breakout orders permitted inside Value Area (Veto 1 chop). Stage Prong A limits only at Value Area boundaries.",
        "tags": ["AMT", "VALUE_AREA", "POC", "VAH", "VAL", "UNFAIR_PRICE"]
    },

    # -------------------------------------------------------------
    # 2. ORDER FLOW & MICROSTRUCTURE (Harris 2003, Jigsaw, Bookmap)
    # -------------------------------------------------------------
    {
        "concept_id": "ORDER_FLOW_PASSIVE_ABSORPTION",
        "category": "ORDER_FLOW_MICROSTRUCTURE",
        "title": "Passive Limit Order Absorption at Structural Shelves",
        "author_citation": "Larry Harris, 'Trading and Exchanges: Market Microstructure for Practitioners' (2003)",
        "core_law": "When aggressive market participants fire high volume delta at a key level but price fails to make progress, institutional passive limit orders are absorbing the liquidity. Once aggressive flow exhausts, price reverses sharply in the direction of the passive absorbers.",
        "physical_trigger": "High negative CVD delta at support with price forming wicks rather than breaking lows (or high positive CVD at resistance without upside progress).",
        "invalidation": "Aggressive market orders chewing completely through the resting limit depth, followed by immediate quote displacement lower/higher.",
        "runway_behavior": "Once absorption flips, aggressive market orders trigger on the reverse side, targeting the stops of trapped aggressive participants.",
        "risk_guidance": "Pattern A and Prong C validation: trade in the direction of the absorbing institutional party. Invalidation placed 1.0 pt beyond absorption wick.",
        "tags": ["ORDER_FLOW", "ABSORPTION", "CVD", "CVD_ABSORPTION", "ABSORPTION_WICK", "CVD_FLIP", "LIQUIDITY", "HARRIS", "TAPE_READING"]
    },
    {
        "concept_id": "ORDER_FLOW_DELTA_EXHAUSTION",
        "category": "ORDER_FLOW_MICROSTRUCTURE",
        "title": "Order Flow Delta Exhaustion vs Kinetic Drive",
        "author_citation": "Larry Harris (2003); Quantower / Jigsaw Order Flow Documentation",
        "core_law": "A true breakout requires accelerating kinetic delta and tick velocity (>100 t/m). When price pushes to a new session extreme but CVD delta flattens or reverses (Delta Exhaustion), the move lacks institutional participation and is vulnerable to immediate mean-reversion collapse.",
        "physical_trigger": "New price high/low formed with declining volume delta and tick velocity dropping <50 t/m -> divergence flag triggered.",
        "invalidation": "Sudden volume surge with fresh aggressive market orders re-accelerating velocity >100 t/m.",
        "runway_behavior": "Exhaustion at session extremes creates a fast vacuum back to the session Point of Control (POC).",
        "risk_guidance": "STRICT BAN on entering breakout stops into exhausted delta (Veto 7). Wait for external sweep & reclaim.",
        "tags": ["ORDER_FLOW", "EXHAUSTION", "DELTA", "CVD_DIVERGENCE", "VELOCITY"]
    },
    {
        "concept_id": "ORDER_FLOW_CVD_DIVERGENCE",
        "category": "ORDER_FLOW_MICROSTRUCTURE",
        "title": "Cumulative Volume Delta (CVD) Structural Divergence",
        "author_citation": "Larry Harris (2003); CME Group Order Flow Mechanics",
        "core_law": "Bullish Delta Divergence occurs when price makes an equal or lower low while CVD forms a distinctly higher low (commercial accumulation). Bearish Delta Divergence occurs when price makes an equal or higher high while CVD forms a lower high (commercial distribution).",
        "physical_trigger": "Price tests prior swing low/high while 10-bar CVD slope shows inverse polarity.",
        "invalidation": "CVD violently breaking down/up in alignment with price cancels the divergence.",
        "runway_behavior": "Divergence signals trapped retail market orders; rotation travels across the dealing range to opposing swing liquidity.",
        "risk_guidance": "Must be accompanied by structural shelf retest or external sweep reclaim. Zero blind entries based on CVD divergence alone.",
        "tags": ["ORDER_FLOW", "CVD_DIVERGENCE", "ACCUMULATION", "DISTRIBUTION", "TAPE"]
    },
    {
        "concept_id": "ORDER_FLOW_STACKED_IMBALANCES",
        "category": "ORDER_FLOW_MICROSTRUCTURE",
        "title": "Stacked Footprint Diagonal Imbalances",
        "author_citation": "Quantower / ATAS Footprint Documentation; Harris (2003)",
        "core_law": "When 3 or more consecutive price levels show diagonal bid/ask volume imbalances exceeding a 3:1 ratio (300%+ buyer/seller dominance), aggressive institutional capital is actively sweeping the order book. The zone containing the stacked imbalances becomes immediate support/resistance on pullbacks.",
        "physical_trigger": "Kinetic expansion candle with multiple stacked buy or sell diagonal imbalances + velocity >90 t/m.",
        "invalidation": "Price closing through the origin of the stacked imbalance cluster invalidates institutional defense.",
        "runway_behavior": "Pullbacks to the tip of stacked imbalances provide high-probability retest entries (Prong A / Pattern C).",
        "risk_guidance": "Stage resting limit orders at the outer edge of the imbalance cluster. SL anchored 1.5 pts behind the cluster base.",
        "tags": ["ORDER_FLOW", "FOOTPRINT", "IMBALANCE", "STACKED_IMBALANCE", "KINETIC_EXPANSION"]
    },
    {
        "concept_id": "ORDER_FLOW_INSTITUTIONAL_VWAP",
        "category": "ORDER_FLOW_MICROSTRUCTURE",
        "title": "Volume-Weighted Average Price (VWAP) & Standard Deviation Bands",
        "author_citation": "Larry Harris, 'Trading and Exchanges' (2003); Institutional Execution Algorithms",
        "core_law": "VWAP is the primary execution benchmark for institutional order execution algorithms (VWAP/TWAP algos). Institutional buyers seek fills below VWAP (discount); institutional sellers seek fills above VWAP (premium). The +/- 1 and 2 standard deviation bands act as dynamic statistical value boundaries.",
        "physical_trigger": "Price displaced to +/- 2 standard deviation VWAP band in a non-trending regime -> statistical mean-reversion opportunity back to VWAP.",
        "invalidation": "In a verified Trend Day, price rides the outer VWAP band and VWAP slope expands aggressively; mean-reversion trades are locked out.",
        "runway_behavior": "Mean-reversion moves travel cleanly from outer VWAP bands to the central session VWAP line.",
        "risk_guidance": "Do not buy at or above +2 sigma VWAP (Apex Premium, Veto 4). Do not short below -2 sigma VWAP.",
        "tags": ["ORDER_FLOW", "VWAP", "STANDARD_DEVIATION", "INSTITUTIONAL_EXECUTION", "ALGORITHMIC"]
    },

    # -------------------------------------------------------------
    # 3. WYCKOFF METHODOLOGY (Wyckoff 1930, Pruden 2007, Weis 2013)
    # -------------------------------------------------------------
    {
        "concept_id": "WYCKOFF_PHASE_C_SPRING_TURTLE_SOUP",
        "category": "WYCKOFF_METHODOLOGY",
        "title": "Wyckoff Phase C Spring & Turtle Soup Liquidity Reclaim",
        "author_citation": "Richard D. Wyckoff (1930); Hank Pruden (2007); David H. Weis (2013)",
        "core_law": "Phase C is the definitive test of remaining supply in an accumulation trading range. The Spring is a brief deliberate break below established support (Day Low / Trading Range Low) designed to trigger retail sell stops and induce breakout shorts. If supply is exhausted, price immediately snaps back inside value on heavy volume, trapping bears.",
        "physical_trigger": "External Day Low or Asian Low swept -> M5 candle closes back above the swept structural level with an absorption wick and CVD flip.",
        "invalidation": "Any sustained M15 candle close below the swept wick extreme confirms genuine breakdown and kills the Spring.",
        "runway_behavior": "Once the Spring is confirmed, price targets the upper trading range boundary (Sign of Strength SOS / Break of Structure BOS).",
        "risk_guidance": "Pattern A (100 pts Champion): Zero moving average alignment required. Entry on reclaim close; SL 1.5 pts below swept wick low.",
        "tags": ["WYCKOFF", "PHASE_C", "SPRING", "TURTLE_SOUP", "DAY_LOW_SWEEP", "SSL_SWEEP", "LIQUIDITY_SWEEP", "M5_RECLAIM", "RECLAIM"]
    },
    {
        "concept_id": "WYCKOFF_PHASE_C_UTAD_SHAKEOUT",
        "category": "WYCKOFF_METHODOLOGY",
        "title": "Wyckoff Phase C Upthrust After Distribution (UTAD)",
        "author_citation": "Richard D. Wyckoff (1930); Rubén Villahermosa (2019)",
        "core_law": "The UTAD is the mirror image of a Spring: a terminal high-volume thrust above trading range resistance (Day High / Asian High) that traps breakout buyers before smart money distributes its final inventory. Price snaps back inside the trading range, initiating the markdown phase.",
        "physical_trigger": "Day High or Asian High swept -> rapid rejection wick -> M5 candle closes back inside the Value Area with bearish CVD delta surge.",
        "invalidation": "Clean M15 structural close above the swept high confirms real kinetic breakout and aborts the UTAD.",
        "runway_behavior": "Price cascades down through the center of the trading range directly toward the Trading Range Low (Sign of Weakness SOW).",
        "risk_guidance": "Pattern A Short (100 pts Champion): Entry on verified inside close; SL placed 1.5 pts above the UTAD peak.",
        "tags": ["WYCKOFF", "PHASE_C", "UTAD", "UPTHRUST", "DISTRIBUTION", "DAY_HIGH_SWEEP", "BSL_SWEEP", "LIQUIDITY_SWEEP", "M5_RECLAIM"]
    },
    {
        "concept_id": "WYCKOFF_PHASE_A_CLIMAX_STOPPING",
        "category": "WYCKOFF_METHODOLOGY",
        "title": "Wyckoff Phase A Climactic Stopping Volume & Automatic Rally",
        "author_citation": "Richard D. Wyckoff (1930); Hank Pruden, 'Three Skills of Top Trading' (2007)",
        "core_law": "Phase A stops the prior trend through climactic action: Preliminary Support (PSY), Selling Climax (SC), and an Automatic Rally (AR). The Selling Climax features extreme tick velocity (>120 t/m), massive volume spread, and a wide-range reversal bar that establishes the lower boundary of the new trading range.",
        "physical_trigger": "Price in freefall hits extreme velocity spike (>120 t/m) -> giant volume bar absorbs selling -> immediate violent bounce (AR).",
        "invalidation": "Failure of the Automatic Rally to reach the midpoint of the prior impulse wave indicates trend continuation, not Phase A stopping.",
        "runway_behavior": "The distance between the Climax Low and the Automatic Rally High defines the initial Trading Range (TR) for Phase B cause-building.",
        "risk_guidance": "Do not chase the Climax bar directly. Wait for the Secondary Test (ST) in Phase B to enter with lower risk.",
        "tags": ["WYCKOFF", "PHASE_A", "SELLING_CLIMAX", "AUTOMATIC_RALLY", "STOPPING_VOLUME"]
    },
    {
        "concept_id": "WYCKOFF_PHASE_D_SIGN_OF_STRENGTH",
        "category": "WYCKOFF_METHODOLOGY",
        "title": "Wyckoff Phase D Sign of Strength (SOS) & Break of Structure",
        "author_citation": "Richard D. Wyckoff (1930); David H. Weis (2013)",
        "core_law": "Phase D marks the beginning of markup inside the trading range. A Sign of Strength (SOS) occurs when price breaks above intermediate resistance on expanding volume and velocity, followed by a low-volume pullback (Last Point of Support LPS / FVG retest) that holds above former resistance.",
        "physical_trigger": "Break of Structure (BOS) above intermediate pivot on high volume -> low-velocity pullback (<40 t/m) into fresh FVG shelf.",
        "invalidation": "Pullback falling completely back through the trading range midpoint indicates distribution, not markup.",
        "runway_behavior": "Phase D offers the cleanest trend runway (Pattern B FVG Retest) targeting the upper trading range boundary.",
        "risk_guidance": "Pattern B (90 pts Champion): Pre-stage Prong A resting limit at the LPS/FVG tip. Fill <= 25% priority.",
        "tags": ["WYCKOFF", "PHASE_D", "SIGN_OF_STRENGTH", "BOS", "LPS", "MARKUP"]
    },

    # -------------------------------------------------------------
    # 4. OPTIONS GEX & DEALER HEDGING (Squeezemetrics, Natenberg)
    # -------------------------------------------------------------
    {
        "concept_id": "OPTIONS_POSITIVE_GAMMA_PINNING",
        "category": "OPTIONS_GEX_VOLATILITY",
        "title": "Positive Gamma Exposure (GEX) & Market Pinning",
        "author_citation": "Squeezemetrics, 'The Implied Order Book' (2019); Sheldon Natenberg (2014)",
        "core_law": "When options market makers (dealers) are net Long Gamma, they hedge by buying dips and selling rallies (trading against the trend). This dampens realized volatility, compresses intraday trading ranges, and causes price to pin toward strikes with massive open interest as expiration approaches.",
        "physical_trigger": "High positive GEX environment + low realized volatility -> price repeatedly mean-reverts to high open-interest strike / POC.",
        "invalidation": "Sharp collapse in underlying price below major put wall flips dealer gamma from positive to negative, unleashing a volatility spike.",
        "runway_behavior": "Price action is mean-reverting; breakouts fail and turn into rotation channels.",
        "risk_guidance": "Fade range extremes back toward central POC/strike pin. BANNED from taking breakout stop orders.",
        "tags": ["OPTIONS", "GEX", "GAMMA", "PINNING", "VOLATILITY_COMPRESSION", "DEALER_HEDGING"]
    },
    {
        "concept_id": "OPTIONS_NEGATIVE_GAMMA_EXPANSION",
        "category": "OPTIONS_GEX_VOLATILITY",
        "title": "Negative Gamma Exposure (GEX) & Volatility Cascades",
        "author_citation": "Squeezemetrics (2019); Colin Bennett, 'Trading Volatility' (2014)",
        "core_law": "When options dealers are net Short Gamma, their dynamic delta-hedging requires them to sell as the market falls and buy as the market rises (trading with the trend). This amplifies market momentum, creates aggressive liquidity air pockets, and fuels rapid trend cascades.",
        "physical_trigger": "Market breaks through key gamma flip line into negative GEX territory -> tick velocity surges >100 t/m with wide candle spreads.",
        "invalidation": "Price reclaiming the gamma flip level and stabilizing inside high open interest strikes.",
        "runway_behavior": "Price moves with high kinetic velocity through air pockets directly toward the next major strike wall.",
        "risk_guidance": "Pattern C Kinetic Breakout authorized. STRICTLY PROHIBITED from fading the trend or catching falling knives.",
        "tags": ["OPTIONS", "GEX", "NEGATIVE_GAMMA", "VOLATILITY_EXPANSION", "CASCADE", "HEDGING"]
    },
    {
        "concept_id": "OPTIONS_VANNA_CHARM_FLOWS",
        "category": "OPTIONS_GEX_VOLATILITY",
        "title": "Vanna & Charm Options Greeks Hedging Flows",
        "author_citation": "Colin Bennett, 'Trading Volatility' (2014); CBOE Insights",
        "core_law": "Vanna measures delta sensitivity to changes in Implied Volatility (IV); Charm (delta bleed) measures delta sensitivity to the passage of time. As expiration approaches or IV drops, dealers must mechanically buy or sell underlying futures to rebalance delta hedges, generating predictable late-day directional flows.",
        "physical_trigger": "OPEX days (Options Expiration) or post-event volatility crush (e.g. post-CPI/FOMC) where falling IV triggers programmatic dealer buying.",
        "invalidation": "Fresh breaking macro shock that spikes IV higher interrupts the Vanna flow.",
        "runway_behavior": "Smooth, continuous directional grind during late New York hours with low tick velocity but persistent delta bias.",
        "risk_guidance": "Align trade direction with the macro Vanna flow. Avoid shorting into post-announcement volatility crush.",
        "tags": ["OPTIONS", "VANNA", "CHARM", "VOLATILITY_CRUSH", "OPEX", "DEALER_FLOWS"]
    },

    # -------------------------------------------------------------
    # 5. MACRO FIXED INCOME & REAL YIELDS (FRED, BIS, Dalton)
    # -------------------------------------------------------------
    {
        "concept_id": "MACRO_REAL_YIELD_GRAVITY",
        "category": "MACRO_FIXED_INCOME_YIELDS",
        "title": "US 10-Year Real Yield (DFII10) Inverse Gravity on Gold",
        "author_citation": "Federal Reserve Economic Data (FRED); World Gold Council Research",
        "core_law": "US 10-Year Real Yields (DFII10 / TIPS) represent the risk-free return of holding cash after accounting for inflation. Because physical gold pays zero yield, rising real yields increase the opportunity cost of holding bullion (bearish headwind), while falling real yields eliminate the penalty of holding gold and unleash massive upward monetary repricing.",
        "physical_trigger": "FRED DFII10 trending down or dropping >3-5 basis points intraday = strong bullish gold tailwind. Rising DFII10 = bearish headwind.",
        "invalidation": "Extreme geopolitical flight-to-safety shock or sovereign debt crisis can temporarily decouple gold from real yields.",
        "runway_behavior": "Real yields establish the macro runway: trade technical setups that align with the real yield drift.",
        "risk_guidance": "Gold price action and physical order flow possess absolute supremacy over lagging macroeconomic models. Do not use lagging macro yields to fade live structural order flow or multi-timeframe trend expansions.",
        "tags": ["MACRO", "REAL_YIELDS", "DFII10", "TIPS", "INFLATION", "BULLION_GRAVITY"]
    },
    {
        "concept_id": "MACRO_NET_USD_LIQUIDITY",
        "category": "MACRO_FIXED_INCOME_YIELDS",
        "title": "Net USD Liquidity (Fed Balance Sheet - TGA - RRP)",
        "author_citation": "Bank for International Settlements (BIS); Federal Reserve H.4.1 Balance Sheet",
        "core_law": "Net Dollar Liquidity = Fed Total Assets minus Treasury General Account (TGA) minus Reverse Repo Facility (RRP). Expansions in net liquidity increase systemic dollar supply, driving currency debasement and secular bull markets in gold and hard commodities.",
        "physical_trigger": "RRP facility draining or Treasury General Account spending cash into the commercial banking system.",
        "invalidation": "Fed quantitative tightening (QT) accelerating alongside Treasury debt issuance draining bank reserves.",
        "runway_behavior": "Provides macro regime permission for multi-week and multi-session swing expansions.",
        "risk_guidance": "In expanding net liquidity regimes, prioritize buying structural discount pullbacks over taking tactical shorts.",
        "tags": ["MACRO", "NET_LIQUIDITY", "FEDERAL_RESERVE", "TGA", "RRP", "DEBASEMENT"]
    },
    {
        "concept_id": "MACRO_COT_SMART_MONEY_POSITIONING",
        "category": "MACRO_FIXED_INCOME_YIELDS",
        "title": "CFTC Commitments of Traders (COT) Smart Money Percentile",
        "author_citation": "U.S. Commodity Futures Trading Commission (CFTC); Schwager, 'Market Wizards'",
        "core_law": "The COT Disaggregated report reveals the net positioning of Commercial hedgers (smart money producers/users) versus Non-Commercial speculators (managed money / hedge funds). COT Money-Manager positioning at 26-week extremes (>85th percentile) indicates strong institutional accumulation; extremes <15th percentile indicate liquidation exhaustion.",
        "physical_trigger": "26-week Money-Manager percentile >80% confirms macro institutional accumulation backing long setups.",
        "invalidation": "Large weekly speculative liquidation (>15,000 contracts) signals smart money profit-taking.",
        "runway_behavior": "High COT percentiles provide institutional fuel that supports buying deep discount retracements.",
        "risk_guidance": "Cross-reference COT with technical 4TF structure. If COT is 85th percentile bullish but 4TF is bearish, flag REGIME DIVERGENCE and stand flat.",
        "tags": ["MACRO", "COT", "CFTC", "SMART_MONEY", "MANAGED_MONEY", "POSITIONING"]
    },

    # -------------------------------------------------------------
    # 6. QUANTITATIVE & PORTFOLIO MATHEMATICS (López de Prado, Taleb)
    # -------------------------------------------------------------
    {
        "concept_id": "QUANT_TRIPLE_BARRIER_METHOD",
        "category": "QUANT_RISK_PORTFOLIO_MATH",
        "title": "Triple-Barrier Labeling & Execution Gating",
        "author_citation": "Marcos López de Prado, 'Advances in Financial Machine Learning' (2018)",
        "core_law": "Every trade execution must be evaluated across three deterministic barriers: (1) Upper Profit Taking Barrier (Mode A TP), (2) Lower Stop Loss Barrier (Structural SL floor), and (3) Maximum Time Horizon Barrier (Holding duration expiration). Trades that fail to touch either price barrier before time expiration must be audited for stagnation.",
        "physical_trigger": "Order fill establishes the 3 barriers simultaneously: TP (4.0-8.0 pts), SL (6.0-10.0 pts), and Time Barrier (20-min stagnation audit).",
        "invalidation": "Adverse structural break before time barrier triggers emergency exit rule.",
        "runway_behavior": "Once inside the barrier envelope, let the broker execute SL or TP without premature retail tampering.",
        "risk_guidance": "Champion Hold Mandate: Zero early scratches before the barrier triggers unless Tier-1 emergency news arrives.",
        "tags": ["QUANT", "TRIPLE_BARRIER", "LOPEZ_DE_PRADO", "RISK_MANAGEMENT", "EXIT_DISCIPLINE"]
    },
    {
        "concept_id": "QUANT_CONVEX_PAYOFF_ANTIFRAGILE",
        "category": "QUANT_RISK_PORTFOLIO_MATH",
        "title": "Convex Payoff Architecture & Antifragile Position Sizing",
        "author_citation": "Nassim Nicholas Taleb, 'Antifragile: Things That Gain from Disorder' (2012); Ralph Vince (1990)",
        "core_law": "A viable long-term quantitative edge requires positive convexity: strictly bounded, non-negotiable downside risk paired with asymmetric upside capture. Taking many small, controlled structural losses while allowing winning expansions to reach structural targets ensures antifragility in volatile markets.",
        "physical_trigger": "Risk-to-reward ratio MUST equal or exceed 1:1.5 to 1:2.0 based on structural runway clearance.",
        "invalidation": "Any setup requiring an SL larger than the available structural runway to opposing liquidity violates positive convexity.",
        "runway_behavior": "Asymmetric setups travel across open roadways with >= 6.0 pts clearance to opposing major pivots.",
        "risk_guidance": "Const_SL_Floor and Const_Max_Lots are Tier-1 immutable constitutional laws protecting positive convexity.",
        "tags": ["QUANT", "CONVEXITY", "ANTIFRAGILE", "TALEB", "POSITION_SIZING", "ASYMMETRY"]
    },
    {
        "concept_id": "QUANT_INFORMATION_RATIO_EDGE",
        "category": "QUANT_RISK_PORTFOLIO_MATH",
        "title": "The Fundamental Law of Active Management & Information Ratio",
        "author_citation": "Richard Grinold and Ronald Kahn, 'Active Portfolio Management' (2000)",
        "core_law": "Information Ratio (IR) = Information Coefficient (IC) * sqrt(Breadth). An active trader's edge depends not on being right 90% of the time on single trades, but on applying a statistically consistent, disciplined rule set across multiple independent, high-conviction decision nodes.",
        "physical_trigger": "Executing Champion setups (85-100 pts) with exact consistency whenever 100% of confluence gates align.",
        "invalidation": "Inconsistent discretionary execution, emotional rule-breaking, and skipping valid setups degrade breadth and destroy IR.",
        "runway_behavior": "Statistical edge compounds smoothly over cohorts of 30-50 disciplined executions.",
        "risk_guidance": "Autonomous execution authorized ONLY when objective gates align. Standing flat in ambiguity is an essential part of maintaining high IR.",
        "tags": ["QUANT", "INFORMATION_RATIO", "GRINOLD_KAHN", "BREADTH", "STATISTICAL_EDGE"]
    }
]
