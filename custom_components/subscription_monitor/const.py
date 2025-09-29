# 传感器平台定义
PLATFORMS = ["sensor"]

# 传感器基本配置
SENSOR_NAME = "订阅信息"
SENSOR_ICON = "mdi:subscription"
DOMAIN = "subscription_monitor"

# 平台配置字典，仅支持云洞数据平台
PLATFORMS = {
    "default": {
        "name": "云洞",
        "api_url": "https://yundong.xn--xhq8sm16c5ls.com/api/v1/user/getSubscribe",
        "subscribe_url_base": "https://link.dingyueapi.net/api/v1/client/subscribe",
        "method": "GET",
        "headers": {
            "Authorization": "{token}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Referer": "https://yundong.xn--xhq8sm16c5ls.com/",
            "Origin": "https://yundong.xn--xhq8sm16c5ls.com",
            "Host": "yundong.xn--xhq8sm16c5ls.com",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "sec-ch-ua": "\"Microsoft Edge\";v=\"140\", \"Chromium\";v=\"140\", \"Not-A.Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"macOS\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1"
        }
    }
}