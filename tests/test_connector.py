import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from trading.models import DepthData

import importlib.util
ws_connector_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'ws', 'connector.py')
spec = importlib.util.spec_from_file_location("ws_connector", ws_connector_path)
ws_connector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws_connector)
BinanceWsConnector = ws_connector.BinanceWsConnector
MarketDataProcessor = ws_connector.MarketDataProcessor


class TestBinanceWsConnector:
    
    def test_initialization(self):
        connector = BinanceWsConnector(symbol="btcusdt", depth_level=100)
        
        assert connector.symbol == "btcusdt"
        assert connector.depth_level == 100
        assert connector.ws_url == "wss://stream.binance.com:9443/ws/btcusdt@depth100"
        assert connector.ws is None
        assert connector.on_depth_update is None
        assert connector.running is False
        assert connector.thread is None
    
    def test_parse_depth_data(self):
        connector = BinanceWsConnector(symbol="btcusdt")
        
        mock_data = {
            'bids': [['45000.00', '0.5'], ['44999.00', '1.2']],
            'asks': [['45001.00', '0.8'], ['45002.00', '1.5']],
            'E': 1620000000000
        }
        
        depth_data = connector._parse_depth_data(mock_data)
        
        assert depth_data.symbol == "BTCUSDT"
        assert len(depth_data.bids) == 2
        assert len(depth_data.asks) == 2
        assert depth_data.bids[0] == (45000.0, 0.5)
        assert depth_data.asks[0] == (45001.0, 0.8)
        assert depth_data.timestamp == 1620000000000
        assert depth_data.best_bid == 45000.0
        assert depth_data.best_ask == 45001.0
    
    def test_parse_empty_depth_data(self):
        connector = BinanceWsConnector(symbol="ethusdt")
        
        mock_data = {}
        
        depth_data = connector._parse_depth_data(mock_data)
        
        assert depth_data.symbol == "ETHUSDT"
        assert len(depth_data.bids) == 0
        assert len(depth_data.asks) == 0
        assert depth_data.timestamp > 0
        assert depth_data.best_bid == 0.0
        assert depth_data.best_ask == 0.0
    
    @patch('websocket.WebSocketApp')
    def test_connect(self, mock_ws_app):
        connector = BinanceWsConnector(symbol="btcusdt")
        
        connector.connect()
        
        mock_ws_app.assert_called_once()
        assert connector.ws is not None
        assert connector.running is True
        assert connector.thread is not None
        
        connector.disconnect()
    
    def test_on_message_with_valid_data(self):
        connector = BinanceWsConnector(symbol="btcusdt")
        mock_callback = Mock()
        connector.on_depth_update = mock_callback
        
        mock_message = json.dumps({
            'bids': [['45000.00', '0.5']],
            'asks': [['45001.00', '0.8']],
            'E': 1620000000000
        })
        
        connector._on_message(None, mock_message)
        
        mock_callback.assert_called_once()
        depth_data = mock_callback.call_args[0][0]
        assert isinstance(depth_data, DepthData)
        assert depth_data.symbol == "BTCUSDT"
    
    def test_on_message_with_invalid_data(self):
        connector = BinanceWsConnector(symbol="btcusdt")
        mock_callback = Mock()
        connector.on_depth_update = mock_callback
        
        with patch.object(ws_connector, 'logger') as mock_logger:
            connector._on_message(None, "invalid json")
            
            mock_logger.error.assert_called_once()
            mock_callback.assert_not_called()


class TestMarketDataProcessor:
    
    def test_initialization(self):
        processor = MarketDataProcessor()
        
        assert processor.order_book_bids == []
        assert processor.order_book_asks == []
        assert processor.last_update_time == 0
    
    def test_process_depth_update(self):
        processor = MarketDataProcessor()
        
        depth_data = DepthData(
            symbol="BTCUSDT",
            bids=[(45000.0, 0.5), (44999.0, 1.0)],
            asks=[(45001.0, 0.8), (45002.0, 1.2)],
            timestamp=1620000000000
        )
        
        result = processor.process_depth_update(depth_data)
        
        assert processor.order_book_bids == depth_data.bids
        assert processor.order_book_asks == depth_data.asks
        assert processor.last_update_time == depth_data.timestamp
        assert result.symbol == "BTCUSDT"
        assert result.timestamp == 1620000000000
    
    def test_get_best_bid(self):
        processor = MarketDataProcessor()
        
        assert processor.get_best_bid() == 0.0
        
        depth_data = DepthData(
            symbol="BTCUSDT",
            bids=[(45000.0, 0.5), (44999.0, 1.0)],
            asks=[],
            timestamp=1620000000000
        )
        processor.process_depth_update(depth_data)
        
        assert processor.get_best_bid() == 45000.0
    
    def test_get_best_ask(self):
        processor = MarketDataProcessor()
        
        assert processor.get_best_ask() == 0.0
        
        depth_data = DepthData(
            symbol="BTCUSDT",
            bids=[],
            asks=[(45001.0, 0.8), (45002.0, 1.2)],
            timestamp=1620000000000
        )
        processor.process_depth_update(depth_data)
        
        assert processor.get_best_ask() == 45001.0
    
    def test_get_mid_price(self):
        processor = MarketDataProcessor()
        
        assert processor.get_mid_price() == 0.0
        
        depth_data = DepthData(
            symbol="BTCUSDT",
            bids=[(45000.0, 0.5)],
            asks=[(45002.0, 0.8)],
            timestamp=1620000000000
        )
        processor.process_depth_update(depth_data)
        
        assert processor.get_mid_price() == 45001.0
    
    def test_get_order_book_snapshot(self):
        processor = MarketDataProcessor()
        
        depth_data = DepthData(
            symbol="BTCUSDT",
            bids=[(45000.0, 0.5), (44999.0, 1.0)],
            asks=[(45001.0, 0.8), (45002.0, 1.2)],
            timestamp=1620000000000
        )
        processor.process_depth_update(depth_data)
        
        snapshot = processor.get_order_book_snapshot()
        
        assert snapshot.bids == depth_data.bids
        assert snapshot.asks == depth_data.asks
        assert snapshot.timestamp == depth_data.timestamp
        assert snapshot.symbol == ""
        
        snapshot.bids[0] = (99999.0, 1.0)
        
        assert processor.order_book_bids[0] == (45000.0, 0.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
