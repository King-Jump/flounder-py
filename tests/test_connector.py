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


def can_connect_to_binance() -> bool:
    """检查是否能够连接到 Binance WebSocket"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('stream.binance.com', 443))
        sock.close()
        return result == 0
    except Exception:
        return False


class TestBinanceWsConnectorIntegration:
    """
    集成测试：真实连接到 Binance WebSocket
    需要网络连接，使用 pytest.mark.skipif 标记
    """
    
    def setup_method(self):
        self.connector = None
    
    def teardown_method(self):
        if self.connector and self.connector.running:
            self.connector.disconnect()
    
    @pytest.mark.integration
    @pytest.mark.timeout(15)
    @pytest.mark.skipif(not can_connect_to_binance(), reason="无法连接到 Binance 服务器")
    def test_real_binance_connection(self):
        """测试真实连接到 Binance WebSocket"""
        self.connector = BinanceWsConnector(symbol="btcusdt", depth_level=10)
        
        received_data = []
        def on_update(depth):
            received_data.append(depth)
            print(f"Received depth update: symbol={depth.symbol}, best_bid={depth.best_bid:.2f}, best_ask={depth.best_ask:.2f}, bids={len(depth.bids)}, asks={len(depth.asks)}, timestamp={depth.timestamp}")
        
        self.connector.on_depth_update = on_update
        self.connector.connect()
        
        import time
        timeout = 10
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if len(received_data) >= 3:
                break
            time.sleep(0.5)
        
        assert len(received_data) >= 1, "未能接收到深度数据"
        
        depth = received_data[0]
        assert isinstance(depth, DepthData)
        assert depth.symbol == "BTCUSDT"
        assert depth.timestamp > 0
        
        if len(depth.bids) > 0:
            assert depth.best_bid > 0
        if len(depth.asks) > 0:
            assert depth.best_ask > 0
    
    @pytest.mark.integration
    @pytest.mark.timeout(20)
    @pytest.mark.skipif(not can_connect_to_binance(), reason="无法连接到 Binance 服务器")
    def test_real_connection_reconnect(self):
        """测试连接断开后自动重连"""
        self.connector = BinanceWsConnector(symbol="btcusdt", depth_level=10)
        
        received_count = [0]
        def on_update(depth):
            received_count[0] += 1
        
        self.connector.on_depth_update = on_update
        self.connector.connect()
        
        import time
        timeout = 8
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if received_count[0] >= 2:
                break
            time.sleep(0.5)
        
        assert received_count[0] >= 1, "初始连接未能接收到数据"
        
        initial_count = received_count[0]
        
        if self.connector.ws:
            self.connector.ws.close()
        
        time.sleep(2)
        
        timeout = 10
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if received_count[0] > initial_count:
                break
            time.sleep(0.5)
        
        assert received_count[0] > initial_count, "重连后未能继续接收数据"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
