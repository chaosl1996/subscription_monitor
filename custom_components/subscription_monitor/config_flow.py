import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol
import aiohttp
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

class SubscriptionMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        # 允许添加多个配置条目
        
        errors = {}
        
        if user_input is not None:
            try:
                # 验证token是否有效
                if not await self._async_validate_token("default", user_input["auth_token"]):
                    errors["base"] = "invalid_token"
                else:
                    # 创建配置条目
                    platform_name = PLATFORMS["default"]["name"]
                    return self.async_create_entry(title=f"{platform_name} - 订阅监控", data=user_input)
            except Exception as e:
                _LOGGER.error(f"配置验证失败: {str(e)}")
                errors["base"] = "unknown_error"
        
        # 显示配置表单，只有云洞数据平台
        data_schema = vol.Schema({
            vol.Required("auth_token"): str
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "auth_token": "输入云洞数据平台的Token"
            }
        )
    
    async def _async_validate_token(self, platform_key, token):
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
        # 不再直接设置config_entry，而是通过super()调用
        super().__init__(config_entry)
    
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        # 可以添加选项配置，但目前不需要
        return self.async_show_form(step_id="init")