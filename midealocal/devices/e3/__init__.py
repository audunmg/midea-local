import json
import logging
import sys
from typing import Any

from .message import (
    MessageE3Response,
    MessageNewProtocolSet,
    MessagePower,
    MessageQuery,
    MessageSet,
)

if sys.version_info < (3, 12):
    from midealocal.backports.enum import StrEnum
else:
    from enum import StrEnum

from midealocal.device import MideaDevice

_LOGGER = logging.getLogger(__name__)


class DeviceAttributes(StrEnum):
    power = "power"
    burning_state = "burning_state"
    zero_cold_water = "zero_cold_water"
    protection = "protection"
    zero_cold_pulse = "zero_cold_pulse"
    smart_volume = "smart_volume"
    current_temperature = "current_temperature"
    target_temperature = "target_temperature"


class MideaE3Device(MideaDevice):
    def __init__(
        self,
        name: str,
        device_id: int,
        ip_address: str,
        port: int,
        token: str,
        key: str,
        protocol: int,
        model: str,
        subtype: int,
        customize: str,
    ) -> None:
        super().__init__(
            name=name,
            device_id=device_id,
            device_type=0xE3,
            ip_address=ip_address,
            port=port,
            token=token,
            key=key,
            protocol=protocol,
            model=model,
            subtype=subtype,
            attributes={
                DeviceAttributes.power: False,
                DeviceAttributes.burning_state: False,
                DeviceAttributes.zero_cold_water: False,
                DeviceAttributes.protection: False,
                DeviceAttributes.zero_cold_pulse: False,
                DeviceAttributes.smart_volume: False,
                DeviceAttributes.current_temperature: None,
                DeviceAttributes.target_temperature: 40,
            },
        )
        self._old_subtypes = [32, 33, 34, 35, 36, 37, 40, 43, 48, 49, 80]
        self._precision_halves: bool | None = None
        self._default_precision_halves = False
        self.set_customize(customize)

    @property
    def precision_halves(self) -> bool | None:
        return self._precision_halves

    def build_query(self) -> list[MessageQuery]:
        return [MessageQuery(self._protocol_version)]

    def process_message(self, msg: bytes) -> dict[str, Any]:
        message = MessageE3Response(msg)
        _LOGGER.debug("[%s] Received: %s", self.device_id, message)
        new_status = {}
        for status in self._attributes.keys():
            if hasattr(message, str(status)):
                if self._precision_halves and status in [
                    DeviceAttributes.current_temperature,
                    DeviceAttributes.target_temperature,
                ]:
                    self._attributes[status] = getattr(message, str(status)) / 2
                else:
                    self._attributes[status] = getattr(message, str(status))
                new_status[str(status)] = self._attributes[status]

        return new_status

    def make_message_set(self) -> MessageSet:
        message = MessageSet(self._protocol_version)
        message.zero_cold_water = self._attributes[DeviceAttributes.zero_cold_water]
        message.protection = self._attributes[DeviceAttributes.protection]
        message.zero_cold_pulse = self._attributes[DeviceAttributes.zero_cold_pulse]
        message.smart_volume = self._attributes[DeviceAttributes.smart_volume]
        message.target_temperature = self._attributes[
            DeviceAttributes.target_temperature
        ]
        return message

    def set_attribute(self, attr: str, value: Any) -> None:
        message: MessagePower | MessageSet | MessageNewProtocolSet | None = None
        if attr not in [
            DeviceAttributes.burning_state,
            DeviceAttributes.current_temperature,
            DeviceAttributes.protection,
        ]:
            if self._precision_halves and attr == DeviceAttributes.target_temperature:
                value = int(value * 2)
            if attr == DeviceAttributes.power:
                message = MessagePower(self._protocol_version)
                message.power = value
            elif self.subtype in self._old_subtypes:
                message = self.make_message_set()
                setattr(message, str(attr), value)
            else:
                message = MessageNewProtocolSet(self._protocol_version)
                message.key = str(attr)
                message.value = value
            self.build_send(message)

    def set_customize(self, customize: str) -> None:
        self._precision_halves = self._default_precision_halves
        if customize and len(customize) > 0:
            try:
                params = json.loads(customize)
                if params and "precision_halves" in params:
                    self._precision_halves = params.get("precision_halves")
            except Exception as e:
                _LOGGER.error("[%s] Set customize error: %s", self.device_id, repr(e))
            self.update_all({"precision_halves": self._precision_halves})


class MideaAppliance(MideaE3Device):
    pass
