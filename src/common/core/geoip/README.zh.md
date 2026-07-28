GeoIP 插件负责管理 MaxMind 格式的数据库（`.mmdb`），BunkerWeb 使用这些数据库解析每个客户端 IP 的**国家/地区**、**ASN**以及可选的**城市**。这些查询结果会提供给 [Country](#country) 插件、黑名单和灰名单的 ASN 规则、[Web UI](web-ui.md) 中显示的报告，以及 `$bw_country`、`$bw_asn_number`、`$bw_asn_org` 和 `$bw_city` 日志变量。

默认情况下无需任何配置：国家/地区和 ASN 数据库来自免费的 [DB-IP Lite](https://db-ip.com/db/lite.php) 版本，并每日更新。只有在需要使用**其他提供商**（MaxMind 订阅或您自行提供的数据库）时，才需要配置此插件。

**工作原理：**

1. 三个每日任务分别更新国家/地区、ASN 和城市数据库。
2. 每个任务都按照简单的优先级选择来源：首先使用您自己的文件，其次是 MaxMind，最后是 DB-IP。
3. 下载的文件会被解压、打开并检查，以确认其类型与请求的数据库一致。
4. 如果它与缓存副本不同，系统会存储该文件并分发到每个 BunkerWeb 实例，各实例通过重新加载来使用它。
5. 查询失败绝不会阻止请求：国家/地区会变为 `unknown`，流量仍会正常处理。

### 来源优先级

没有用于选择“来源”的设置。优先级仅取决于您填写了哪些设置：

| 优先级 | 使用条件                                      | 来源                                                    |
| ------ | --------------------------------------------- | ------------------------------------------------------- |
| 1      | 已设置 `GEOIP_<KIND>_MMDB`                   | 您自己的文件或 URL                                      |
| 2      | 已设置 `MAXMIND_LICENSE_KEY`                  | MaxMind（免费的 GeoLite2 或您的 GeoIP2 订阅）           |
| 3      | 未设置任何内容                                | DB-IP Lite（默认）                                      |

设置 `MAXMIND_LICENSE_KEY` 会将**全部三个**数据库切换到 MaxMind。不支持为不同数据库混用提供商；如果需要让某个特定数据库来自其他来源，请使用 `GEOIP_<KIND>_MMDB`。

### 配置设置

| 设置                     | 默认值 | 上下文 | 多个 | 描述                                                                                                                                                                  |
| ------------------------ | ------ | ------ | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `MAXMIND_LICENSE_KEY`    |        | global | 否   | **MaxMind 许可证密钥：** 设置后，国家/地区、ASN 和城市数据库将从 MaxMind 而不是 DB-IP 下载。                                                                           |
| `MAXMIND_ACCOUNT_ID`     |        | global | 否   | **MaxMind 账户 ID：** 可选但建议提供；如果未提供，系统将使用已弃用的仅密钥端点，而该端点会在 URL 中携带密钥。                                                          |
| `GEOIP_CITY`             | `no`   | global | 否   | **城市数据库：** 下载城市数据库。其体积远大于其他数据库（解压后为 125 MB），且不包含在镜像中。                                                                         |
| `GEOIP_COUNTRY_MMDB`     |        | global | 否   | **自定义国家/地区数据库：** worker 可读取的绝对路径或 `http(s)` URL。优先级高于 MaxMind 和 DB-IP。                                                                     |
| `GEOIP_ASN_MMDB`         |        | global | 否   | **自定义 ASN 数据库：** worker 可读取的绝对路径或 `http(s)` URL。优先级高于 MaxMind 和 DB-IP。                                                                         |
| `GEOIP_CITY_MMDB`        |        | global | 否   | **自定义城市数据库：** worker 可读取的绝对路径或 `http(s)` URL。优先级高于 MaxMind 和 DB-IP。                                                                          |

!!! warning "城市数据库体积很大"
    DB-IP City Lite 是一个 **59 MB 的下载文件，解压后达到 125 MB**；相比之下，国家/地区数据库为 7.8 MB，ASN 数据库为 9.2 MB。与后两者不同，它**不包含在镜像中**：首次成功下载前不会有任何数据可用，下载失败只会让 `$bw_city` 保持为空。

    由于任务缓存会存储在数据库中并分发到每个实例，启用它会带来实际影响：

    - 对于 MariaDB 和 MySQL，请将 `max_allowed_packet` 提高到 125 MB 以上，否则任务会失败（默认值为 64 MB）。发生这种情况时，任务会在日志中明确说明。
    - worker 在存储数据库时会将其保留在内存中，因此请相应提高 `WORKER_MAX_MEMORY_KB` 和 worker 容器的内存限制。
    - 每次配置更改都会将缓存重新分发到每个实例，因此请规划好带宽和磁盘空间。

    如果您拥有许可证密钥，MaxMind 的 `GeoLite2-City` 体积会明显更小。

!!! info "获取 MaxMind 许可证密钥"
    在 [maxmind.com](https://www.maxmind.com/en/geolite2/signup) 创建免费账户，然后生成许可证密钥，**并**记下您的账户 ID。两者都会显示在账户门户中。GeoLite2 每周更新两次，而 DB-IP Lite 每月更新一次。

    新创建的密钥可能需要一些时间才能激活；在此之前，下载会以 `401` 失败。

!!! warning "请提供账户 ID，而不只是密钥"
    账户 ID 仅出于向后兼容的原因而设为可选。不提供它会带来两个问题：

    - MaxMind 的仅密钥端点已被**弃用**，可能会被撤下。
    - 它会将您的许可证密钥放在 **URL 查询字符串中**，从而记录在路径上任何正向代理的访问日志中。提供账户 ID 后，凭据会改为通过 `Authorization` 请求头传输。

    无论采用哪种方式，BunkerWeb 都会从自己的日志中移除密钥，包括下载错误消息，但它无法从第三方日志中移除密钥。

!!! info "使用您自己的数据库"
    任何 MaxMind 格式的 `.mmdb` 都可以使用，包括商业版 GeoIP2 和内部数据库，只要它采用标准字段名（`country.iso_code`、`autonomous_system_number`、`autonomous_system_organization`、`city.names.en`）。

    本地路径必须可由 **worker** 读取，而不是由 BunkerWeb 实例读取：worker 只读取一次，然后进行分发。支持普通 `.mmdb`、`.mmdb.gz` 和 `.tar.gz` 文件。

    文件会在存储或发送到任何位置**之前**被打开并检查类型。因此，如果设置指向了错误类型的数据库，或指向了根本不是数据库的内容，系统会明确报错，而不是悄无声息地不返回任何结果。

    URL 应优先使用 `https`。地理位置会影响允许和阻止决策，因此在传输过程中被替换的数据库可能会让流量看似来自您允许的国家/地区。

### 配置示例

=== "默认（DB-IP）"

    无需配置。国家/地区和 ASN 数据库每天从 DB-IP Lite 更新：

    ```yaml
    # no settings needed
    ```

=== "MaxMind GeoLite2"

    将所有数据库切换到 MaxMind：

    ```yaml
    MAXMIND_ACCOUNT_ID: "123456"
    MAXMIND_LICENSE_KEY: "your-license-key"
    ```

=== "添加城市数据"

    在默认来源的基础上启用城市数据库：

    ```yaml
    GEOIP_CITY: "yes"
    ```

=== "自有数据库"

    使用挂载到 worker 中的商业数据库，并让其余数据库继续使用 DB-IP：

    ```yaml
    GEOIP_COUNTRY_MMDB: "/data/geoip/GeoIP2-Country.mmdb"
    ```

=== "内部镜像"

    从内部 HTTP 镜像获取所有数据库：

    ```yaml
    GEOIP_COUNTRY_MMDB: "https://mirror.example.com/geoip/country.mmdb"
    GEOIP_ASN_MMDB: "https://mirror.example.com/geoip/asn.mmdb"
    GEOIP_CITY: "yes"
    GEOIP_CITY_MMDB: "https://mirror.example.com/geoip/city.mmdb.gz"
    ```

### 许可证

- **DB-IP Lite** 数据库采用 [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) 许可证发布，并要求注明 DB-IP.com。
- **GeoLite2** 数据库受 MaxMind 最终用户许可协议约束，创建密钥时即表示您接受该协议。BunkerWeb 绝不会重新分发这些数据库：它们使用您自己的凭据下载，因此镜像中不包含任何 MaxMind 数据库。
