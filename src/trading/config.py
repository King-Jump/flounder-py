from typing import Dict, Any

class Config:
    WS_URL: str = "wss://stream.binance.com:9443/ws"
    SYMBOL: str = "btcusdt"
    DEPTH_LEVEL: int = 100
    INITIAL_BALANCE: float = 10000.0
    COMMISSION_RATE: float = 0.001
    PNL_UPDATE_INTERVAL: int = 1000
    CHART_DATA_RETENTION: int = 30
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        config = cls()
        for key, value in config_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config
