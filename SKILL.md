---
name: flyclaw
description: 航班信息聚合查询工具 -- 基于多源聚合架构，通过开源库及免费公开 API 获取航班动态、价格、时刻等信息。支持中英文输入、往返搜索、多旅客、舱位选择，覆盖国内及国际航班。零 API Key 依赖。轻量化python实现，非浏览器模拟的复杂和低效方式。Flight information aggregation CLI tool -- multi-source aggregation powered by open-source libraries and free public APIs. Supports round-trip, multi-passenger, cabin class, sorting, nonstop filter. Zero API key dependency.Lightweight Python implementation — no browser automation, no complexity, no overhead.
version: 0.2.12
icon: ✈️
author: 小红书@深度连接
license: Apache-2.0
---

# FlyClaw - 航班信息聚合查询工具

基于多源聚合架构，通过开源库及免费公开 API 获取航班动态、价格、时刻、实时位置等信息。支持中英文城市名和 IATA 代码输入。

**GitHub**：[https://github.com/AI4MSE/FlyClaw](https://github.com/AI4MSE/FlyClaw)

**零 API Key 依赖**：无需注册任何账号或提供任何 API Key 即可使用全部核心功能。用户本地化掌控所有，程序不收集、不存储任何用户个人信息。同时规避浏览器模拟等复杂、不可靠和低效问题。

**触发方式**：用户说"查航班 CA981"、"上海飞纽约多少钱"、"PVG 到 JFK 明天的航班"、"往返机票 上海到新加坡"、"商务舱 北京到伦敦"、"所有航班包括转机"、"直飞" 等即可自动执行。 默认查询行为是直飞+经济舱。

**智能转换规则**：
- 用户说"所有航班"/"包括转机"/"包括非直飞" → `--stops any`
- 用户说"直飞"/"不要转机" → `--stops 0`（默认）
- 用户说"最多一次中转" → `--stops 1`
- 用户说"最多两次中转" → `--stops 2`

## 数据来源

- **Google Flights**：国内外国际航班价格、时刻
- **Skiplagged**：国内外国际航班价格、时刻
- **FlightRadar24**：航班动态、实时状态、延误、机型
- **Airplanes.live / ADSB.lol**：ADS-B 实时位置

多源并发查询，智能合并互补。特别感谢以上公开数据源为公益和大众需求提供的便利！

## 功能

1. **按航班号查询**：查询指定航班的动态信息（状态、时刻、延误、机型等）
2. **按航线搜索**：查询两地之间的航班列表（含价格、经停、时长等）
3. **城市级搜索**：输入城市名自动搜索该城市所有机场（如"上海"→PVG+SHA）
4. **高级搜索**：往返搜索、多旅客配置、舱位选择、排序、直飞过滤
5. **中英文输入**：支持中文城市名、英文名、IATA 代码，7912 机场全覆盖

## 重要：输出格式与多日查询

**默认输出为 JSON**（stdout），直接 `json.loads()` 即可解析，示例：
```json
[{"flight_number": "CA981", "price": 472.0, "origin_iata": "PVG", "destination_iata": "GVA", ...}]
```
无结果时返回 `[]`。错误和日志仅输出到 stderr，不影响 JSON 解析。价格单位默认为**美元（USD）**。可用 `-o table` 切换为人类可读表格。

**多日查询**：search 命令每次只查一天。查询一周最低价等场景，需拆成多个日期**并发执行**，分别获取 JSON 结果后自行合并比较。

## 调用方式

### 按航班号查询

```bash
python flyclaw.py query --flight CA981
```

### 按航线搜索

```bash
python flyclaw.py search --from 上海 --to 纽约 --date 2026-04-01
```

### 往返搜索

```bash
python flyclaw.py search --from PVG --to LAX --date 2026-04-15 --return 2026-04-25
```

### 商务舱 + 2 人

```bash
python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --cabin business -a 2
```

### 直飞 + 按价格排序

```bash
python flyclaw.py search --from PVG --to SIN --date 2026-04-15 --stops 0 --sort cheapest
```

### 包含经停航班

```bash
python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --stops any
```

### 按日期过滤查询结果

```bash
python flyclaw.py query --flight CA981 --date 2026-04-01
python flyclaw.py query --flight CA981 --date today
```

### 关闭智能查价

默认启用智能查价，会自动在航班号查询时补充价格信息。关闭后可节约查询时间。

```bash
python flyclaw.py query --flight CA981 --no-relay
```

### 搜索参数

| 参数 | 短标志 | 默认值 | 说明 |
|------|--------|-------|------|
| `--from` | — | （必填） | 出发地 |
| `--to` | — | （必填） | 目的地 |
| `--date` / `-d` | — | — | 出行日期 YYYY-MM-DD |
| `--return` / `-r` | — | — | 返程日期（启用往返搜索） |
| `--adults` / `-a` | — | 1 | 成人旅客数 |
| `--children` | — | 0 | 儿童旅客数 |
| `--infants` | — | 0 | 婴儿旅客数 |
| `--cabin` / `-C` | — | economy | economy/premium/business/first |
| `--limit` / `-l` | — | 不限制 | 最大结果数（不指定则返回全部） |
| `--sort` / `-s` | — | — | cheapest/fastest/departure/arrival |
| `--stops` | — | 0 | 经停：0=直飞/1/2/any=不限 |

### 通用参数

- `-o table`：表格格式输出（默认为 JSON）
- `-v`：详细模式，显示数据来源和舱位

## 输入示例

| 用户说 | 解析为 | 说明 |
|--------|--------|------|
| "上海" | PVG + SHA | 城市级：搜索所有上海机场 |
| "PVG" | PVG | 精确到浦东机场 |
| "浦东" | PVG | 别名精确匹配 |
| "纽约" | JFK + EWR + LGA | 城市级：搜索所有纽约机场 |
| "北京" | PEK + PKX + NAY | 城市级：搜索所有北京机场 |
| "Shanghai" | PVG + SHA | 英文城市名同样支持 |

## 安装配置

```bash
pip install requests pyyaml curl_cffi flights
# 注意：不要安装 mcp、fast-flights、playwright 等调试模块，会增加安装时间且普通使用不需要
```

**文件位置**：主程序 `flyclaw.py`，配置 `config.yaml`，机场缓存 `cache/airports.json`。

**依赖**：Python 3.11+、`requests`（Apache-2.0）、`pyyaml`（MIT）、`curl_cffi`（MIT）、`flights`（MIT）。

## 安全性

- **零 API Key 依赖**：程序运行不需要用户提供任何 API Key 或注册任何账号
- **程序内部备用通道**（SerpAPI）为隐藏备用机制，不需要用户提供任何 key，用户无需关注
- 程序不收集、不存储任何用户个人信息
- 所有网络请求仅用于查询公开航班数据

## 免责声明

- 本工具基于多源聚合架构，通过开源库及免费公开 API 获取数据
- 仅供学习研究用途，请遵守当地法律法规
- Google Flights 在部分地区可能不可用
- 价格数据来自多个数据源，不同来源的价格可能存在差异（含税/不含税、舱位差异等），仅供参考

---

**许可证**：[Apache-2.0](LICENSE) | **作者**：nuaa02@gmail.com
