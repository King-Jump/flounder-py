import logging
import time
from trading.config import Config
from trading.service import TradingService
from examples.strategies import SimpleMovingAverageStrategy, GridTradingStrategy, RsiStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    config = Config()
    
    trading_service = TradingService(config)
    
    sma_strategy = SimpleMovingAverageStrategy(window_size=50)
    grid_strategy = GridTradingStrategy(grid_count=5, grid_range=0.02)
    rsi_strategy = RsiStrategy(window_size=14, oversold=30, overbought=70)
    
    trading_service.strategy_engine.register_strategy(sma_strategy)
    trading_service.strategy_engine.register_strategy(grid_strategy)
    trading_service.strategy_engine.register_strategy(rsi_strategy)
    
    sma_strategy.set_trading_service(trading_service)
    grid_strategy.set_trading_service(trading_service)
    rsi_strategy.set_trading_service(trading_service)
    
    print("\nAvailable strategies:")
    print("1. Simple Moving Average Strategy")
    print("2. Grid Trading Strategy")
    print("3. RSI Strategy")
    
    choice = input("\nEnter strategy number to run (1/2/3): ").strip()
    
    if choice == "1":
        trading_service.strategy_engine.start_strategy("SimpleMovingAverageStrategy")
        print("Running Simple Moving Average Strategy...")
    elif choice == "2":
        trading_service.strategy_engine.start_strategy("GridTradingStrategy")
        print("Running Grid Trading Strategy...")
    elif choice == "3":
        trading_service.strategy_engine.start_strategy("RsiStrategy")
        print("Running RSI Strategy...")
    else:
        print("Invalid choice, running all strategies")
        trading_service.strategy_engine.start_strategy("SimpleMovingAverageStrategy")
        trading_service.strategy_engine.start_strategy("GridTradingStrategy")
        trading_service.strategy_engine.start_strategy("RsiStrategy")
    
    try:
        trading_service.start()
        
        while True:
            time.sleep(5)
            account_info = trading_service.get_account_info()
            print("\nAccount Summary:")
            print(f"Equity: ${account_info['equity']:.2f}")
            print(f"Initial Balance: ${account_info['initial_balance']:.2f}")
            print("Balances:")
            for asset, balance in account_info['balances'].items():
                if balance['total'] > 0:
                    print(f"  {asset}: {balance['free']:.4f} (free) + {balance['locked']:.4f} (locked)")
            print("Positions:")
            for symbol, position in account_info['positions'].items():
                print(f"  {symbol}: {position['quantity']:.4f} @ ${position['avg_cost']:.2f}")
                print(f"    Unrealized PnL: ${position['unrealized_pnl']:.2f}")
            print("-" * 50)
            
    except KeyboardInterrupt:
        print("\nStopping trading service...")
        trading_service.stop()
        trading_service.pnl_chart.plot_pnl()

if __name__ == "__main__":
    main()
