import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

class SubscriptionDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, logger, entry):
        self.hass = hass
        self.entry = entry
        self.auth_token = entry.data.get("auth_token")
        
        # 直接使用默认平台配置（云洞数据）
        self.platform = PLATFORMS["default"]
        
        # 默认扫描间隔为30分钟
        scan_interval = entry.options.get("scan_interval", 1800)
        
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        try:
            # 获取订阅数据
            data = await self._async_fetch_subscription_data()
            return data
        except Exception as e:
            raise UpdateFailed(f"数据更新失败: {str(e)}") from e

    async def _async_fetch_subscription_data(self):
        # 验证API URL是否存在
        if not self.platform["api_url"]:
            raise UpdateFailed("API URL未配置")
        
        # 根据平台配置构建请求头，替换token占位符
        headers = {}
        for key, value in self.platform["headers"].items():
            # 替换token占位符
            try:
                headers[key] = value.format(token=self.auth_token)
            except Exception as e:
                # 如果格式化失败，直接使用原始值
                _LOGGER.error(f"Token格式化失败: {str(e)}")
                headers[key] = value
        
        # 添加详细的日志记录以调试请求
        _LOGGER.debug(f"请求URL: {self.platform['api_url']}")
        _LOGGER.debug(f"请求头: {headers}")
        
        platform_name = self.platform.get("name", "未知平台")
        _LOGGER.info(f"正在尝试连接{platform_name}平台，使用增强的浏览器请求头和{self.platform.get('method', 'GET').upper()}方法")
        _LOGGER.debug(f"请求使用的token长度: {len(self.auth_token)} 字符")
        
        try:
            # 使用aiohttp实现请求
            async with aiohttp.ClientSession() as session:
                # 根据平台配置选择请求方法
                request_method = self.platform.get("method", "GET").upper()
                _LOGGER.debug(f"使用{request_method}方法请求API")
                
                try:
                    # 根据方法选择请求函数
                    if request_method == "POST":
                        async with session.post(self.platform["api_url"], headers=headers, json={}) as response:
                            _LOGGER.debug(f"响应状态码: {response.status}")
                            _LOGGER.debug(f"响应头: {dict(response.headers)}")
                            
                            response.raise_for_status()
                            raw_data = await response.json()
                            _LOGGER.debug(f"响应数据: {raw_data}")
                        
                            # 提取实际的订阅数据
                            subscription_data = raw_data.get('data', {})
                            
                            # 计算相关指标
                            processed_data = self._process_subscription_data(subscription_data)
                            return processed_data
                    else:
                        async with session.get(self.platform["api_url"], headers=headers) as response:
                            _LOGGER.debug(f"响应状态码: {response.status}")
                            _LOGGER.debug(f"响应头: {dict(response.headers)}")
                            
                            response.raise_for_status()
                            raw_data = await response.json()
                            _LOGGER.debug(f"响应数据: {raw_data}")
                        
                            # 提取实际的订阅数据
                            subscription_data = raw_data.get('data', {})
                            
                            # 计算相关指标
                            processed_data = self._process_subscription_data(subscription_data)
                            return processed_data
                except aiohttp.ClientResponseError as e:
                    _LOGGER.error(f"API请求错误: {str(e)}")
                    if hasattr(e, 'headers'):
                        _LOGGER.error(f"错误响应头: {dict(e.headers)}")
                    raise UpdateFailed(f"数据更新失败: {str(e)}") from e
                except Exception as e:
                    _LOGGER.error(f"数据获取过程中发生未知错误: {str(e)}")
                    raise UpdateFailed(f"数据更新失败: {str(e)}") from e
        except Exception as e:
            _LOGGER.error(f"数据获取过程中发生未知错误: {str(e)}")
            raise UpdateFailed(f"数据更新失败: {str(e)}") from e
    
    def _process_subscription_data(self, data):
        """处理原始订阅数据，计算并格式化所需的指标"""
        try:
            # 提取基础数据
            plan = data.get('plan', {})
            
            # 流量转换（字节转GB）
            u = data.get('u', 0)  # 上传流量
            d = data.get('d', 0)  # 下载流量
            used_traffic = (u + d) / (1024 ** 3)  # 转换为GB
            
            # 尝试从data中获取transfer_enable，如果不存在则从plan中获取
            total_transfer = data.get('transfer_enable', 0)
            if total_transfer == 0:
                # 从plan中获取的transfer_enable可能已经是GB单位
                plan_transfer = plan.get('transfer_enable', 0)
                if plan_transfer > 0 and plan_transfer < 1000:  # 如果是小数字，可能已经是GB
                    total_traffic = plan_transfer
                else:
                    total_traffic = plan_transfer / (1024 ** 3)  # 转换为GB
            else:
                total_traffic = total_transfer / (1024 ** 3)  # 转换为GB
            
            usage_percentage = round((used_traffic / total_traffic) * 100, 2) if total_traffic > 0 else 0
            
            # 计算剩余天数
            expired_at = data.get('expired_at', 0)
            if expired_at > 0:
                expire_date = datetime.fromtimestamp(expired_at)
                days_remaining = (expire_date - datetime.now()).days
                expire_date_str = expire_date.strftime('%Y-%m-%d')
            else:
                expire_date_str = "未知"
                days_remaining = 0
            
            # 提取订阅类型
            subscription_type = plan.get('name', '未知')
            
            # 从API响应中提取token（如果有），然后使用正确的域名构造URL
            # 检查data中是否有subscribe_url或token字段
            api_subscribe_url = data.get('subscribe_url', '')
            
            if api_subscribe_url:
                # 移除API响应中可能存在的反斜杠转义
                clean_url = api_subscribe_url.replace('\\', '')
                
                # 尝试从URL中提取token参数
                import urllib.parse
                parsed_url = urllib.parse.urlparse(clean_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                # 获取token值（如果存在）
                if 'token' in query_params and query_params['token']:
                    api_token = query_params['token'][0]
                    # 使用正确的域名和API返回的token
                    subscribe_url = f"{self.platform['subscribe_url_base']}?token={api_token}"
                else:
                    # 如果无法提取token，使用配置的token
                    subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
            else:
                # 如果API没有返回subscribe_url，检查是否直接返回了token字段
                api_token = data.get('token', '')
                if api_token:
                    subscribe_url = f"{self.platform['subscribe_url_base']}?token={api_token}"
                else:
                    # 动态生成subscribe_url，包含用户的token
                    subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
            
            # 返回处理后的数据
            return {
                "subscriptionType": subscription_type,
                "expireDate": expire_date_str,
                "daysRemaining": days_remaining,
                "resetDays": data.get('reset_day', 0),
                "used": used_traffic,
                "total": total_traffic,
                "usage_percentage": usage_percentage,
                "onlineDevices": "∞",  # 从用户数据看是不限制设备数量
                "email": data.get('email', '未知'),
                "plan_id": data.get('plan_id', 0),
                "subscribe_url": subscribe_url,
                "raw_data": data
            }
        except Exception as e:
            _LOGGER.error(f"数据处理错误: {str(e)}")
            # 返回默认数据，避免组件崩溃
            # 构建subscribe_url，尝试从data中提取token（如果有）
            try:
                # 检查data中是否有subscribe_url或token字段
                api_subscribe_url = data.get('subscribe_url', '')
                
                if api_subscribe_url:
                    # 移除API响应中可能存在的反斜杠转义
                    clean_url = api_subscribe_url.replace('\\', '')
                    
                    # 尝试从URL中提取token参数
                    import urllib.parse
                    parsed_url = urllib.parse.urlparse(clean_url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    
                    # 获取token值（如果存在）
                    if 'token' in query_params and query_params['token']:
                        api_token = query_params['token'][0]
                        # 使用正确的域名和API返回的token
                        subscribe_url = f"{self.platform['subscribe_url_base']}?token={api_token}"
                    else:
                        # 如果无法提取token，使用配置的token
                        subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
                else:
                    # 如果API没有返回subscribe_url，检查是否直接返回了token字段
                    api_token = data.get('token', '')
                    if api_token:
                        subscribe_url = f"{self.platform['subscribe_url_base']}?token={api_token}"
                    else:
                        # 动态生成subscribe_url，包含用户的token
                        subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
            except:
                # 如果处理过程中出错，回退到使用配置的token
                subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
            
            return {
                "subscriptionType": "未知",
                "expireDate": "未知",
                "daysRemaining": 0,
                "resetDays": 0,
                "used": 0,
                "total": 0,
                "usage_percentage": 0,
                "onlineDevices": "∞",
                "email": "未知",
                "plan_id": 0,
                "subscribe_url": subscribe_url,
                "raw_data": data
            }

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # 创建协调器实例，传递完整的配置条目
    coordinator = SubscriptionDataUpdateCoordinator(
        hass, _LOGGER, entry
    )
    
    # 初始化协调器数据
    await coordinator.async_config_entry_first_refresh()
    
    # 存储协调器实例
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = all(
        await asyncio.gather(
            hass.config_entries.async_forward_entry_unload(entry, "sensor"),
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok