import json
import os


def create_training_data():
    data = {
        "training_data": [
            {
                "text": "比特币突破重要压力位，成交量显著放大，看多信号明显",
                "label": "bullish",
                "confidence": 0.92,
            },
            {
                "text": "市场恐慌情绪蔓延，多个技术指标显示超卖，建议谨慎",
                "label": "bearish",
                "confidence": 0.90,
            },
            {"text": "双底形态确认，MACD金叉，做多机会来临", "label": "bullish", "confidence": 0.95},
            {"text": "头肩顶形态形成，卖压持续增加，建议减仓", "label": "bearish", "confidence": 0.93},
            {"text": "突破上升通道，成交量配合，看涨确认", "label": "bullish", "confidence": 0.91},
        ]
    }

    os.makedirs("app/data", exist_ok=True)
    with open("app/data/financial_sentiment_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    create_training_data()
