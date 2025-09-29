from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, SENSOR_NAME, SENSOR_ICON

class SubscriptionMonitorSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = SENSOR_NAME
    _attr_icon = SENSOR_ICON

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_subscription"

    @property
    def state(self):
        # 使用流量使用率作为状态
        usage_percentage = self.coordinator.data.get("usage_percentage", 0)
        return usage_percentage

    @property
    def extra_state_attributes(self):
        # 提取并格式化所有相关信息作为额外属性
        data = self.coordinator.data
        
        return {
            "subscription_type": data.get("subscriptionType", "未知"),
            "expire_date": data.get("expireDate", "未知"),
            "days_remaining": data.get("daysRemaining", 0),
            "reset_days": data.get("resetDays", 0),
            "used_traffic": f"{data.get('used', 0):.2f} GB",
            "total_traffic": f"{data.get('total', 0):.2f} GB",
            "usage_percentage": data.get("usage_percentage", 0),
            "online_devices": data.get("onlineDevices", "∞"),
            "email": data.get("email", ""),
            "plan_id": data.get("plan_id", ""),
            "subscribe_url": data.get("subscribe_url", "")
        }

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        SubscriptionMonitorSensor(coordinator, config_entry)
    ])