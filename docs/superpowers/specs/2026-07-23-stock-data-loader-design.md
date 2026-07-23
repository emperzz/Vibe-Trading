# stock_data 同进程 DataLoader 适配设计

日期：2026-07-23

## 目标

将 `D:\GitRepo\skills\stock_data` 作为一个聚合式 A 股行情数据源接入 Vibe-Trading 的 `DataLoaderProtocol`。第一阶段只覆盖标准 OHLCV 行情，不接入新闻、公告、板块、指标或独立 FastAPI 服务。

## 方案

新增 `agent/backtest/loaders/stock_data_loader.py`，在同一 Python 进程中调用 `stock_data.data_provider.manager.DataFetcherManager`。Vibe-Trading 只暴露一个 `stock_data` loader；具体 fetcher 的优先级、熔断和内部回退继续由 `stock_data` 管理，避免复制十几个 fetcher。

调用链：

```text
Vibe-Trading DataLoaderProtocol
  -> StockDataLoader.fetch()
  -> DataFetcherManager
  -> stock_data fetcher/failover
  -> 标准化 DataFrame
```

## 接口适配

`StockDataLoader` 实现：

- `name = "stock_data"`
- `markets = {"a_share"}`
- `requires_auth` 根据 stock_data 可用配置判定，不能把可选 token 写死为必需
- `is_available()`：仅检查同进程包是否可导入及 manager 是否可构造，不发起网络请求
- `fetch(codes, start_date, end_date, interval="1D", fields=None)`

输出统一为：

```python
{
    "000001.SZ": DataFrame(
        index=DatetimeIndex(name="trade_date"),
        columns=["open", "high", "low", "close", "volume"],
    )
}
```

代码格式、日期格式和字段名称在 adapter 内转换。支持的第一阶段周期为 `1D`、`1m`、`5m`、`15m`、`30m`、`1H`；不支持的周期显式拒绝，不静默降级为日线。返回结果按日期升序排列，数值字段转为数值类型并删除无法使用的行。

标准化后调用 Vibe-Trading 现有 `validate_ohlc`，不重新实现 OHLC 规则。单个代码失败不应丢弃其它成功代码；全部失败时返回与现有 loader 一致的空映射或受控异常，并记录来源和失败原因。

## 注册与路由

修改 `agent/backtest/loaders/registry.py`：

- 将 `stock_data` 加入 `VALID_SOURCES`
- 将 loader 模块加入懒加载列表
- 将其加入 `FALLBACK_CHAINS["a_share"]`

初始顺序：

```text
tencent -> mootdx -> stock_data -> eastmoney -> baostock -> akshare -> tushare -> local
```

不修改其它市场的 fallback chain，也不把 `stock_data` HTTP 服务加入配置。

如面向用户的 source 枚举是静态列表，则同步加入 `agent/src/tools/market_data_tool.py`；否则保持 registry 为唯一来源。

## 依赖与失败边界

`stock_data` 是 sibling 项目，不假设已经安装。adapter 应使用懒导入，使 Vibe-Trading 在未安装该包时仍能启动，其 `is_available()` 返回 False，自动 fallback 到其它 A 股数据源。

不在本次工作中新增依赖锁或复制 sibling 项目代码。开发/测试环境通过可编辑安装或现有 Python 路径提供 `stock_data`；生产打包方式若尚未确定，单独记录为后续发布问题。

避免在 Vibe-Trading 和 stock_data 之间形成双层无限重试：Vibe-Trading 只把一次 fetch 委托给 manager，manager 内部负责自己的有限回退；适配器不再套额外重试循环。

## 测试

新增 `agent/tests/test_stock_data_loader.py`，全部使用 mock，不访问外部网络，至少覆盖：

1. registry 注册和 loader 元数据
2. stock_data 未安装时的可用性行为
3. manager 返回数据的字段、索引、排序和代码格式标准化
4. 日线及分钟周期映射
5. 不支持周期显式拒绝
6. OHLC 异常数据经过现有校验
7. 多代码中一部分失败时保留成功结果
8. A 股 fallback chain 包含 `stock_data`

验证命令：

```bash
pytest agent/tests/test_stock_data_loader.py agent/tests/test_market_data.py -q
pytest agent/tests/test_valid_sources_covers_all_registered_loaders.py -q
```

## 不包含的内容

- 新闻、公告、研报、板块和涨停池的独立工具接入
- 技术指标搬迁到 loader
- SQLite 数据迁移
- `stock_data` FastAPI 服务启动、健康检查或 HTTP 客户端
- 将每个 stock_data fetcher 拆成独立 Vibe-Trading loader
