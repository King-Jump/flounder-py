from dataclasses import dataclass
from typing import List, Optional, Dict
from trading.models import Order, Position, DepthData
from account.manager import AccountManager
import logging
import statistics

logger = logging.getLogger(__name__)

@dataclass
class PnLDataPoint:
    timestamp: int
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    return_rate: float

@dataclass
class PerformanceMetrics:
    total_return: float
    max_drawdown: float
    avg_return: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int

class PnLTracker:
    
    def __init__(self, account_manager: AccountManager, initial_balance: float = 10000.0):
        self.account_manager = account_manager
        self.initial_balance = initial_balance
        self.pnl_history: List[PnLDataPoint] = []
        self.realized_pnl = 0.0
        self.equity_history: List[float] = []
    
    def calculate_realized_pnl(self, orders: List[Order]) -> float:
        realized = 0.0
        for order in orders:
            if order.status.name == "FILLED" and order.side.name == "SELL" and order.avg_fill_price:
                position = self.account_manager.get_position(order.symbol)
                if position.avg_cost > 0:
                    realized += (order.avg_fill_price - position.avg_cost) * order.filled_quantity
        return realized
    
    def calculate_unrealized_pnl(self, positions: List[Position], current_price: float) -> float:
        unrealized = 0.0
        for position in positions:
            unrealized += position.unrealized_pnl
        return unrealized
    
    def get_total_pnl(self) -> float:
        positions = list(self.account_manager.positions.values())
        unrealized = sum(p.unrealized_pnl for p in positions)
        return self.realized_pnl + unrealized
    
    def update_pnl(self, depth: DepthData):
        symbol = depth.symbol
        current_price = depth.mid_price
        
        self.account_manager.recalculate_unrealized_pnl(symbol, current_price)
        
        unrealized_pnl = sum(p.unrealized_pnl for p in self.account_manager.positions.values())
        total_pnl = self.realized_pnl + unrealized_pnl
        equity = self.initial_balance + total_pnl
        return_rate = (total_pnl / self.initial_balance) * 100
        
        datapoint = PnLDataPoint(
            timestamp=depth.timestamp,
            total_pnl=total_pnl,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized_pnl,
            equity=equity,
            return_rate=return_rate
        )
        
        self.pnl_history.append(datapoint)
        self.equity_history.append(equity)
        
        logger.debug(f"PnL updated: total={total_pnl:.2f}, realized={self.realized_pnl:.2f}, unrealized={unrealized_pnl:.2f}")
    
    def get_pnl_history(self, time_range: Optional[str] = None) -> List[PnLDataPoint]:
        if not time_range or time_range == "ALL":
            return self.pnl_history
        
        now = self.pnl_history[-1].timestamp if self.pnl_history else 0
        
        if time_range == "1D":
            threshold = now - (24 * 60 * 60 * 1000)
        elif time_range == "1W":
            threshold = now - (7 * 24 * 60 * 60 * 1000)
        elif time_range == "1M":
            threshold = now - (30 * 24 * 60 * 60 * 1000)
        else:
            return self.pnl_history
        
        return [p for p in self.pnl_history if p.timestamp >= threshold]
    
    def record_trade_pnl(self, order: Order):
        if order.status.name == "FILLED":
            if order.side.name == "SELL":
                position = self.account_manager.get_position(order.symbol)
                if position and position.avg_cost > 0 and order.avg_fill_price:
                    trade_pnl = (order.avg_fill_price - position.avg_cost) * order.filled_quantity
                    self.realized_pnl += trade_pnl
                    logger.info(f"Recorded realized PnL: {trade_pnl:.2f}")
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        if not self.pnl_history:
            return PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
        
        total_return = self.pnl_history[-1].return_rate
        
        max_drawdown = self._calculate_max_drawdown()
        
        returns = []
        for i in range(1, len(self.pnl_history)):
            returns.append(self.pnl_history[i].total_pnl - self.pnl_history[i-1].total_pnl)
        
        avg_return = statistics.mean(returns) if returns else 0.0
        
        if returns:
            std_dev = statistics.stdev(returns) if len(returns) > 1 else statistics.pstdev(returns)
            sharpe_ratio = avg_return / std_dev if std_dev > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        winning_trades = sum(1 for r in returns if r > 0)
        total_trades = len(returns)
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
        
        total_winning = sum(r for r in returns if r > 0)
        total_losing = abs(sum(r for r in returns if r < 0))
        profit_factor = total_winning / total_losing if total_losing > 0 else float('inf')
        
        return PerformanceMetrics(
            total_return=total_return,
            max_drawdown=max_drawdown,
            avg_return=avg_return,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=total_trades
        )
    
    def _calculate_max_drawdown(self) -> float:
        if not self.equity_history:
            return 0.0
        
        max_drawdown = 0.0
        peak = self.equity_history[0]
        
        for equity in self.equity_history:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown

class PnLChart:
    
    def __init__(self, pnl_tracker: PnLTracker):
        self.pnl_tracker = pnl_tracker
    
    def get_chart_data(self, time_range: str = "ALL") -> Dict:
        history = self.pnl_tracker.get_pnl_history(time_range)
        
        labels = [self._format_timestamp(p.timestamp) for p in history]
        total_pnl_data = [p.total_pnl for p in history]
        equity_data = [p.equity for p in history]
        realized_pnl_data = [p.realized_pnl for p in history]
        unrealized_pnl_data = [p.unrealized_pnl for p in history]
        
        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "Total PnL",
                    "data": total_pnl_data,
                    "borderColor": "#22c55e",
                    "backgroundColor": "rgba(34, 197, 94, 0.1)"
                },
                {
                    "label": "Equity",
                    "data": equity_data,
                    "borderColor": "#3b82f6",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)"
                },
                {
                    "label": "Realized PnL",
                    "data": realized_pnl_data,
                    "borderColor": "#f59e0b",
                    "backgroundColor": "rgba(245, 158, 11, 0.1)"
                },
                {
                    "label": "Unrealized PnL",
                    "data": unrealized_pnl_data,
                    "borderColor": "#ef4444",
                    "backgroundColor": "rgba(239, 68, 68, 0.1)"
                }
            ]
        }
    
    def _format_timestamp(self, timestamp: int) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(timestamp / 1000).strftime("%H:%M:%S")
    
    def print_pnl_summary(self):
        metrics = self.pnl_tracker.get_performance_metrics()
        print("\n" + "="*50)
        print("PnL Summary Report")
        print("="*50)
        print(f"Total Return: {metrics.total_return:.2f}%")
        print(f"Max Drawdown: {metrics.max_drawdown:.2f}%")
        print(f"Average Return: {metrics.avg_return:.2f}")
        print(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        print(f"Win Rate: {metrics.win_rate:.2f}%")
        print(f"Profit Factor: {metrics.profit_factor:.2f}")
        print(f"Total Trades: {metrics.total_trades}")
        print("="*50 + "\n")
    
    def plot_pnl(self):
        try:
            import matplotlib.pyplot as plt
            chart_data = self.get_chart_data()
            
            plt.figure(figsize=(12, 6))
            for dataset in chart_data["datasets"]:
                plt.plot(chart_data["labels"], dataset["data"], label=dataset["label"], linewidth=2)
            
            plt.title("PnL Curve")
            plt.xlabel("Time")
            plt.ylabel("Value (USDT)")
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.show()
        except ImportError:
            logger.warning("matplotlib not installed, cannot plot PnL curve")
            print("matplotlib not installed. Install with: pip install matplotlib")
