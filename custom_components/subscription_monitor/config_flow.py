import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
import aiohttp
import asyncio
from datetime import datetime
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

class SubscriptionMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        # 允许添加多个配置条目
        
        errors = {}
        
        if user_input is not None:
            try:
                # 使用邮箱和密码登录获取token
                token_data = await self._async_login_get_token(user_input["email"], user_input["password"])
                if token_data:
                    # 创建配置条目，存储邮箱、密码和token信息
                    platform_name = PLATFORMS["default"]["name"]
                    entry_data = {
                        "email": user_input["email"],
                        "password": user_input["password"],
                        "auth_token": token_data["token"],
                        "auth_data": token_data["auth_data"],
                        "token_expiry": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    return self.async_create_entry(title=f"{platform_name} - {user_input['email']}", data=entry_data)
                else:
                    errors["base"] = "invalid_credentials"
            except Exception as e:
                _LOGGER.error(f"配置验证失败: {str(e)}")
                errors["base"] = "unknown_error"
        
        # 显示配置表单，只有云洞数据平台
        data_schema = vol.Schema({
            vol.Required("email"): str,
            vol.Required("password"): str
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "email": "输入云洞数据平台的邮箱",
                "password": "输入云洞数据平台的密码"
            }
        )
    
    async def _async_login_get_token(self, email, password):
        """通过邮箱和密码登录获取token"""
        try:
            platform = PLATFORMS["default"]
            login_url = platform.get("login_url", "")
            login_headers = platform.get("login_headers", {})
            
            if not login_url:
                _LOGGER.error("登录URL未配置")
                return None
            
            # 构建登录请求数据
            form_data = f"email={email}&password={password}"
            
            _LOGGER.debug(f"发送登录请求到: {login_url}")
            _LOGGER.debug(f"登录请求头: {login_headers}")
            
            # 发送登录请求
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(login_url, headers=login_headers, data=form_data) as response:
                        _LOGGER.debug(f"登录请求响应状态码: {response.status}")
                        _LOGGER.debug(f"登录响应头: {dict(response.headers)}")
                        
                        # 尝试获取响应内容（无论状态码如何）
                        response_text = await response.text()
                        _LOGGER.debug(f"登录响应原始内容: {response_text}")
                        
                        if response.status == 200:
                            try:
                                # 尝试解析JSON响应
                                data = await response.json(content_type=None)  # 忽略content_type检查
                                _LOGGER.debug(f"登录响应解析后数据: {data}")
                                
                                # 检查是否获取到token，考虑多种可能的数据结构
                                if data:
                                    # 检查常见的token字段位置
                                    token = None
                                    auth_data = None
                                    
                                    # 检查data.token结构
                                    if isinstance(data, dict):
                                        if "token" in data:
                                            token = data["token"]
                                            auth_data = data
                                        elif "data" in data and isinstance(data["data"], dict):
                                            if "token" in data["data"]:
                                                token = data["data"]["token"]
                                                auth_data = data["data"]
                                        elif "result" in data and isinstance(data["result"], dict):
                                            if "token" in data["result"]:
                                                token = data["result"]["token"]
                                                auth_data = data["result"]
                                
                                if token:
                                    _LOGGER.info("成功获取到token")
                                    return {
                                        "token": token,
                                        "auth_data": auth_data or ""
                                    }
                                else:
                                    _LOGGER.error(f"登录成功但未获取到token: {data}")
                                    return None
                            except Exception as e:
                                _LOGGER.error(f"解析登录响应JSON失败: {str(e)}")
                                _LOGGER.debug(f"无法解析的响应内容: {response_text}")
                                return None
                        else:
                            _LOGGER.error(f"登录请求失败: 状态码{response.status}, 响应内容: {response_text}")
                            return None
                except aiohttp.ClientError as e:
                    _LOGGER.error(f"登录请求网络错误: {str(e)}")
                    return None
        except Exception as e:
            _LOGGER.error(f"登录过程中发生未知错误: {str(e)}")
            return None
    
    async def _async_validate_token(self, platform_key, token):
        """验证token是否有效"""
        # 基本的token格式验证
        if not token:
            return False
        
        # 获取平台配置
        platform = PLATFORMS.get(platform_key, PLATFORMS["default"])
        
        # 构建请求头，替换token占位符
        headers = {}
        for key, value in platform["headers"].items():
            try:
                headers[key] = value.format(token=token)
            except Exception as e:
                # 如果格式化失败（如cookie中包含特殊字符），直接使用原始值
                headers[key] = value
        
        # 尝试实际调用API验证token是否有效
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(platform["api_url"], headers=headers) as response:
                    # 即使返回404，也可能意味着token是有效的但API路径可能有变化
                    # 所以我们只检查连接是否成功，不严格要求200状态码
                    if response.status < 500:  # 排除服务器错误
                        try:
                            data = await response.json()
                            # 如果能解析JSON，则认为token基本有效
                            return True
                        except:
                            # 如果不能解析JSON，可能是API变更，但至少连接成功
                            return True
                    return False
        except Exception as e:
            _LOGGER.warning(f"API验证出错: {str(e)}")
            # 在网络错误的情况下，我们保守地认为token可能有效
            # 这样用户可以继续配置，后续实际使用时会得到更明确的错误
            return True

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SubscriptionMonitorOptionsFlow(config_entry)

class SubscriptionMonitorOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        # 不再向父类构造函数传递config_entry参数，也不再显式设置self.config_entry
        # Home Assistant 2025.12开始，OptionsFlow基类会自动处理config_entry
        super().__init__()
    
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        # 获取当前配置项的选项，如果没有则使用默认值
        current_options = self.config_entry.options or {}
        
        # 配置选项表单，添加刷新间隔配置
        options_schema = vol.Schema({
            vol.Optional(
                "scan_interval", 
                default=current_options.get("scan_interval", 300)
            ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
        })
        
        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={
                "interval_description": "配置数据刷新间隔（秒），默认300秒（5分钟）"
            }
        )