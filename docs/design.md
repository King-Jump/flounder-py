# 模拟交易模块设计文档

## 1. 架构设计

### 1.1 整体架构

采用事件驱动架构，模块间通过事件总线解耦：

```
┌─────────────────────────────────────────────────────────────────┐
│                        模拟交易系统                              │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  WebSocket   │───▶│  MarketData  │───▶│  Strategy    │      │
│  │  Connector   │    │  Processor   │    │  Engine      │      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘      │
│                                                 │               │
│                                                 ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │  Account     │◀───│  Order       │◀───│  Matcher     │      │
│  │  Manager     │    │  Manager     │    │  Engine      │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                  │                                   │
│         ▼                  ▼                                   │
│  ┌──────────────┐    ┌──────────────┐                          │
│  │  PnL Tracker │◀───│  Position    │                          │
│  │  (盈亏跟踪)   │    │  Manager     │                          │
│  └──────────────┘    └──────────────┘                          │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                              │
│  │  PnL Chart   │                                              │
│  │  (盈亏曲线)   │                                              │
│  └──────────────┘                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 模块职责

| 模块 | 职责 | 关键类/接口 |
| :--- | :--- | :--- |
| WebSocket Connector | 连接 Binance WS、接收 Depth 数据 | `BinanceWsConnector` |
| MarketData Processor | 解析深度数据、维护实时订单簿 | `OrderBook`, `MarketDataProcessor` |
| Strategy Engine | 策略接口管理、策略执行调度 | `TradingStrategy` (接口), `StrategyEngine` |
| Matcher Engine | 订单撮合逻辑 | `OrderMatcher` |
| Order Manager | 订单状态管理、订单查询 | `OrderManager` |
| Account Manager | 账户资金管理 | `AccountManager` |
| Position Manager | 持仓管理 | `PositionManager` |
| PnL Tracker | 盈亏计算与跟踪 | `PnLTracker` |
| PnL Chart | 盈亏曲线可视化 | `PnLChart` |

## 2. 核心接口设计

### 2.1 交易策略接口 (TradingStrategy)

```typescript
interface TradingStrategy {
    getName(): string;
    onDepthUpdate(depth: DepthData): void;
    onOrderUpdate(order: Order): void;
}
```

### 2.2 订单服务接口 (TradingService)

| 方法名 | 功能说明 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| `placeOrder` | 下单 | `orderRequest: OrderRequest` | `Order` |
| `cancelOrder` | 取消订单 | `orderId: string` | `Order` |
| `getOrder` | 查询订单 | `orderId: string` | `Order \| null` |
| `getOpenOrders` | 获取开放订单列表 | `symbol?: string` | `Order[]` |

### 2.3 账户服务接口 (AccountService)

| 方法名 | 功能说明 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| `getAccount` | 获取账户信息 | 无 | `Account` |
| `getBalance` | 获取指定币种余额 | `asset: string` | `Balance \| null` |

### 2.4 策略管理接口 (StrategyManager)

| 方法名 | 功能说明 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| `registerStrategy` | 注册策略 | `strategy: TradingStrategy` | `void` |
| `unregisterStrategy` | 注销策略 | `strategyName: string` | `void` |
| `startStrategy` | 启动策略 | `strategyName: string` | `void` |
| `stopStrategy` | 停止策略 | `strategyName: string` | `void` |

### 2.5 盈亏跟踪接口 (PnLTracker)

| 方法名 | 功能说明 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| `calculateRealizedPnL` | 计算已实现盈亏 | `orders: Order[]` | `number` |
| `calculateUnrealizedPnL` | 计算未实现盈亏 | `positions: Position[], currentPrice: number` | `number` |
| `getTotalPnL` | 获取总盈亏 | 无 | `number` |
| `getPnLHistory` | 获取盈亏历史数据 | `timeRange?: TimeRange` | `PnLDataPoint[]` |
| `updatePnL` | 更新盈亏数据 | `depth: DepthData` | `void` |

### 2.6 盈亏可视化接口 (PnLChart)

| 方法名 | 功能说明 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| `addDataPoint` | 添加数据点 | `point: PnLDataPoint` | `void` |
| `getChartData` | 获取图表数据 | `timeRange: TimeRange` | `ChartData` |
| `getPerformanceMetrics` | 获取绩效指标 | 无 | `PerformanceMetrics` |

## 3. 核心类设计

### 3.1 订单模型 (Order)

| 字段名 | 类型 | 含义 | 约束 |
| :--- | :--- | :--- | :--- |
| orderId | string | 订单ID | UUID |
| symbol | string | 交易对 | 非空 |
| orderType | OrderType | 订单类型 | LIMIT/MARKET |
| side | OrderSide | 买卖方向 | BUY/SELL |
| price | decimal | 限价价格 | LIMIT必填 |
| quantity | decimal | 下单数量 | > 0 |
| filledQuantity | decimal | 已成交数量 | >= 0 |
| avgFillPrice | decimal | 平均成交价 | >= 0 |
| status | OrderStatus | 订单状态 | NEW/FILLED/CANCELLED/PARTIALLY_FILLED |
| createdAt | long | 创建时间 | 毫秒时间戳 |
| updatedAt | long | 更新时间 | 毫秒时间戳 |

### 3.2 深度数据模型 (DepthData)

| 字段名 | 类型 | 含义 | 约束 |
| :--- | :--- | :--- | :--- |
| symbol | string | 交易对 | 非空 |
| bids | Array<[price, quantity]> | 卖盘挂单（价格从高到低） | 非空，按价格降序 |
| asks | Array<[price, quantity]> | 买盘挂单（价格从低到高） | 非空，按价格升序 |
| timestamp | long | 数据时间戳 | 毫秒 |

### 3.3 账户模型 (Account)

| 字段名 | 类型 | 含义 | 约束 |
| :--- | :--- | :--- | :--- |
| accountId | string | 账户ID | UUID |
| balances | Map<string, Balance> | 币种余额 | 非空 |
| initialBalance | decimal | 初始资金 | > 0 |
| createdAt | long | 创建时间 | 毫秒时间戳 |

### 3.4 余额模型 (Balance)

| 字段名 | 类型 | 含义 | 约束 |
| :--- | :--- | :--- | :--- |
| asset | string | 币种 | 非空 |
| free | decimal | 可用余额 | >= 0 |
| locked | decimal | 冻结余额 | >= 0 |

### 3.5 持仓模型 (Position)

| 字段名 | 类型 | 含义 | 约束 |
| :--- | :--- | :--- | :--- |
| symbol | string | 交易对 | 非空 |
| quantity | decimal | 持仓数量 | 可为负（表示空头） |
| avgCost | decimal | 平均成本价 | >= 0 |
| unrealizedPnL | decimal | 未实现盈亏 | 计算得出 |
| realizedPnL | decimal | 已实现盈亏 | 累加 |

### 3.6 盈亏数据点模型 (PnLDataPoint)

| 字段名 | 类型 | 含义 | 约束 |
| :--- | :--- | :--- | :--- |
| timestamp | long | 时间戳 | 毫秒 |
| totalPnl | decimal | 总盈亏 | 可正可负 |
| realizedPnl | decimal | 已实现盈亏 | 可正可负 |
| unrealizedPnl | decimal | 未实现盈亏 | 可正可负 |
| equity | decimal | 账户权益 | >= 0 |
| returnRate | decimal | 收益率 | 百分比 |

### 3.7 绩效指标模型 (PerformanceMetrics)

| 字段名 | 类型 | 含义 | 约束 |
| :--- | :--- | :--- | :--- |
| totalReturn | decimal | 总收益率 | 百分比 |
| maxDrawdown | decimal | 最大回撤 | 百分比 |
| avgReturn | decimal | 平均收益率 | 百分比 |
| sharpeRatio | decimal | 夏普比率 | 可正可负 |
| winRate | decimal | 胜率 | 百分比 |
| profitFactor | decimal | 盈亏比 | >= 0 |
| totalTrades | number | 总交易次数 | >= 0 |

## 4. 撮合引擎设计

### 4.1 撮合流程

```
1. 订单提交 → 2. 订单验证 → 3. 撮合匹配 → 4. 资金处理 → 5. 持仓更新 → 6. 状态更新 → 7. 盈亏更新
     ↓            ↓              ↓              ↓              ↓              ↓              ↓
   Order      余额检查      价格优先        冻结/扣减       持仓成本       NEW→FILLED       PnL重算
            数量检查      时间优先        成交后解冻      更新均价       PARTIALLY_FILLED
```

### 4.2 撮合规则

| 订单类型 | 撮合规则 |
| :--- | :--- |
| **市价买单** | 以当前最低卖价（ask[0]）成交，直至订单完全成交或卖盘耗尽 |
| **市价卖单** | 以当前最高买价（bid[0]）成交，直至订单完全成交或买盘耗尽 |
| **限价买单** | 挂单在买盘（等待成交），当卖盘价格 <= 限价时触发成交 |
| **限价卖单** | 挂单在卖盘（等待成交），当买盘价格 >= 限价时触发成交 |

### 4.3 订单簿模拟

| 操作 | 说明 |
| :--- | :--- |
| 深度数据解析 | 从 Binance WS 解析 bids/asks 数组 |
| 价格层级 | 按价格排序构建订单簿 |
| 成交量匹配 | 根据数量消耗订单簿层级 |

## 5. 盈亏跟踪设计

### 5.1 盈亏计算公式

#### 5.1.1 已实现盈亏 (Realized PnL)

```
买单已实现盈亏 = (卖出成交价 - 买入成本价) × 卖出数量
卖单已实现盈亏 = (卖出成交价 - 卖出成本价) × 卖出数量
```

#### 5.1.2 未实现盈亏 (Unrealized PnL)

```
多头持仓未实现盈亏 = (当前价格 - 持仓成本价) × 持仓数量
空头持仓未实现盈亏 = (持仓成本价 - 当前价格) × 持仓数量
```

#### 5.1.3 总盈亏 (Total PnL)

```
总盈亏 = 已实现盈亏 + 未实现盈亏
```

#### 5.1.4 收益率 (Return Rate)

```
收益率 = 总盈亏 / 初始资金 × 100%
```

### 5.2 盈亏更新触发条件

| 事件 | 盈亏更新内容 |
| :--- | :--- |
| 订单成交 | 重新计算已实现盈亏和持仓成本 |
| 行情更新 | 重新计算未实现盈亏 |
| 定时触发 | 生成新的 PnLDataPoint 记录 |

### 5.3 持仓成本计算

采用**移动平均法**计算持仓成本：

```
新持仓成本 = (原持仓数量 × 原成本价 + 新成交数量 × 成交价) / (原持仓数量 + 新成交数量)
```

### 5.4 盈亏数据存储

| 数据结构 | 用途 | 容量 |
| :--- | :--- | :--- |
| `List<PnLDataPoint>` | 盈亏历史数据点 | 无限制 |
| `Map<String, Order>` | 历史订单记录 | 无限制 |
| `Map<String, Position>` | 当前持仓 | 按交易对 |

## 6. 盈亏曲线可视化设计

### 6.1 图表数据结构 (ChartData)

```typescript
interface ChartData {
    labels: string[];          // 时间标签
    datasets: Dataset[];       // 数据集
}

interface Dataset {
    label: string;             // 数据集名称
    data: number[];            // 数据值
    borderColor: string;       // 线条颜色
    backgroundColor: string;   // 填充颜色
}
```

### 6.2 支持的图表类型

| 图表类型 | 用途 |
| :--- | :--- |
| 盈亏曲线 | 显示总盈亏随时间变化 |
| 权益曲线 | 显示账户权益随时间变化 |
| 回撤曲线 | 显示账户回撤情况 |
| 收益率曲线 | 显示收益率百分比变化 |

### 6.3 时间范围选择

| 范围 | 说明 |
| :--- | :--- |
| 1D | 当日数据，粒度 1 分钟 |
| 1W | 本周数据，粒度 5 分钟 |
| 1M | 本月数据，粒度 30 分钟 |
| ALL | 全部历史数据，粒度自适应 |

## 7. 绩效指标计算

### 7.1 最大回撤 (Max Drawdown)

```
最大回撤 = max(Peak - CurrentValue) / Peak × 100%
```

### 7.2 夏普比率 (Sharpe Ratio)

```
夏普比率 = (平均收益率 - 无风险利率) / 收益率标准差
假设无风险利率为 0
```

### 7.3 胜率 (Win Rate)

```
胜率 = 盈利交易次数 / 总交易次数 × 100%
```

### 7.4 盈亏比 (Profit Factor)

```
盈亏比 = 总盈利金额 / 总亏损金额
```

## 8. 配置说明

| 配置项 | 说明 | 默认值 |
| :--- | :--- | :--- |
| wsUrl | Binance WS 地址 | wss://stream.binance.com:9443/ws |
| symbol | 交易对 | btcusdt |
| depthLevel | 深度级别 | 100 |
| initialBalance | 初始资金（USDT） | 10000 |
| commissionRate | 手续费率 | 0.001 (0.1%) |
| pnlUpdateInterval | 盈亏更新间隔(ms) | 1000 |
| chartDataRetention | 图表数据保留天数 | 30 |

## 9. 类图

```
┌─────────────────────┐       ┌─────────────────────┐
│   <<interface>>     │       │   <<interface>>     │
│   TradingStrategy    │       │   TradingService     │
├─────────────────────┤       ├─────────────────────┤
│ + getName()         │       │ + placeOrder()      │
│ + onDepthUpdate()   │       │ + cancelOrder()     │
│ + onOrderUpdate()   │       │ + getOrder()        │
└─────────────────────┘       │ + getOpenOrders()   │
           ▲                  └─────────────────────┘
           │                            │
           │                            ▼
┌─────────────────────┐       ┌─────────────────────┐
│   StrategyEngine    │       │   OrderManager      │
├─────────────────────┤       ├─────────────────────┤
│ - strategies[]      │       │ - orders Map        │
│ - start()           │       │ - placeOrder()      │
│ - stop()            │       │ - cancelOrder()     │
└─────────────────────┘       │ - updateOrder()     │
                             └─────────────────────┘
                                    │
                                    ▼
                             ┌─────────────────────┐
                             │   OrderMatcher      │
                             ├─────────────────────┤
                             │ - matchOrder()      │
                             │ - matchMarketOrder()│
                             │ - matchLimitOrder() │
                             └─────────────────────┘
                                    │
                                    ▼
┌─────────────────────┐       ┌─────────────────────┐
│   PnLTracker        │       │   AccountManager    │
├─────────────────────┤       ├─────────────────────┤
│ - pnlHistory[]      │       │ - balances Map      │
│ - updatePnL()        │       │ - positions Map     │
│ - getPnLHistory()   │       │ - updateBalance()   │
│ - calculatePnL()     │       │ - updatePosition()  │
└─────────────────────┘       └─────────────────────┘
            │
            ▼
┌─────────────────────┐
│   PnLChart          │
├─────────────────────┤
│ - dataPoints[]      │
│ - addDataPoint()    │
│ - getChartData()    │
│ - getMetrics()      │
└─────────────────────┘
```

## 10. 时序图

### 10.1 订单撮合时序

```
用户    StrategyEngine   OrderManager   OrderMatcher   AccountManager   PnLTracker
 │           │                │              │              │              │
 │  placeOrder()              │              │              │              │
 │──────────>│                │              │              │              │
 │           │   createOrder()│              │              │              │
 │           │──────────────>│              │              │              │
 │           │               │   validate() │              │              │
 │           │               │─────────────>│              │              │
 │           │               │              │  checkBalance()              │
 │           │               │              │──────────────>│              │
 │           │               │              │<──────────────│              │
 │           │               │              │               │              │
 │           │               │              │   match()     │              │
 │           │               │              │──────────────>│              │
 │           │               │              │               │  updatePnL() │
 │           │               │              │               │─────────────>│
 │           │               │              │               │              │
 │           │  return Order │              │              │              │
 │<──────────│<──────────────│              │              │              │
```

### 10.2 盈亏更新时序

```
MarketData   OrderMatcher   AccountManager   PnLTracker   PnLChart
   │              │              │              │              │
   │ onDepth()    │              │              │              │
   │─────────────>│              │              │              │
   │              │              │              │              │
   │  recalculateUnrealizedPnL()│              │              │
   │              │──────────────>│              │              │
   │              │              │              │              │
   │              │   updatePnL()│              │              │
   │              │─────────────>│              │              │
   │              │              │              │              │
   │              │              │  createDataPoint()         │
   │              │              │─────────────>│              │
   │              │              │              │              │
   │              │              │   addDataPoint()            │
   │              │              │              │────────────>│
   │              │              │              │              │
```
