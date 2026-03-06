# FlyClaw - 航班信息聚合查询 CLI 工具

**FlyClaw** 是一个轻量级命令行工具，基于多源聚合架构，通过开源库及免费公开 API 获取数据，在终端中聚合查询航班信息（航班动态、价格、时刻等），原生支持中英文查询，原生OpenClaw技能，覆盖中国国内及国际航班。

核心价值：单一来源不稳定、不完整、覆盖有限 -- FlyClaw 的目标是**聚合、去重、补齐、呈现**。

**作者**：nuaa02@gmail.com 小红书@深度连接
**GitHub**：[https://github.com/AI4MSE/FlyClaw](https://github.com/AI4MSE/FlyClaw)
**许可证**：[Apache-2.0](LICENSE)

## 功能特性

- **多数据源聚合**：基于多源聚合架构（FR24、Google Flight、airplaneslive，后续可以无限扩展），通过开源库及免费公开 API 获取航班动态、价格、实时位置等数据
- **高级搜索**：往返搜索、多旅客（成人/儿童/婴儿）、舱位选择（经济/超经/商务/头等）、结果排序、经停控制（`--stops 0/1/2/any`）、结果限制
- **智能补价（Route Relay）**：航班号查询时自动用发现的航线查 Google Flights 补价格，解决冷启动无价格问题
- **智能返回时间**：有结果后提前返回，不等待慢源（`query.return_time` 配置）
- **可信度优先级合并**：高优先级数据源字段优先，低优先级补空
- **城市级搜索**：城市名输入自动搜索该城市所有机场（"上海"→PVG+SHA，"纽约"→JFK+EWR+LGA），IATA 代码/别名精确到单一机场
- **中英文输入兼容**：支持中文城市名（"上海"、"浦东"）、英文（"Shanghai"、"New York"）、IATA 代码（"PVG"、"JFK"）混合输入
- **7,912 个机场缓存**：覆盖全球 99% 有 IATA 代码的机场，含中英文名称、别名对照（100% 中文翻译覆盖，AI检查和翻译，如有错误请帮忙更正）
- **多源容错**：ADSB.lol 透明备份、数据源失败时用户友好的降级提示
- **字段互补合并**：同航班号的多源结果自动合并，已有字段不覆盖，缺失字段从其他来源补入
- **并发查询**：ThreadPoolExecutor 多数据源同时查询，全局超时控制，超时返回部分结果
- **机场数据自动更新**：支持定期自动更新、手动更新、永久关闭三种模式（仅接口，暂不支持自动更新数据，可手动更新）
- **双输出格式**：表格（终端友好）和 JSON（程序集成）
- **单配置文件驱动**：`config.yaml` 控制数据源开关、超时、优先级、输出格式
- **零 API Key 依赖**：无需注册任何账号或提供 API Key 即可使用全部核心功能

## 快速开始



### 安装（OpenClaw）

技能文件 SKIL.md (中文）  SKILL_EN.md(英文）
技能市场安装

```bash
clawclub install flyclaw
```
或告知小龙虾本github地址让它帮忙自动安装

### 安装（非OpenClaw方式）

```bash
# 创建 conda 环境
conda create -n flyclaw python=3.11 -y
conda activate flyclaw

# 安装依赖
pip install -r requirements.txt

# 可选：安装 fli 库以启用 Google Flights 数据源
pip install flights
```
### 环境要求

- Python 3.11+
- conda 环境（推荐）

### 配置

默认配置文件 `config.yaml` 已包含推荐值，通常无需修改即可使用：

```yaml
sources:
  fr24:
    enabled: true
    priority: 1
    timeout: 10
  google_flights:
    enabled: true
    priority: 2
    timeout: 15
    serpapi_key: ""  # 留空跳过 SerpAPI；填入 Key 自动启用
  airplanes_live:
    enabled: true
    priority: 3
    timeout: 8

cache:
  dir: cache
  airport_update_days: 99999  # 自动更新间隔（天）；99999 = 关闭；0 = 禁用
  airport_update_url: ""   # 自定义更新 URL；空 = 使用内置默认

query:
  timeout: 20      # 全局查询超时（秒）
  return_time: 12  # 智能返回时间（秒）；0 = 禁用
  route_relay: true           # 绕行开关：自动查价格
  relay_timeout_factor: 2     # 超时系数

output:
  format: table  # table / json
  language: both  # cn / en / both
```

### 使用示例

```bash
# 按航班号查询（三源并发）
conda run -n flyclaw python flyclaw.py query --flight CA981

# 按航线搜索（含价格）——城市级搜索自动覆盖所有机场
conda run -n flyclaw python flyclaw.py search --from 上海 --to 纽约 --date 2026-04-01
# 上海(PVG+SHA) → 纽约(JFK+EWR+LGA) 所有机场组合

# 往返搜索
conda run -n flyclaw python flyclaw.py search --from PVG --to LAX --date 2026-04-15 --return 2026-04-25

# 商务舱 + 2 人
conda run -n flyclaw python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --cabin business -a 2

# 直飞 + 按价格排序 + JSON 输出
conda run -n flyclaw python flyclaw.py search --from PVG --to NRT --date 2026-04-15 --stops 0 --sort cheapest -o json

# 包含经停航班
conda run -n flyclaw python flyclaw.py search --from PVG --to JFK --date 2026-04-15 --stops any

# 关闭绕行查价
conda run -n flyclaw python flyclaw.py query --flight CA981 --no-relay

# 英文输入同样支持
conda run -n flyclaw python flyclaw.py search --from Shanghai --to "New York" --date 2026-04-01

# 详细模式（显示数据来源和舱位）
conda run -n flyclaw python flyclaw.py query --flight CA981 -v

# 自定义超时
conda run -n flyclaw python flyclaw.py query --flight CA981 --timeout 10 --return-time 5

# 更新机场数据
conda run -n flyclaw python flyclaw.py update-airports --url http://example.com/airports.json
```

### 搜索参数

| 参数 | 短标志 | 默认值 | 说明 |
|------|--------|-------|------|
| `--from` | — | （必填） | 出发地（IATA/中文/英文） |
| `--to` | — | （必填） | 目的地 |
| `--date` | `-d` | — | 出行日期 YYYY-MM-DD |
| `--return` | `-r` | — | 返程日期（启用往返搜索） |
| `--adults` | `-a` | 1 | 成人旅客数 |
| `--children` | — | 0 | 儿童旅客数 |
| `--infants` | — | 0 | 婴儿旅客数 |
| `--cabin` | `-C` | economy | 舱位：economy/premium/business/first |
| `--limit` | `-l` | 智能默认 | 最大结果数（直飞 99，含中转 20，用户覆盖优先） |
| `--sort` | `-s` | — | 排序：cheapest/fastest/departure/arrival |
| `--stops` | — | 0 | 经停控制：0=直飞/1/2/any=不限 |

### 输出示例

```
  CA981  (Air China)
  北京(PEK) → 纽约(JFK)
  Departure: 2026-04-01 13:00    Arrival: 2026-04-01 14:30
  Price: $856 | Stops: 0 | Duration: 840min
```

往返搜索输出：
```
  CA981  (Air China)
  上海(PVG) → 洛杉矶(LAX)
  Departure: 2026-04-15 10:00    Arrival: 2026-04-15 14:00
  Price: $2400 (round-trip) | Stops: 0 | Duration: 840min
  ── Return ──
  CA982  (Air China)
  Departure: 2026-04-25 18:00    Arrival: 2026-04-26 22:00
  Stops: 0 | Duration: 900min
```

## 数据来源

FlyClaw 基于多源聚合架构，通过开源库及免费公开 API 获取数据。无需注册账号或提供 API Key。使用相关数据请遵守当地法律和规定。


## 依赖及许可证

| 依赖 | 版本要求 | 许可证 | 用途 |
|------|----------|--------|------|
| requests | >=2.28.0 | Apache-2.0 | HTTP 请求 |
| pyyaml | >=6.0 | MIT | YAML 配置解析 |
| flights (fli) | latest | MIT | Google Flights 查询（可选） |

Python 版本要求：3.11+


## 免责声明

- 本工具基于多源聚合架构，通过开源库及免费公开 API 获取数据
- **无需注册账号或提供任何 API Key** 即可使用全部核心功能
- 本工具仅供学习研究用途，请遵守当地法律法规
- Google Flights 在部分地区（如中国大陆）可能不可用
- 中国国内航班信息可能不完整，受限于免费公开数据源的覆盖范围
- 程序不收集、不存储、不传输任何用户个人信息

## License

[Apache-2.0](LICENSE) |  nuaa02@gmail.com
