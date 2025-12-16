import logging
import json
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
                token_data = await self._async_login_get_token(user_input["email"], user_input["password"], user_input.get("base_url"))
                if token_data:
                    # 创建配置条目，存储邮箱、密码和token信息
                    platform_name = PLATFORMS["default"]["name"]
                    entry_data = {
                        "email": user_input["email"],
                        "password": user_input["password"],
                        "base_url": user_input.get("base_url"),
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
        
        # 获取默认base_url
        default_base_url = PLATFORMS["default"]["base_url"]
        
        # 显示配置表单，只有云洞数据平台
        data_schema = vol.Schema({
            vol.Required("email"): str,
            vol.Required("password"): str,
            vol.Optional("base_url", default=default_base_url): str
        })
        
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "email": "输入云洞数据平台的邮箱",
                "password": "输入云洞数据平台的密码",
                "base_url": f"输入云洞数据平台的域名，默认：{default_base_url}"
            }
        )
    
    async def _async_login_get_token(self, email, password, base_url=None):
        """通过邮箱和密码登录获取token"""
        try:
            platform = PLATFORMS["default"]
            
            # 使用提供的base_url或默认base_url
            current_base_url = base_url or platform.get("base_url", "")
            login_path = platform.get("login_path", "")
            login_url = f"{current_base_url}{login_path}"
            login_headers = platform.get("login_headers", {})
            
            # 更新headers中的Host和Origin/Referer
            updated_headers = login_headers.copy()
            # 从base_url中提取主机名
            from urllib.parse import urlparse
            parsed_url = urlparse(current_base_url)
            host = parsed_url.netloc
            
            if host:
                updated_headers["Host"] = host
                updated_headers["Origin"] = current_base_url
                updated_headers["Referer"] = f"{current_base_url}/"
            
            if not login_url:
                _LOGGER.error("登录URL未配置")
                return None
            
            # 构建登录请求数据，使用字典格式，让aiohttp自动处理URL编码
            form_data = {
                'email': email,
                'password': password
            }
            
            # 使用与curl命令完全匹配的请求头
            curl_headers = {
                'accept': '*/*',
                'accept-language': 'zh-CN,zh;q=0.9',
                'content-language': 'zh-CN',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': current_base_url,
                'priority': 'u=1, i',
                'referer': f'{current_base_url}/',
                'sec-ch-ua': '"Chromium";v="135", "Not-A.Brand";v="8"',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': '"Android"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36'
            }
            
            # 从base_url中提取主机名并添加到请求头
            parsed_url = urlparse(current_base_url)
            host = parsed_url.netloc
            if host:
                curl_headers['Host'] = host
            
            _LOGGER.debug(f"发送登录请求到: {login_url}")
            _LOGGER.debug(f"登录请求头: {curl_headers}")
            _LOGGER.debug(f"登录请求数据: {form_data}")
            
            # 发送登录请求，禁用SSL验证（解决证书验证失败问题）
            # 添加auto_decompress=True确保自动解压所有压缩响应
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), auto_decompress=True) as session:
                # 只发送一次请求，使用完整的curl头
                curl_headers = {
                    'accept': '*/*',
                    'accept-language': 'zh-CN,zh;q=0.9',
                    'content-language': 'zh-CN',
                    'content-type': 'application/x-www-form-urlencoded',
                    'origin': current_base_url,
                    'priority': 'u=1, i',
                    'referer': f'{current_base_url}/',
                    'sec-ch-ua': '"Chromium";v="135", "Not-A.Brand";v="8"',
                    'sec-ch-ua-mobile': '?1',
                    'sec-ch-ua-platform': '"Android"',
                    'sec-fetch-dest': 'empty',
                    'sec-fetch-mode': 'cors',
                    'sec-fetch-site': 'same-origin',
                    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36'
                }
                
                # 从base_url中提取主机名并添加到请求头
                parsed_url = urlparse(current_base_url)
                host = parsed_url.netloc
                if host:
                    curl_headers['Host'] = host
                
                try:
                    async with session.post(login_url, headers=curl_headers, data=form_data) as response:
                        _LOGGER.debug(f"登录请求响应状态码: {response.status}")
                        _LOGGER.debug(f"登录响应头: {dict(response.headers)}")
                        
                        # 检查响应的Content-Encoding和Content-Type
                        content_encoding = response.headers.get('Content-Encoding', 'none')
                        content_type = response.headers.get('Content-Type', 'unknown')
                        _LOGGER.debug(f"响应Content-Encoding: {content_encoding}")
                        _LOGGER.debug(f"响应Content-Type: {content_type}")
                        
                        # 首先检查响应状态码
                        if response.status != 200:
                            _LOGGER.error(f"登录请求失败，状态码: {response.status}")
                            # 尝试获取错误响应
                            try:
                                error_text = await response.text()
                                _LOGGER.error(f"响应内容: {error_text}")
                            except Exception as e:
                                _LOGGER.error(f"无法获取文本错误响应: {str(e)}")
                                try:
                                    error_content = await response.read()
                                    _LOGGER.error(f"响应二进制数据: {error_content[:200]}")
                                except Exception as read_e:
                                    _LOGGER.error(f"无法读取错误响应: {str(read_e)}")
                            return None
                        
                        # 完全复制测试脚本的逻辑，只根据Content-Encoding头解压
                        response_content = await response.read()
                        _LOGGER.debug(f"原始响应二进制数据: {response_content[:200]}")
                        _LOGGER.debug(f"原始响应长度: {len(response_content)} 字节")
                        
                        # 检查响应是否为压缩格式
                        content_encoding = response.headers.get('Content-Encoding', '')
                        _LOGGER.debug(f"Content-Encoding: {content_encoding}")
                        
                        # 手动解压响应，只根据Content-Encoding头，移除brotli支持
                        import zlib
                        import gzip
                        
                        decompressed = response_content
                        decompression_method = "none"
                        
                        try:
                            if content_encoding == 'gzip':
                                decompressed = gzip.decompress(response_content)
                                decompression_method = "gzip"
                            elif content_encoding == 'deflate':
                                try:
                                    decompressed = zlib.decompress(response_content)
                                    decompression_method = "deflate"
                                except:
                                    decompressed = zlib.decompress(response_content, -zlib.MAX_WBITS)
                                    decompression_method = "deflate_raw"
                        except Exception as e:
                            _LOGGER.warning(f"解压失败，使用原始内容: {str(e)}")
                            decompressed = response_content
                            decompression_method = "none"
                        
                        _LOGGER.debug(f"使用{decompression_method}解压后长度: {len(decompressed)} 字节")
                        _LOGGER.debug(f"解压后前200字节: {decompressed[:200]}")
                        
                        # 尝试解码为字符串，优先使用utf-8
                        try:
                            response_text = decompressed.decode('utf-8')
                            _LOGGER.debug(f"使用utf-8编码成功解码响应")
                        except UnicodeDecodeError:
                            try:
                                response_text = decompressed.decode('gbk')
                                _LOGGER.debug(f"使用gbk编码成功解码响应")
                            except UnicodeDecodeError:
                                response_text = decompressed.decode('latin-1')
                                _LOGGER.debug(f"使用latin-1编码成功解码响应")
                        
                        _LOGGER.debug(f"最终响应文本内容: {response_text[:200]}")
                        
                        # 现在尝试解析JSON
                        # 先清理文本，移除可能的BOM和无效字符
                        import re
                        # 移除BOM（字节顺序标记）
                        if response_text.startswith('\ufeff'):
                            response_text = response_text[1:]
                        # 移除控制字符，但保留换行符和制表符
                        response_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', response_text)
                        
                        # 检查响应是否为HTML格式
                        if '<html' in response_text.lower() or '<!DOCTYPE' in response_text.lower():
                            _LOGGER.error(f"登录响应为HTML格式，不是预期的JSON格式: {response_text[:200]}")
                            return None
                        
                        # 检查响应是否为空
                        if not response_text.strip():
                            _LOGGER.error("登录响应为空")
                            return None
                            
                        # 尝试解析JSON
                        try:
                            data = json.loads(response_text)
                            _LOGGER.debug(f"登录响应解析后数据: {data}")
                            
                            # 检查是否获取到token，考虑多种可能的数据结构
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
                        except json.JSONDecodeError as e:
                            _LOGGER.error(f"JSON解析错误: {str(e)}")
                            _LOGGER.error(f"响应文本内容: {response_text}")
                            return None
                        except Exception as e:
                            _LOGGER.error(f"解析响应失败: {str(e)}")
                            _LOGGER.error(f"响应文本内容: {response_text}")
                            return None
                except aiohttp.ClientError as e:
                    _LOGGER.error(f"登录请求网络错误: {str(e)}")
                    return None
        except Exception as e:
            _LOGGER.error(f"登录过程中发生未知错误: {str(e)}")
            return None
    
    async def _async_validate_token(self, platform_key, token, base_url=None):
        """验证token是否有效"""
        # 基本的token格式验证
        if not token:
            return False
        
        # 获取平台配置
        platform = PLATFORMS.get(platform_key, PLATFORMS["default"])
        
        # 使用提供的base_url或默认base_url
        current_base_url = base_url or platform.get("base_url", "")
        api_path = platform.get("api_path", "")
        api_url = f"{current_base_url}{api_path}"
        
        # 构建请求头，替换token占位符
        headers = {}
        for key, value in platform["headers"].items():
            try:
                headers[key] = value.format(token=token)
            except Exception as e:
                # 如果格式化失败（如cookie中包含特殊字符），直接使用原始值
                headers[key] = value
        
        # 更新headers中的Host和Origin/Referer
        from urllib.parse import urlparse
        parsed_url = urlparse(current_base_url)
        host = parsed_url.netloc
        
        if host:
            headers["Host"] = host
            headers["Origin"] = current_base_url
            headers["Referer"] = f"{current_base_url}/"
        
        # 尝试实际调用API验证token是否有效
        try:
            # 添加auto_decompress=True确保自动解压所有压缩响应，禁用SSL验证
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), auto_decompress=True) as session:
                async with session.get(api_url, headers=headers) as response:
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