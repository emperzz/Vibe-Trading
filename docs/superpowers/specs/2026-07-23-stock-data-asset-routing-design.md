# stock_data DataLoader 股票/指数路由设计

日期：2026-07-23

## 目标

让新增的 `stock_data` dataloader 沿用现有 `.SH/.SZ` 代码格式，正确区分 A 股股票和指数 K 线，同时不修改 upstream fork 的既有 loader 或共享逻辑。

## 方案

1. 仅在 `backtest/loaders/stock_data_loader.py` 内实现与 Tushare 相同的 A 股指数判断：
   - `000xxx.SH` → `index`；
   - `399xxx.SZ` → `index`；
   - 其他代码（普通股票、ETF、北交所代码）→ `stock`。
2. 调用 `manager.get_kline_data` 时显式传递 `asset="index"` 或 `asset="stock"`。
3. 返回映射继续使用原始请求代码作为 key。
4. 不修改 `tushare.py`、`_symbol_utils.py`、其他 loader 或 DataLoaderProtocol。

## 测试

- 在 `test_stock_data_loader.py` 覆盖股票、ETF、北交所、沪深指数、大小写及异常格式。
- 使用伪 Manager 验证混合代码按输入顺序收到正确的 `asset`。
- 保持周期、日期、复权和 OHLCV 标准化行为不变。

## 范围外

不新增代码前缀，不扩展周/月线、复权配置、缓存或额外字段。
