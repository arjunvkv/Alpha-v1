# master_literature_corpus.py - Foundational Theorems of Global Trading Literature
# Codified for the Total O.C.E.A.N. Cognitive Node Globe (NNG 2.0)

MASTER_LITERATURE = {
    'AUCTION_MARKET_THEORY': {
        'authors': ['James F. Dalton', 'J. Peter Steidlmayer', 'Eric T. Jones'],
        'texts': ['Mind Over Markets (1990)', 'Markets in Profile (2007)', 'Steidlmayer on Markets (1989)'],
        'theorems': {
            'AUCTION_PURPOSE': 'Markets exist solely to facilitate 2-way trade and discover price levels that maximize volume.',
            'THREE_VARIABLES': 'Price advertises opportunity, Time regulates opportunity, Volume measures success or failure of the auction.',
            'VALUE_AREA_70': '70% of total volume occurs within 1 standard deviation of the Point of Control (POC). Prices outside VA are premium or discount.',
            'DALTON_80_RULE': 'If price trades outside previous Value Area and prints 2 consecutive 15-min closes back INSIDE the Value Area, there is an 80% statistical probability of traversing to the opposite Value Area boundary.',
            'EXCESS_REJECTION': 'Tails (single-print wicks) at Value Area extremes signify swift institutional rejection of unfair prices.'
        }
    },
    'ORDER_FLOW_MICROSTRUCTURE': {
        'authors': ['Jean-Philippe Bouchaud', 'Larry Harris', 'Joel Hasbrouck'],
        'texts': ['Trades, Quotes and Prices (2018)', 'Trading and Exchanges (2003)', 'Empirical Market Microstructure (2007)'],
        'theorems': {
            'SQUARE_ROOT_IMPACT': 'Market impact of institutional volume follows a universal square-root law (Impact proportional to sqrt(Volume)). Large orders must be split or absorbed passively.',
            'LIMIT_ORDER_ABSORPTION': 'When aggressive market orders (high tick velocity) fail to displace price at a key boundary, passive institutional limit orders are absorbing the flow.',
            'CVD_DELTA_POLARITY': 'CVD Delta = Aggressive Buyer Volume (Ask) - Aggressive Seller Volume (Bid). Divergence between Delta and Price highlights institutional absorption.',
            'TOXIC_FLOW_AND_SPREAD': 'High velocity one-sided flow widens bid-ask spreads; market orders suffer adverse selection and negative slippage.'
        }
    },
    'SMART_MONEY_PD_ARRAYS': {
        'authors': ['Michael J. Huddleston', 'Inner Circle Trader (ICT)'],
        'texts': ['ICT Market Maker Primer', 'PD Array Matrix & Price Delivery Delivery Model'],
        'theorems': {
            'FAIR_VALUE_GAP': 'A 3-candle imbalance where Candle 1 and Candle 3 wicks do not overlap creates a price void that institutional algorithms rebalance.',
            'CONSEQUENT_ENCROACHMENT_50': 'The exact 50% midpoint of an FVG or Order Block is the primary institutional equilibrium rebalance anchor.',
            'LIQUIDITY_SWEEP': 'Smart money engineers counterparty liquidity by sweeping recognizable swing highs/lows (retail buy/sell stops) before reversing price into internal imbalances.',
            'INVERSION_FVG': 'When a validated FVG is violated with displacement, its polarity flips (Bullish FVG becomes Bearish Resistance).'
        }
    },
    'MACRO_INTERMARKET': {
        'authors': ['John J. Murphy', 'Joseph Wang', 'Gabriel Burstein'],
        'texts': ['Intermarket Analysis (2004)', 'Central Banking 101 (2020)', 'Macro Trading and Investment Strategies (1999)'],
        'theorems': {
            'GOLD_REAL_YIELD_BETA': 'Gold exhibits a -0.85 empirical inverse correlation to US 10-Year Real Yields (TIPS). Rising real yields increase the opportunity cost of holding non-yielding bullion.',
            'FOUR_PHASE_NEWS_LIFECYCLE': 'News catalysts follow: Phase 1 (Compression) -> Phase 2 (Impulse Shock) -> Phase 3 (Exhaustion & Pricing-In) -> Phase 4 (True Trend). Stale news in Phase 3 is ignored.',
            'DXY_DENOMINATOR_PRESSURE': 'US Dollar Index strength applies direct mechanical downward valuation pressure on spot commodities priced in USD.'
        }
    },
    'ASSET_POSITIONING_COT': {
        'authors': ['Stephen Briese', 'Jamie Saettele'],
        'texts': ['The Commitments of Traders Bible (2008)', 'Sentiment in the Forex Market (2008)'],
        'theorems': {
            'COT_100TH_PERCENTILE_TRAP': 'When Managed Money (Speculators) reach 100th percentile net-long extremes, buying power is exhausted and Commercials are heavily short, preconditioning a sharp liquidation cascade.',
            'COMMERCIAL_INSIDER_ALIGNMENT': 'Commercial bullion banks are smart-money producers and hedgers; trading aligned with Commercial positioning yields superior risk-adjusted returns.'
        }
    },
    'QUANTITATIVE_RISK_EXPECTANCY': {
        'authors': ['Ralph Vince', 'Ernie Chan', 'David Aronson'],
        'texts': ['The Mathematics of Money Management (1992)', 'Quantitative Trading (2008)', 'Evidence-Based Technical Analysis (2006)'],
        'theorems': {
            'MATHEMATICAL_EXPECTANCY': 'Expected Value E[V] = (P_win * R_win) - (P_loss * R_loss). Trades must have positive expectancy and R:R >= 2.5:1.',
            'ASYMMETRIC_PAYOUT': 'Resting limit orders placed at structural boundaries with tight invalidation SL create mathematically superior payoff profiles.'
        }
    }
}
