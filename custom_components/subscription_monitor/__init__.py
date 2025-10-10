import asyncio
import logging
from datetime import datetime, timedelta
import aiohttp
import json
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

class SubscriptionDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, logger, entry):
        self.hass = hass
        self.entry = entry
        self.auth_token = entry.data.get("auth_token")
        self.email = entry.data.get("email")
        self.password = entry.data.get("password")
        self.auth_data = entry.data.get("auth_data", "")
        self.token_expiry = entry.data.get("token_expiry")
        
        # 添加最后刷新时间，避免短时间内频繁刷新
        self.last_refresh_time = None
        
        # 直接使用默认平台配置（云洞数据）
        self.platform = PLATFORMS["default"]
        
        # 默认扫描间隔为5分钟（300秒）
        scan_interval = entry.options.get("scan_interval", 300)
        
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
    
    async def _async_update_data(self):
        try:
            # 检查并刷新token
            await self._async_check_and_refresh_token()
            
            # 获取订阅数据
            data = await self._async_fetch_subscription_data()
            return data
        except Exception as e:
            # 如果是认证错误，尝试刷新token后重试一次
            if "认证" in str(e) or "Unauthorized" in str(e) or "401" in str(e):
                _LOGGER.warning(f"认证失败，尝试刷新token: {str(e)}")
                try:
                    # 验证是否在短时间内已经尝试过刷新
                    if self.last_refresh_time:
                        time_since_last_refresh = (datetime.now() - self.last_refresh_time).total_seconds()
                        if time_since_last_refresh < 300:  # 5分钟内不重复尝试刷新
                            _LOGGER.warning(f"5分钟内已尝试过刷新token，跳过此次刷新")
                            raise UpdateFailed(f"认证失败且短时间内已刷新过token") from e
                    
                    await self._async_refresh_token()
                    data = await self._async_fetch_subscription_data()
                    return data
                except Exception as refresh_e:
                    raise UpdateFailed(f"刷新token后重试失败: {str(refresh_e)}") from refresh_e
            raise UpdateFailed(f"数据更新失败: {str(e)}") from e
    
    async def _async_check_and_refresh_token(self):
        """检查token是否需要刷新"""
        # 如果没有邮箱和密码，无法自动刷新
        if not self.email or not self.password:
            _LOGGER.debug("没有邮箱和密码，无法自动刷新token")
            return
        
        # 检查是否在短时间内已经刷新过，避免频繁请求
        if self.last_refresh_time:
            time_since_last_refresh = (datetime.now() - self.last_refresh_time).total_seconds()
            if time_since_last_refresh < 3600:  # 1小时内不重复检查刷新
                _LOGGER.debug(f"1小时内已刷新过token，跳过此次检查")
                return
        
        # 检查token是否过期或即将过期
        try:
            if self.token_expiry:
                expiry_time = datetime.strptime(self.token_expiry, '%Y-%m-%d %H:%M:%S')
                # 如果token将在48小时内过期，或者已经过期，则刷新
                time_difference = expiry_time - datetime.now()
                if time_difference.total_seconds() < 172800:  # 48小时 = 172800秒
                    _LOGGER.info(f"Token将在{time_difference.total_seconds()/3600:.1f}小时后过期，准备刷新")
                    await self._async_refresh_token()
        except Exception as e:
            _LOGGER.error(f"检查token过期时间失败: {str(e)}")
            # 如果解析失败，检查是否在短时间内已经尝试过刷新
            if not self.last_refresh_time or (datetime.now() - self.last_refresh_time).total_seconds() > 3600:
                _LOGGER.info("Token过期时间解析失败，尝试刷新")
                await self._async_refresh_token()

    async def _async_refresh_token(self):
        """刷新token"""
        try:
            # 检查5分钟内是否已经尝试过刷新token
            now = datetime.now()
            if hasattr(self, 'last_refresh_time') and self.last_refresh_time:
                time_diff = (now - self.last_refresh_time).total_seconds() / 60
                if time_diff < 5:
                    _LOGGER.warning(f"5分钟内已尝试刷新token，跳过本次刷新")
                    raise UpdateFailed("5分钟内已尝试刷新token")
            
            # 发送登录请求获取新token
            platform = self.platform
            login_url = platform.get("login_url", "")
            login_headers = platform.get("login_headers", {})
            
            # 确保login_headers的所有键都是字符串
            login_headers = {str(k): v for k, v in login_headers.items()}
            
            if not login_url:
                _LOGGER.error("登录URL未配置，无法刷新token")
                raise UpdateFailed("登录URL未配置")
            
            # 构建登录请求数据（使用字典格式，而不是字符串）
            form_data = {
                'email': self.email,
                'password': self.password
            }
            
            _LOGGER.debug(f"发送刷新token请求到: {login_url}")
            _LOGGER.debug(f"刷新token请求头: {login_headers}")
            _LOGGER.debug(f"刷新token请求数据: {form_data}")
            
            # 发送登录请求
            async with aiohttp.ClientSession() as session:
                try:
                    # 发送登录请求，使用data参数而不是json参数以匹配用户示例
                    async with session.post(login_url, headers=login_headers, data=form_data) as response:
                        _LOGGER.debug(f"刷新token请求响应状态码: {response.status}")
                        _LOGGER.debug(f"刷新token响应头: {dict(response.headers)}")
                        
                        # 尝试获取响应内容（无论状态码如何）
                        response_text = await response.text()
                        _LOGGER.debug(f"刷新token响应原始内容: {response_text}")
                        
                        if response.status == 200:
                            try:
                                # 使用已经读取的响应文本进行JSON解析
                                _LOGGER.debug(f"原始JSON响应: {response_text}")
                                try:
                                    data = json.loads(response_text)
                                    # 确保解析后的数据中所有键都是字符串
                                    if isinstance(data, dict):
                                        data = {str(k): v for k, v in data.items()}
                                except Exception as json_e:
                                    _LOGGER.error(f"JSON解析错误: {str(json_e)}")
                                    raise UpdateFailed(f"刷新token失败: JSON解析错误") from json_e
                                _LOGGER.debug(f"刷新token响应解析后数据: {data}")
                                
                                # 检查是否获取到token，考虑多种可能的数据结构
                                if data:
                                    # 检查常见的token字段位置，特别处理云洞平台返回格式
                                    new_token = None
                                    new_auth_data = None
                                    
                                    # 检查data.token结构，根据用户示例特别处理
                                    if isinstance(data, dict):
                                        # 云洞平台特定格式：{"data":{"token":"...", "is_admin":0, "auth_data":"..."}}
                                        if "data" in data and isinstance(data["data"], dict):
                                            if "token" in data["data"]:
                                                new_token = data["data"]["token"]
                                                # 对于云洞平台，auth_data是一个JWT令牌字符串，而不是字典
                                                if "auth_data" in data["data"]:
                                                    # 存储原始auth_data字符串
                                                    self.auth_data = data["data"]["auth_data"]
                                                # 但在updated_data中，我们存储整个data字典
                                                new_auth_data = data["data"]
                                        # 兼容其他可能的格式
                                        elif "token" in data:
                                            new_token = data["token"]
                                            new_auth_data = data
                                        elif "result" in data and isinstance(data["result"], dict):
                                            if "token" in data["result"]:
                                                new_token = data["result"]["token"]
                                                new_auth_data = data["result"]
                                
                                if new_token:
                                    # 更新token和过期时间
                                    self.auth_token = new_token
                                    # 对于云洞平台，我们已经在上面直接设置了self.auth_data为JWT字符串
                                    # 这里只需要确保new_auth_data在存储到配置条目时键是字符串
                                    if not hasattr(self, 'auth_data') or self.auth_data is None:
                                        # 如果上面没有特殊处理，则使用默认逻辑
                                        if isinstance(new_auth_data, dict):
                                            self.auth_data = {str(key): value for key, value in new_auth_data.items()}
                                        else:
                                            self.auth_data = new_auth_data or ""
                                    self.token_expiry = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    # 更新配置条目
                                    updated_data = dict(self.entry.data)
                                    updated_data["auth_token"] = new_token
                                    # 存储到配置条目时也确保auth_data键是字符串
                                    if isinstance(new_auth_data, dict):
                                        updated_data["auth_data"] = {str(key): value for key, value in new_auth_data.items()}
                                    else:
                                        updated_data["auth_data"] = new_auth_data or ""
                                    updated_data["token_expiry"] = self.token_expiry
                                    
                                    # 更新配置条目
                                    try:
                                        # 检查async_update_entry是否是协程函数
                                        update_method = self.hass.config_entries.async_update_entry
                                        if asyncio.iscoroutinefunction(update_method):
                                            # 如果是协程函数，使用await
                                            await update_method(self.entry, data=updated_data)
                                        else:
                                            # 如果不是协程函数，直接调用
                                            update_method(self.entry, data=updated_data)
                                        _LOGGER.info("配置条目更新成功")
                                    except Exception as e:
                                        _LOGGER.error(f"配置条目更新失败: {str(e)}")
                                        # 即使更新配置条目失败，token仍然有效，继续使用
                                    
                                    # 更新最后刷新时间
                                    self.last_refresh_time = now
                                    
                                    _LOGGER.info("token刷新成功")
                                    return True
                                else:
                                    _LOGGER.error(f"刷新token成功但未获取到token: {data}")
                                    # 记录刷新时间，避免立即重试
                                    self.last_refresh_time = now
                                    raise UpdateFailed(f"刷新token失败: 未获取到token")
                            except Exception as e:
                                _LOGGER.error(f"解析刷新token响应JSON失败: {str(e)}")
                                _LOGGER.debug(f"无法解析的响应内容: {response_text}")
                                # 记录刷新时间，避免立即重试
                                self.last_refresh_time = now
                                raise UpdateFailed(f"刷新token失败: 解析响应失败") from e
                        else:
                            _LOGGER.error(f"刷新token请求失败: 状态码{response.status}, 响应内容: {response_text}")
                            # 对于非200响应，也记录刷新时间，避免立即重试
                            self.last_refresh_time = now
                            raise UpdateFailed(f"刷新token请求失败: 状态码{response.status}")
                except aiohttp.ClientError as e:
                    _LOGGER.error(f"刷新token请求网络错误: {str(e)}")
                    # 记录刷新时间，避免立即重试
                    self.last_refresh_time = now
                    raise UpdateFailed(f"刷新token失败: 网络错误") from e
        except UpdateFailed:
            # 重新抛出UpdateFailed异常，让调用者处理
            raise
        except Exception as e:
            _LOGGER.error(f"刷新token过程中发生未知错误: {str(e)}")
            # 即使发生错误，也记录刷新时间，避免立即重试
            self.last_refresh_time = now
            raise UpdateFailed(f"刷新token失败: {str(e)}") from e

    async def _async_fetch_subscription_data(self):
        # 验证API URL是否存在
        if not self.platform["api_url"]:
            raise UpdateFailed("API URL未配置")
        
        # 构建请求头，云洞平台特殊处理
        headers = {}
        
        # 检查是否有平台特定的请求头模板
        if "headers" in self.platform:
            for key, value in self.platform["headers"].items():
                # 替换token占位符
                try:
                    # 根据用户提供的云洞平台API示例，Authorization头应使用auth_data（JWT字符串）
                    if key.lower() == "authorization":
                        # 优先使用auth_data（JWT字符串）而不是token
                        if hasattr(self, 'auth_data') and self.auth_data:
                            headers[key] = self.auth_data
                        else:
                            # 检查模板是否包含"Bearer"前缀
                            if "Bearer" in value:
                                headers[key] = value.format(token=self.auth_token)
                            else:
                                headers[key] = self.auth_token
                    else:
                        headers[key] = value.format(token=self.auth_token)
                except Exception as e:
                    # 如果格式化失败，直接使用原始值
                    _LOGGER.error(f"Token格式化失败: {str(e)}")
                    headers[key] = value
        
        # 云洞平台特定检查：确保Authorization头存在并且格式正确
        if "Authorization" not in headers:
            # 优先使用auth_data（JWT字符串）而不是token
            if hasattr(self, 'auth_data') and self.auth_data:
                headers["Authorization"] = self.auth_data
            elif self.auth_token:
                # 检查平台配置中是否有Authorization头的模板
                if "headers" in self.platform and "Authorization" in self.platform["headers"]:
                    headers["Authorization"] = self.platform["headers"]["Authorization"].format(token=self.auth_token)
                else:
                    headers["Authorization"] = self.auth_token
        
        # 添加详细的日志记录以调试请求
        _LOGGER.debug(f"请求URL: {self.platform['api_url']}")
        _LOGGER.debug(f"请求头: {headers}")
        _LOGGER.debug(f"Authorization头: {headers.get('Authorization', '未设置')}")
        
        platform_name = self.platform.get("name", "未知平台")
        _LOGGER.info(f"正在尝试连接{platform_name}平台，使用增强的浏览器请求头和{self.platform.get('method', 'GET').upper()}方法")
        # 添加auth_data相关的调试信息
        if hasattr(self, 'auth_data') and self.auth_data:
            _LOGGER.debug(f"请求使用的auth_data长度: {len(self.auth_data)} 字符")
            _LOGGER.debug(f"auth_data格式: {'JWT格式' if 'eyJ' in str(self.auth_data) else '其他格式'}")
        _LOGGER.debug(f"请求使用的token长度: {len(self.auth_token)} 字符")
        _LOGGER.debug(f"请求使用的完整Authorization头: {headers.get('Authorization', '未设置')}")
        
        max_retries = 2
        retry_count = 0
        
        while retry_count < max_retries:
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
                                
                                # 特殊处理401和403错误，尝试刷新token并重试
                                if response.status in (401, 403) and retry_count < max_retries - 1:
                                    _LOGGER.warning(f"收到{response.status}错误，尝试刷新token并重试")
                                    # 强制刷新token
                                    await self._async_refresh_token(force=True)
                                    # 重新构建请求头
                                    headers = {}
                                    if "headers" in self.platform:
                                        for key, value in self.platform["headers"].items():
                                            try:
                                                if key.lower() == "authorization":
                                                    # 刷新后优先使用新的auth_data
                                                    if hasattr(self, 'auth_data') and self.auth_data:
                                                        headers[key] = self.auth_data
                                                    else:
                                                        if "Bearer" in value:
                                                            headers[key] = value.format(token=self.auth_token)
                                                        else:
                                                            headers[key] = self.auth_token
                                                else:
                                                    headers[key] = value.format(token=self.auth_token)
                                            except Exception as e:
                                                _LOGGER.error(f"Token格式化失败: {str(e)}")
                                                headers[key] = value
                                    if "Authorization" not in headers:
                                        if hasattr(self, 'auth_data') and self.auth_data:
                                            headers["Authorization"] = self.auth_data
                                        elif self.auth_token:
                                            headers["Authorization"] = self.platform["headers"]["Authorization"].format(token=self.auth_token)
                                    retry_count += 1
                                    _LOGGER.debug(f"刷新token后重试请求，重试次数: {retry_count}")
                                    continue
                                
                                response.raise_for_status()
                                raw_data = await response.json()
                                _LOGGER.debug(f"响应数据: {raw_data}")
                                
                                # 确保raw_data的所有键都是字符串
                                if isinstance(raw_data, dict):
                                    raw_data = {str(k): v for k, v in raw_data.items()}
                                
                                # 提取实际的订阅数据
                                subscription_data = raw_data.get('data', {})
                                
                                # 计算相关指标
                                processed_data = self._process_subscription_data(subscription_data)
                                return processed_data
                        else:
                            async with session.get(self.platform["api_url"], headers=headers) as response:
                                _LOGGER.debug(f"响应状态码: {response.status}")
                                _LOGGER.debug(f"响应头: {dict(response.headers)}")
                                
                                # 特殊处理401和403错误，尝试刷新token并重试
                                if response.status in (401, 403) and retry_count < max_retries - 1:
                                    _LOGGER.warning(f"收到{response.status}错误，尝试刷新token并重试")
                                    # 强制刷新token
                                    await self._async_refresh_token(force=True)
                                    # 重新构建请求头
                                    headers = {}
                                    if "headers" in self.platform:
                                        for key, value in self.platform["headers"].items():
                                            try:
                                                if key.lower() == "authorization":
                                                    # 刷新后优先使用新的auth_data
                                                    if hasattr(self, 'auth_data') and self.auth_data:
                                                        headers[key] = self.auth_data
                                                    else:
                                                        if "Bearer" in value:
                                                            headers[key] = value.format(token=self.auth_token)
                                                        else:
                                                            headers[key] = self.auth_token
                                                else:
                                                    headers[key] = value.format(token=self.auth_token)
                                            except Exception as e:
                                                _LOGGER.error(f"Token格式化失败: {str(e)}")
                                                headers[key] = value
                                    if "Authorization" not in headers:
                                        if hasattr(self, 'auth_data') and self.auth_data:
                                            headers["Authorization"] = self.auth_data
                                        elif self.auth_token:
                                            headers["Authorization"] = self.platform["headers"]["Authorization"].format(token=self.auth_token)
                                    retry_count += 1
                                    _LOGGER.debug(f"刷新token后重试请求，重试次数: {retry_count}")
                                    continue
                                
                                response.raise_for_status()
                                raw_data = await response.json()
                                _LOGGER.debug(f"响应数据: {raw_data}")
                                
                                # 确保raw_data的所有键都是字符串
                                if isinstance(raw_data, dict):
                                    raw_data = {str(k): v for k, v in raw_data.items()}
                                
                                # 提取实际的订阅数据
                                subscription_data = raw_data.get('data', {})
                                
                                # 计算相关指标
                                processed_data = self._process_subscription_data(subscription_data)
                                return processed_data
                    except aiohttp.ClientResponseError as e:
                        _LOGGER.error(f"API请求错误: {str(e)}")
                        # 对403错误添加更详细的调试信息
                        if e.status == 403:
                            _LOGGER.error(f"403 Forbidden错误详情:")
                            _LOGGER.error(f"- 请求URL: {self.platform['api_url']}")
                            _LOGGER.error(f"- 请求头: {headers}")
                            _LOGGER.error(f"- Token长度: {len(self.auth_token)} 字符")
                            if hasattr(self, 'auth_data') and self.auth_data:
                                _LOGGER.error(f"- AuthData长度: {len(self.auth_data)} 字符")
                                _LOGGER.error(f"- AuthData格式: {'JWT格式' if 'eyJ' in str(self.auth_data) else '其他格式'}")
                            _LOGGER.error(f"- Authorization头: {headers.get('Authorization', '未设置')}")
                        if hasattr(e, 'headers'):
                            _LOGGER.error(f"错误响应头: {dict(e.headers)}")
                        # 如果是401/403错误并且已经重试过了，抛出异常
                        if e.status in (401, 403) and retry_count >= max_retries - 1:
                            _LOGGER.error(f"多次尝试刷新token后仍然无法授权，可能是token无效或平台API变更")
                        raise UpdateFailed(f"数据更新失败: {str(e)}") from e
                    except Exception as e:
                        _LOGGER.error(f"数据获取过程中发生未知错误: {str(e)}")
                        raise UpdateFailed(f"数据更新失败: {str(e)}") from e
            except Exception as e:
                _LOGGER.error(f"数据获取过程中发生未知错误: {str(e)}")
                raise UpdateFailed(f"数据更新失败: {str(e)}") from e
                
    def _ensure_str_keys(self, data):
        """递归确保字典的所有键都是字符串类型"""
        if isinstance(data, dict):
            return {str(k): self._ensure_str_keys(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._ensure_str_keys(item) for item in data]
        else:
            return data

    def _process_subscription_data(self, data):
        """处理原始订阅数据，计算并格式化所需的指标"""
        try:
            # 确保data的所有键都是字符串
            safe_data = self._ensure_str_keys(data)
            
            # 提取基础数据
            plan = safe_data.get('plan', {})
            
            # 流量转换（字节转GB）
            u = safe_data.get('u', 0)  # 上传流量
            d = safe_data.get('d', 0)  # 下载流量
            used_traffic = (u + d) / (1024 ** 3)  # 转换为GB
            
            # 尝试从data中获取transfer_enable，如果不存在则从plan中获取
            total_transfer = safe_data.get('transfer_enable', 0)
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
            expired_at = safe_data.get('expired_at', 0)
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
            api_subscribe_url = safe_data.get('subscribe_url', '')
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
                api_token = safe_data.get('token', '')
                if api_token:
                    subscribe_url = f"{self.platform['subscribe_url_base']}?token={api_token}"
                else:
                    # 动态生成subscribe_url，包含用户的token
                    subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
            
            # 返回处理后的数据，确保所有数据结构都是可JSON序列化的
            result = {
                "subscriptionType": subscription_type,
                "expireDate": expire_date_str,
                "daysRemaining": days_remaining,
                "resetDays": safe_data.get('reset_day', 0),
                "used": used_traffic,
                "total": total_traffic,
                "usage_percentage": usage_percentage,
                "onlineDevices": "∞",  # 从用户数据看是不限制设备数量
                "email": safe_data.get('email', '未知'),
                "plan_id": safe_data.get('plan_id', 0),
                "subscribe_url": subscribe_url,
                "raw_data": safe_data
            }
            
            # 最后确保整个结果的所有键都是字符串
            result = self._ensure_str_keys(result)
            return result
        except Exception as e:
            _LOGGER.error(f"数据处理错误: {str(e)}")
            # 返回默认数据，避免组件崩溃
            # 构建subscribe_url，尝试从data中提取token（如果有）
            try:
                # 检查data中是否有subscribe_url或token字段
                api_subscribe_url = data.get('subscribe_url', '')
                
                # 确保data的所有键都是字符串
                safe_data = self._ensure_str_keys(data)
                
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
                    api_token = safe_data.get('token', '')
                    if api_token:
                        subscribe_url = f"{self.platform['subscribe_url_base']}?token={api_token}"
                    else:
                        # 动态生成subscribe_url，包含用户的token
                        subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
            except:
                # 如果处理过程中出错，回退到使用配置的token
                subscribe_url = f"{self.platform['subscribe_url_base']}?token={self.auth_token}"
                # 确保data的所有键都是字符串
                safe_data = self._ensure_str_keys(data)
            
            result = {
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
                "raw_data": safe_data
            }
            
            # 最后确保整个结果的所有键都是字符串
            result = self._ensure_str_keys(result)
            return result

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

    # 注册配置选项更新的回调
    entry.async_on_unload(
        entry.add_update_listener(async_update_options)
    )

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
    return True

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """处理配置选项的更新"""
    # 重新加载条目以应用新的配置选项
    await hass.config_entries.async_reload(entry.entry_id)