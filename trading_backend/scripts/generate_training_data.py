import json
import os
import random
from typing import List, Dict, Tuple
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_technical_patterns(language: str = 'english') -> List[Dict[str, str]]:
    """Generate training data for technical patterns."""
    if language == 'english':
        patterns = [
            # Bullish patterns with volume and price action
            ("Strong breakout above resistance with increasing volume and institutional buying", "bullish"),
            ("Golden cross forming on daily timeframe with volume confirmation and price follow-through", "bullish"),
            ("Multiple bullish divergences on RSI and MACD with increasing buy pressure", "bullish"),
            ("Accumulation phase with institutional buying pressure and decreasing selling volume", "bullish"),
            ("Higher highs and higher lows forming clear uptrend with strong volume support", "bullish"),
            ("Double bottom pattern confirmed with volume spike and institutional accumulation", "bullish"),
            ("Inverse head and shoulders pattern completion with volume confirmation", "bullish"),
            ("Strong support level holding with increasing buy orders and institutional interest", "bullish"),
            ("Bullish engulfing pattern with volume confirmation and follow-through", "bullish"),
            ("Moving averages showing strong upward momentum with institutional buying", "bullish"),
            ("RSI showing oversold conditions with positive divergence and volume support", "bullish"),
            ("Accumulation occurring at key support levels with increasing buy volume", "bullish"),
            ("Breakout from bull flag pattern with strong volume confirmation", "bullish"),
            ("Cup and handle formation completing with institutional buying support", "bullish"),
            ("Ascending triangle breakout with increasing volume and momentum", "bullish"),

            # Bearish patterns with volume and price action
            ("Death cross confirmed on daily chart with increasing selling pressure", "bearish"),
            ("Lower lows continuing as support breaks down with heavy volume", "bearish"),
            ("Distribution pattern emerging at resistance with institutional selling", "bearish"),
            ("Head and shoulders pattern forming with declining volume and support break", "bearish"),
            ("Double top pattern with heavy selling pressure and volume confirmation", "bearish"),
            ("Bearish divergence on multiple timeframes with decreasing buy volume", "bearish"),
            ("Breaking down below major support levels with increasing sell volume", "bearish"),
            ("Declining volume in upward moves with institutional distribution", "bearish"),
            ("Multiple technical indicators showing overbought with bearish divergence", "bearish"),
            ("Moving averages crossing downward with strong selling momentum", "bearish"),
            ("RSI showing overbought conditions with negative divergence", "bearish"),
            ("Distribution occurring at resistance with increasing sell orders", "bearish"),
            ("Breakdown from bear flag pattern with volume confirmation", "bearish"),
            ("Rising wedge pattern breaking down with increasing volume", "bearish"),
            ("Descending triangle breakdown with heavy selling pressure", "bearish"),

            # Neutral patterns with volume analysis
            ("Price consolidating in tight range with decreasing volume", "neutral"),
            ("Sideways trading with balanced buying and selling pressure", "neutral"),
            ("No clear trend direction on multiple timeframes with average volume", "neutral"),
            ("Equal highs and lows in ranging market with declining volume", "neutral"),
            ("Volume declining in consolidation phase with no clear direction", "neutral"),
            ("Price action trapped between support and resistance with neutral volume", "neutral"),
            ("Moving averages flattening in sideways market with average volume", "neutral"),
            ("Balanced order book with no clear directional bias", "neutral"),
            ("Technical indicators showing mixed signals with normal volume", "neutral"),
            ("Low volatility period with no breakout signals and declining volume", "neutral"),
            ("Doji patterns forming with decreasing volume in range", "neutral"),
            ("Price hovering around major moving averages with indecision", "neutral"),
            ("Symmetrical triangle formation with declining volume", "neutral"),
            ("No clear institutional buying or selling pressure", "neutral"),
            ("Market makers maintaining price in trading range", "neutral")
        ]
    else:  # Chinese patterns
        patterns = [
            # Bullish patterns
            ("突破重要阻力位，成交量显著放大，机构持续买入", "bullish"),
            ("日线图形成金叉，成交量配合，价格突破确认", "bullish"),
            ("RSI和MACD出现多重底背离，买盘压力增加", "bullish"),
            ("机构持续买入，积累阶段明显，卖盘减少", "bullish"),
            ("持续创造更高高点和更高低点，成交量支撑", "bullish"),
            ("双底形态确认，成交量突破，机构参与", "bullish"),
            ("倒头肩形态完成确认，成交量配合", "bullish"),
            ("强劲支撑位获得买单支撑，机构兴趣增加", "bullish"),
            ("多方吞没形态，成交量确认，后续走强", "bullish"),
            ("均线系统显示强劲上升动能，机构买入", "bullish"),
            ("RSI超卖区域出现正背离，成交量支撑", "bullish"),
            ("关键支撑位出现积累，买盘增加", "bullish"),
            ("牛旗形态突破，成交量确认", "bullish"),
            ("杯柄形态完成，机构支撑明显", "bullish"),
            ("上升三角突破，成交量动能增强", "bullish"),

            # Bearish patterns
            ("日线图死叉确认，卖压持续增加", "bearish"),
            ("持续创新低，支撑位失守，成交量放大", "bearish"),
            ("阻力位出现分销形态，机构抛售", "bearish"),
            ("头肩顶形态，成交量萎缩，支撑破位", "bearish"),
            ("双顶形态，卖压沉重，成交确认", "bearish"),
            ("多个时间周期出现顶背离，买盘减少", "bearish"),
            ("跌破主要支撑位，成交量放大", "bearish"),
            ("上涨成交量持续萎缩，机构分销", "bearish"),
            ("技术指标显示超买，顶背离明显", "bearish"),
            ("均线系统下行交叉，卖盘动能强", "bearish"),
            ("RSI超买区域出现负背离", "bearish"),
            ("阻力位出现分销，卖单增加", "bearish"),
            ("空头旗形突破，成交确认", "bearish"),
            ("上升楔形下破，成交量增加", "bearish"),
            ("下降三角突破，抛压沉重", "bearish"),

            # Neutral patterns
            ("价格在狭窄区间整理，成交量减少", "neutral"),
            ("横盘交易，买卖压力平衡", "neutral"),
            ("多个时间周期无明确趋势，成交量平均", "neutral"),
            ("区间交易高点低点相等，成交清淡", "neutral"),
            ("盘整阶段成交量萎缩，方向不明", "neutral"),
            ("价格在支撑阻力间震荡，成交中性", "neutral"),
            ("均线系统趋于平缓，成交量一般", "neutral"),
            ("买卖盘口均衡，无明显偏向", "neutral"),
            ("技术指标显示混合信号，成交正常", "neutral"),
            ("低波动无突破信号，成交量递减", "neutral"),
            ("十字星形态，成交量区间内减少", "neutral"),
            ("价格在主要均线附近徘徊，不确定", "neutral"),
            ("对称三角形态，成交量递减", "neutral"),
            ("无明显机构买卖压力", "neutral"),
            ("做市商维持价格区间交易", "neutral")
        ]

    return [{"text": text, "label": label} for text, label in patterns]

def generate_market_context(language: str = 'english') -> List[Dict[str, str]]:
    """Generate training data for market context."""
    if language == 'english':
        contexts = [
            # Bullish contexts
            ("Institutional investors increasing Bitcoin holdings significantly with strong accumulation", "bullish"),
            ("Strong market fundamentals with growing adoption and institutional interest", "bullish"),
            ("Positive regulatory developments boosting market confidence and institutional participation", "bullish"),
            ("Major companies adding crypto to balance sheets with long-term holding strategy", "bullish"),
            ("Retail interest surging with positive sentiment and increasing wallet addresses", "bullish"),
            ("Network metrics showing strong accumulation by long-term holders", "bullish"),
            ("Exchange outflows increasing as investors move to cold storage", "bullish"),
            ("Mining hash rate reaching new highs with strong network security", "bullish"),
            ("Institutional derivatives showing increasing long positions", "bullish"),
            ("Technical upgrades improving network scalability and adoption", "bullish"),

            # Bearish contexts
            ("Large miners selling Bitcoin holdings amid market uncertainty", "bearish"),
            ("Regulatory crackdown causing market uncertainty and institutional exits", "bearish"),
            ("Institutional outflows from crypto funds accelerating", "bearish"),
            ("Market sentiment shifts bearish on macro concerns and rate hikes", "bearish"),
            ("Whale addresses decreasing their positions with heavy distribution", "bearish"),
            ("Network activity declining with decreasing transaction volume", "bearish"),
            ("Exchange inflows increasing as holders prepare to sell", "bearish"),
            ("Mining difficulty dropping due to miner capitulation", "bearish"),
            ("Derivatives showing increasing short interest", "bearish"),
            ("Technical vulnerabilities discovered in major protocols", "bearish"),

            # Neutral contexts
            ("Market awaiting key economic data with balanced positions", "neutral"),
            ("Mixed signals from different market indicators and timeframes", "neutral"),
            ("Balanced institutional flows in crypto markets with no clear direction", "neutral"),
            ("Regulatory landscape remains unclear with ongoing discussions", "neutral"),
            ("Trading volume average with no clear directional bias", "neutral"),
            ("Network metrics showing stable activity levels", "neutral"),
            ("Balance between exchange inflows and outflows", "neutral"),
            ("Mining hash rate stabilizing at current levels", "neutral"),
            ("Derivatives showing balanced long-short ratio", "neutral"),
            ("Technical development proceeding as scheduled", "neutral")
        ]
    else:  # Chinese contexts
        contexts = [
            # Bullish contexts
            ("机构投资者大幅增持比特币，积累明显加强", "bullish"),
            ("市场基本面强劲，采用率持续增长，机构兴趣浓厚", "bullish"),
            ("监管政策利好提振市场信心，机构参与度提升", "bullish"),
            ("大型企业将加密货币纳入资产负债表，长期持有策略", "bullish"),
            ("散户兴趣激增，市场情绪积极，钱包地址增加", "bullish"),
            ("网络指标显示长期持有者强势积累", "bullish"),
            ("交易所流出量增加，投资者转向冷储存", "bullish"),
            ("挖矿算力创新高，网络安全性增强", "bullish"),
            ("机构衍生品市场看多仓位增加", "bullish"),
            ("技术升级改善网络扩展性和采用率", "bullish"),

            # Bearish contexts
            ("大型矿工抛售比特币持仓，市场不确定性增加", "bearish"),
            ("监管收紧引发市场不确定性，机构撤离", "bearish"),
            ("机构资金持续流出加密货币基金，速度加快", "bearish"),
            ("宏观担忧和加息导致市场情绪转向悲观", "bearish"),
            ("鲸鱼地址减少持仓，大量分销迹象", "bearish"),
            ("网络活动下降，交易量减少", "bearish"),
            ("交易所流入量增加，持有者准备抛售", "bearish"),
            ("矿工投降导致挖矿难度下降", "bearish"),
            ("衍生品市场空头兴趣增加", "bearish"),
            ("主要协议发现技术漏洞", "bearish"),

            # Neutral contexts
            ("市场等待关键经济数据，仓位平衡", "neutral"),
            ("不同市场指标和时间周期显示混合信号", "neutral"),
            ("机构资金流向趋于平衡，无明确方向", "neutral"),
            ("监管环境仍不明朗，讨论持续进行", "neutral"),
            ("成交量平平，无明确方向偏好", "neutral"),
            ("网络指标显示活动水平稳定", "neutral"),
            ("交易所流入流出量保持平衡", "neutral"),
            ("挖矿算力在当前水平稳定", "neutral"),
            ("衍生品市场多空比例平衡", "neutral"),
            ("技术开发按计划进行中", "neutral")
        ]

    return [{"text": text, "label": label} for text, label in contexts]

def generate_combined_patterns(language: str = 'english') -> List[Dict[str, str]]:
    """Generate training data combining technical and fundamental analysis."""
    if language == 'english':
        patterns = [
            # Complex bullish patterns
            ("Golden cross forming with institutional buying and positive regulatory news", "bullish"),
            ("Strong support holding with increasing network adoption and whale accumulation", "bullish"),
            ("Multiple bullish divergences with growing institutional interest", "bullish"),
            ("Breaking resistance with positive regulatory developments and volume", "bullish"),
            ("Accumulation phase with improving network metrics and institutional buying", "bullish"),

            # Complex bearish patterns
            ("Death cross confirmed with regulatory uncertainty and miner selling", "bearish"),
            ("Support breakdown with increasing exchange inflows and whale distribution", "bearish"),
            ("Multiple bearish divergences with declining network activity", "bearish"),
            ("Distribution pattern with regulatory concerns and institutional outflows", "bearish"),
            ("Breaking down with technical vulnerabilities and increasing shorts", "bearish"),

            # Complex neutral patterns
            ("Consolidation with mixed regulatory signals and balanced flows", "neutral"),
            ("Range-bound trading with stable network metrics", "neutral"),
            ("Technical consolidation with balanced institutional activity", "neutral"),
            ("Sideways movement with unclear regulatory direction", "neutral"),
            ("Price action trapped with mixed market signals", "neutral")
        ]
    else:  # Chinese patterns
        patterns = [
            # Complex bullish patterns
            ("金叉形成，机构买入，监管消息利好", "bullish"),
            ("强支撑确认，网络采用率提升，大户积累", "bullish"),
            ("多重底背离，机构兴趣增加", "bullish"),
            ("突破阻力位，监管政策向好，成交放量", "bullish"),
            ("积累阶段，网络指标改善，机构买入", "bullish"),

            # Complex bearish patterns
            ("死叉确认，监管不确定，矿工抛售", "bearish"),
            ("支撑破位，交易所流入增加，大户分销", "bearish"),
            ("多重顶背离，网络活动下降", "bearish"),
            ("分销形态，监管担忧，机构流出", "bearish"),
            ("跌破支撑，技术漏洞，空单增加", "bearish"),

            # Complex neutral patterns
            ("盘整，监管信号混合，资金流向平衡", "neutral"),
            ("区间震荡，网络指标稳定", "neutral"),
            ("技术整理，机构活动平衡", "neutral"),
            ("横盘，监管方向不明", "neutral"),
            ("价格受困，市场信号混合", "neutral")
        ]

    return [{"text": text, "label": label} for text, label in patterns]

def save_training_data(language: str):
    """Save generated training data to file."""
    technical_data = generate_technical_patterns(language)
    context_data = generate_market_context(language)
    combined_data = generate_combined_patterns(language)

    # Combine all data
    all_data = technical_data + context_data + combined_data
    random.shuffle(all_data)

    # Split data into training and validation sets (80-20 split)
    validation_size = int(len(all_data) * 0.2)
    training_data = all_data[validation_size:]
    validation_data = all_data[:validation_size]

    data = {
        "training_data": training_data,
        "validation_data": validation_data
    }

    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app/data')
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f'financial_sentiment_data_{language}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    logger.info(f"Generated {len(training_data)} training and {len(validation_data)} validation examples for {language}")

    # Log label distribution
    label_counts = {'bullish': 0, 'bearish': 0, 'neutral': 0}
    for item in all_data:
        label_counts[item['label'].lower()] += 1

    logger.info(f"Label distribution for {language}:")
    logger.info(f"Bullish: {label_counts['bullish']}")
    logger.info(f"Bearish: {label_counts['bearish']}")
    logger.info(f"Neutral: {label_counts['neutral']}")

if __name__ == '__main__':
    random.seed(42)  # For reproducibility

    for language in ['english', 'chinese']:
        logger.info(f"Generating training data for {language}...")
        save_training_data(language)
        logger.info(f"Completed generating {language} training data")
