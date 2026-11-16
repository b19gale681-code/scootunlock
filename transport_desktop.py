import asyncio
from bleak import BleakClient, BleakScanner

NUS_SVC = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"


class Desktop:
    def __init__(self):
        self.c = None
        self.on_notify = None

    async def scan(self, seconds=10, out=None):
        def cb(dev, adv):
            name = adv.local_name or dev.name or ""
            if not name:
                return
            tags = []
            if 0x0B46 in (adv.manufacturer_data or {}):
                tags.append("BIRD")
            if any(str(u).lower() == NUS_SVC for u in (adv.service_uuids or [])):
                tags.append("NUS")
            if out:
                out({"name": name, "addr": dev.address,
                     "rssi": adv.rssi, "tags": tags})
        async with BleakScanner(detection_callback=cb):
            await asyncio.sleep(seconds)

    async def connect(self, addr):
        self.c = BleakClient(addr, timeout=25)
        await self.c.connect()
        if not self.c.is_connected:
            raise RuntimeError("connect failed")

    async def discover(self):
        await self.c.get_services()
        res = []
        for svc in self.c.services:
            for ch in svc.characteristics:
                res.append({"uuid": ch.uuid, "props": list(ch.properties),
                            "descs": [x.uuid for x in ch.descriptors]})
        return res

    async def pair(self):
        await self.c.pair()

    async def subscribe(self, char, cccd):
        await self.c.start_notify(
            char, lambda s, v: self.on_notify and self.on_notify(s.uuid, v))
        await self.c.write_gatt_char(cccd, b"\x01\x00", response=True)

    async def write(self, char, data, response):
        await self.c.write_gatt_char(char, data, response=response)

    async def sleep(self, s):
        await asyncio.sleep(s)

    async def disconnect(self):
        if self.c:
            await self.c.disconnect()