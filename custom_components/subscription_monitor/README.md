# 云洞数据订阅监控集成

这个集成允许你在Home Assistant中监控[云洞数据平台](https://yundong.xn--xhq8sm16c5ls.com/#/register?code=NXp1KlCC)的网络服务订阅信息，包括会员类型、到期时间、流量使用情况等。

## 功能特点

- 监控订阅到期时间
- 显示已用流量和总流量
- 计算流量使用百分比
- 显示剩余天数
- 显示套餐信息

## 安装方法

### 通过 HACS (推荐)

1. 打开 HACS
2. 点击 `集成`
3. 点击右上角的三点菜单，选择 `自定义存储库`
4. 添加存储库 URL (https://github.com/chaosl1996/subscription_monitor) 并选择类别为 `集成`
5. 搜索并安装 `云洞数据订阅监控` 集成

### 手动安装

1. 下载此存储库的 ZIP 文件
2. 解压并将 `subscription_monitor` 文件夹复制到 Home Assistant 的 `config/custom_components/` 目录
3. 重启 Home Assistant

## 配置方法

安装完成后，可以通过 Home Assistant 的 UI 进行配置：

1. 进入 `配置` > `集成` > `添加集成`
2. 搜索并选择 `云洞数据订阅监控`
3. 输入你的云洞数据平台的邮箱和密码
4. 完成配置

集成会自动使用你的邮箱和密码登录云洞数据平台获取认证信息。

### 配置选项

添加集成后，你可以通过以下步骤修改配置选项：

1. 进入 `配置` > `集成`
2. 找到并点击 `云洞数据订阅监控` 集成
3. 点击 `配置` 按钮
4. 修改数据刷新间隔（范围：60-3600秒，默认：300秒）
5. 保存更改

配置更改将立即生效，无需重启Home Assistant。

## 实体属性

集成添加后，将在 Home Assistant 中创建以下实体：

- `sensor.daily_subscription` - 主传感器，显示订阅状态

传感器包含以下属性：

- `subscription_type` - 订阅类型
- `expire_date` - 到期日期
- `days_remaining` - 剩余天数
- `reset_days` - 下次重置流量天数
- `used_traffic` - 已用流量 (GB)
- `total_traffic` - 总流量 (GB)
- `usage_percentage` - 流量使用百分比
- `online_devices` - 在线设备数量
- `node_type` - 节点类型
- `email` - 绑定邮箱
- `plan_id` - 套餐ID

## 已知问题

- 如果 API 发生变化，可能需要更新集成
- 网络连接问题可能导致数据更新失败

## 故障排除

1. 确保 Token 格式正确且有效
2. 检查网络连接是否正常
3. 查看 Home Assistant 日志获取详细错误信息

## 更新日志

### 1.4.0
- 添加SensorStateClass.MEASUREMENT状态类，使实体能够在历史记录中显示图表曲线
- 保持单位为百分比(%)，确保状态返回纯数字值

### 1.3.0
- 添加配置选项功能，允许用户自定义数据刷新间隔
- 修复OptionsFlow类中的TypeError错误
- 移除弃用的self.config_entry设置，符合Home Assistant 2025.12标准
- 统一默认刷新间隔为5分钟
- 添加配置选项更新处理机制

### 1.2.0
- 修复API请求认证问题
- 优化token刷新机制
- 修复403 Forbidden错误
- 优化实体状态显示，使用Home Assistant标准单位属性而非字符串后缀
- 修复配置文档，使其与实际实现一致

### 1.1.0
- 专注云洞数据平台支持
- 移除其他平台支持
- 简化配置流程
- 优化代码结构
- 简化依赖要求

### 1.0.0
- 初始版本发布
- 支持订阅信息监控
- 支持流量统计
- 支持到期时间监控
## 贡献
欢迎提交问题报告和改进建议。