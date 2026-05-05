import websocket
import json
import threading
from typing import Optional, Callable, List, Tuple
from trading.models import DepthData
import logging

logger = logging.getLogger(__name__)

class BinanceWsConnector:
    
    def __init__(self, symbol: str = "btcusdt", depth_level: int = 100):
        self.symbol = symbol.lower()
        self.depth_level = depth_level
        self.ws_url = f"wss://stream.binance.com:9443/ws/{self.symbol}@depth{self.depth_level}"
        self.ws: Optional[websocket.WebSocketApp] = None
        self.on_depth_update: Optional[Callable[[DepthData], None]] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.running = True
        self.thread = threading.Thread(target=self._run_forever)
        self.thread.start()
        logger.info(f"Connecting to Binance WebSocket: {self.ws_url}")
    
    def _run_forever(self):
        while self.running:
            try:
                self.ws.run_forever()
            except Exception as e:
                logger.error(f"WebSocket connection error: {e}")
                import time
                time.sleep(5)
    
    def disconnect(self):
        self.running = False
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join()
        logger.info("Disconnected from Binance WebSocket")
    
    def _on_open(self, ws):
        logger.info("WebSocket connection opened")
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            depth_data = self._parse_depth_data(data)
            if self.on_depth_update:
                self.on_depth_update(depth_data)
        except Exception as e:
            logger.error(f"Error parsing WebSocket message: {e}")
    
    def _parse_depth_data(self, data: dict) -> DepthData:
        bids: List[Tuple[float, float]] = []
        asks: List[Tuple[float, float]] = []
        
        if 'bids' in data:
            bids = [(float(item[0]), float(item[1])) for item in data['bids']]
        if 'asks' in data:
            asks = [(float(item[0]), float(item[1])) for item in data['asks']]
        
        timestamp = data.get('E', 0)
        
        return DepthData(
            symbol=self.symbol.upper(),
            bids=bids,
            asks=asks,
            timestamp=timestamp
        )
    
    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        if self.running:
            logger.info("Attempting to reconnect...")

class MarketDataProcessor:
    
    def __init__(self):
        self.order_book_bids: List[Tuple[float, float]] = []
        self.order_book_asks: List[Tuple[float, float]] = []
        self.last_update_time = 0
    
    def process_depth_update(self, depth: DepthData) -> DepthData:
        self.order_book_bids = depth.bids
        self.order_book_asks = depth.asks
        self.last_update_time = depth.timestamp
        
        return DepthData(
            symbol=depth.symbol,
            bids=self.order_book_bids,
            asks=self.order_book_asks,
            timestamp=self.last_update_time
        )
    
    def get_best_bid(self) -> float:
        return self.order_book_bids[0][0] if self.order_book_bids else 0.0
    
    def get_best_ask(self) -> float:
        return self.order_book_asks[0][0] if self.order_book_asks else 0.0
    
    def get_mid_price(self) -> float:
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        return (best_bid + best_ask) / 2 if best_bid and best_ask else 0.0
    
    def get_order_book_snapshot(self) -> DepthData:
        return DepthData(
            symbol="",
            bids=self.order_book_bids.copy(),
            asks=self.order_book_asks.copy(),
            timestamp=self.last_update_time
        )
