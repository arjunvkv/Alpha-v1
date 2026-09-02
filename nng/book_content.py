# nng/book_content.py - Master Authored Content for the Knowledge Book (NNG 2.0)
# -*- coding: utf-8 -*-
# Content: Tools, Usages (FOR/MUST-NOT), Conditions, Synergies, Invalidations, Literature

TOOLS_CATALOG = {
    'CVD_DELTA': {
        'name': 'Cumulative Volume Delta (CVD)',
        'type': 'MICROSTRUCTURE',
        'for_rules': [
            'Order flow volume delta analysis',
            'Detecting passive institutional limit order absorption',
            'Spotting delta divergence at structural boundaries'
        ],
        'must_not_rules': [
            'MUST NOT use as a standalone trend filter',
            'MUST NOT treat as a lagging indicator',
            'MUST NOT chase market orders into divergent delta'
        ],
        'applies_to': ['ABSORPTION_REGIME', 'LIQUIDITY_SWEEP_REGIME'],
        'literature': 'Jean-Philippe Bouchaud & Larry Harris'
    },
    'FVG_MATRIX': {
        'name': 'Fair Value Gap (FVG) Matrix',
        'type': 'SMART_MONEY_GEOMETRY',
        'for_rules': [
            'Locating structural imbalance boundaries',
            '50% Consequent Encroachment (CE) exact limit order entry pricing',
            'Identifying virgin liquidity pools (<30% fill rate)'
        ],
        'must_not_rules': [
            'MUST NOT use as a momentum gauge',
            'MUST NOT enter trades inside exhausted FVGs (>60% fill)',
            'MUST NOT place orders in mid-range chop without an FVG anchor'
        ],
        'applies_to': ['FVG_CE_RETEST_REGIME', 'BREAKOUT_DISPLACEMENT_REGIME'],
        'literature': 'Michael J. Huddleston (ICT)'
    },
    'VOLUME_PROFILE': {
        'name': 'Volume Profile & Market Profile (POC/VAH/VAL)',
        'type': 'AUCTION_DYNAMICS',
        'for_rules': [
            'Mapping 70% Value Area boundaries (VAH/VAL)',
            'Trading Dalton 80% Rule rotations across the Value Area',
            'Point of Control (POC) high-volume gravitational targeting'
        ],
        'must_not_rules': [
            'MUST NOT use for momentum breakout trading inside the Value Area',
            'MUST NOT ignore buying/selling excess tails at extremes'
        ],
        'applies_to': ['VALUE_AREA_ROTATION_REGIME', 'COMPRESSED_CHOP_REGIME'],
        'literature': 'James F. Dalton & J. Peter Steidlmayer'
    },
    'EMA_20_50': {
        'name': 'Multi-Timeframe Exponential Moving Averages (EMA 20/50)',
        'type': 'TREND_REGIME',
        'for_rules': [
            'Assessing macro trend direction and dynamic structural slope',
            'Identifying dynamic support/resistance pullbacks in strong trends'
        ],
        'must_not_rules': [
            'MUST NOT use for precise tick entry timing',
            'MUST NOT fight H4/H1 EMA alignment without confirmed Phase 3 macro exhaustion'
        ],
        'applies_to': ['TREND_CONTINUATION_REGIME'],
        'literature': 'John J. Murphy (Intermarket Analysis)'
    },
    'RSI_MOMENTUM': {
        'name': 'Relative Strength Index (RSI)',
        'type': 'MOMENTUM_EXHAUSTION',
        'for_rules': [
            'Detecting overbought (>70) and oversold (<30) exhaustion zones',
            'Spotting multi-timeframe regular and hidden divergences'
        ],
        'must_not_rules': [
            'MUST NOT execute standalone trades on RSI crosses alone',
            'MUST NOT short strong trend continuation just because RSI is overbought'
        ],
        'applies_to': ['STATISTICAL_EXHAUSTION_REGIME', 'ABSORPTION_REGIME'],
        'literature': 'J. Welles Wilder'
    },
    'TICK_VELOCITY': {
        'name': 'Tick Velocity (tpm)',
        'type': 'MICROSTRUCTURE_SPEED',
        'for_rules': [
            'Measuring tape acceleration and liquidity arrival rates',
            'Selecting between resting limit orders (Burst >120 t/m) vs patient staging'
        ],
        'must_not_rules': [
            'MUST NOT use as a directional indicator',
            'MUST NOT place market orders during high velocity spikes (slippage hazard)'
        ],
        'applies_to': ['LIQUIDITY_SWEEP_REGIME', 'NEWS_SHOCK_REGIME'],
        'literature': 'Jean-Philippe Bouchaud'
    },
    'COT_REPORT': {
        'name': 'CFTC Commitments of Traders (COT)',
        'type': 'ASSET_POSITIONING',
        'for_rules': [
            'Tracking Commercial Hedgers smart money positioning',
            'Identifying 100th percentile speculative crowding liquidation traps'
        ],
        'must_not_rules': [
            'MUST NOT use for intraday trade timing or scalping',
            'MUST NOT trade against extreme Commercial positioning'
        ],
        'applies_to': ['COT_CROWDING_REGIME'],
        'literature': 'Stephen Briese (The Commitments of Traders Bible)'
    },
    'REAL_YIELDS_TIPS': {
        'name': 'US 10-Year Real Yields (TIPS)',
        'type': 'MACRO_VALUATION',
        'for_rules': [
            'Tracking real cost of capital and Gold -0.85 inverse beta',
            'Filtering macro tailwinds vs headwinds'
        ],
        'must_not_rules': [
            'MUST NOT execute immediate market trades on nominal yield ticks without real yield spread confirmation'
        ],
        'applies_to': ['MACRO_TREND_REGIME'],
        'literature': 'Joseph Wang & John J. Murphy'
    }
}

CONDITIONS_CATALOG = {
    'ABSORPTION_REGIME': {
        'name': 'Passive Institutional Absorption at Boundary',
        'description': 'Aggressive market orders (high CVD) fail to displace price at a key FVG CE or Value Area extreme.',
        'mandatory_tools': ['CVD_DELTA', 'TICK_VELOCITY', 'FVG_MATRIX'],
        'noise_to_ignore': ['Lagging MACD', '1-minute Stochastic wiggles'],
        'action_blueprint': 'Stage resting limit order at FVG 50% CE. Invalidation SL beyond absorption wick.'
    },
    'VALUE_AREA_ROTATION_REGIME': {
        'name': 'Dalton 80% Rule Value Area Rotation',
        'description': 'Price returns inside Value Area with 2 consecutive 15-min closes after trading outside.',
        'mandatory_tools': ['VOLUME_PROFILE', 'EMA_20_50'],
        'noise_to_ignore': ['Micro wicks', 'Intraday news noise'],
        'action_blueprint': 'Execute or limit order at Value Area boundary targeting opposite VA level (VAH to VAL or VAL to VAH).'
    },
    'TREND_CONTINUATION_REGIME': {
        'name': 'Structural Trend BOS Continuation',
        'description': 'High volume displacement candle breaks swing structure leaving fresh FVG in trend direction.',
        'mandatory_tools': ['EMA_20_50', 'FVG_MATRIX', 'CVD_DELTA'],
        'noise_to_ignore': ['Overbought/Oversold RSI (trend overrides RSI)'],
        'action_blueprint': 'Resting limit order at newly formed FVG 50% CE pullback.'
    },
    'COT_CROWDING_REGIME': {
        'name': '100th Percentile Speculative Crowding Squeeze',
        'description': 'Non-commercials at 52-week net-long extreme with Commercials heavily short.',
        'mandatory_tools': ['COT_REPORT', 'FVG_MATRIX', 'REAL_YIELDS_TIPS'],
        'noise_to_ignore': ['Bullish retail headlines'],
        'action_blueprint': 'High-conviction short staging upon first M15/H1 structural CHoCH.'
    },
    'COMPRESSED_CHOP_REGIME': {
        'name': 'Compressed Mid-Range Value Area Chop',
        'description': 'Low velocity (<40 t/m), price floating near POC inside Value Area.',
        'mandatory_tools': ['VOLUME_PROFILE', 'FVG_MATRIX'],
        'noise_to_ignore': ['All micro signals inside the middle'],
        'action_blueprint': 'STAND FLAT inside the middle or stage dual resting brackets at extreme boundaries (VAH & VAL).'
    }
}

SYNERGIES_CATALOG = [
    {'source': 'CVD_DELTA', 'target': 'TICK_VELOCITY', 'relation': 'CONFIRMS', 'desc': 'High velocity with negative delta confirms aggressive sell absorption.'},
    {'source': 'CVD_DELTA', 'target': 'FVG_MATRIX', 'relation': 'CONFIRMS', 'desc': 'Absorption delta at 50% CE confirms institutional limit defense.'},
    {'source': 'VOLUME_PROFILE', 'target': 'FVG_MATRIX', 'relation': 'CONFIRMS', 'desc': 'FVG CE aligned with VAH/VAL creates highest conviction anchor.'},
    {'source': 'COT_REPORT', 'target': 'REAL_YIELDS_TIPS', 'relation': 'CONFIRMS', 'desc': 'Rising real yields + 100th percentile COT longs = asymmetric short thesis.'},
    {'source': 'RSI_MOMENTUM', 'target': 'EMA_20_50', 'relation': 'CONFLICTS_WITH', 'desc': 'Do not use RSI overbought to fade an active EMA20/50 trend impulse.'}
]
