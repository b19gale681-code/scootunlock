import threading, time
from jnius import autoclass, PythonJavaClass, java_method

BluetoothAdapter = autoclass("android.bluetooth.BluetoothAdapter")
UUID = autoclass("java.util.UUID")
PythonActivity = autoclass("org.kivy.android.PythonActivity")

CCCD_UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")


class _ScanCB(PythonJavaClass):
    __javainterfaces__ = ["android/bluetooth/le/ScanCallback"]

    def __init__(self, sink):
        super().__init__()
        self.sink = sink

    @java_method("(ILandroid/bluetooth/le/ScanResult;)V")
    def onScanResult(self, ctype, res):
        try:
            d = res.getDevice()
            self.sink({"name": d.getName() or "", "addr": d.getAddress(),
                       "rssi": res.getRssi(), "tags": []})
        except Exception:
            pass


class _GattCB(PythonJavaClass):
    __javainterfaces__ = ["android/bluetooth/BluetoothGattCallback"]

    def __init__(self, owner):
        super().__init__()
        self.o = owner

    @java_method("(Landroid/bluetooth/BluetoothGatt;II)V")
    def onConnectionStateChange(self, g, status, state):
        self.o.connected = (state == 2 and status == 0)
        self.o.ev.set()

    @java_method("(Landroid/bluetooth/BluetoothGatt;I)V")
    def onServicesDiscovered(self, g, status):
        self.o.last_err = status
        self.o.ev.set()

    @java_method("(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;I)V")
    def onCharacteristicWrite(self, g, ch, status):
        self.o.last_err = status
        self.o.ev.set()

    @java_method("(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattDescriptor;I)V")
    def onDescriptorWrite(self, g, d, status):
        self.o.last_err = status
        self.o.ev.set()

    @java_method("(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/BluetoothGattCharacteristic;)V")
    def onCharacteristicChanged(self, g, ch):
        if self.o.on_notify:
            self.o.on_notify(ch.getUuid().toString(), bytes(ch.getValue()))


class Android:
    def __init__(self):
        self.a = BluetoothAdapter.getDefaultAdapter()
        self.g = None
        self.cb = _GattCB(self)
        self.ev = threading.Event()
        self.connected = False
        self.last_err = 0
        self.on_notify = None
        self._ch = {}

    def _perm(self):
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.BLUETOOTH_SCAN,
                             Permission.BLUETOOTH_CONNECT,
                             Permission.ACCESS_FINE_LOCATION])

    async def scan(self, seconds=10, out=None):
        self._perm()
        time.sleep(0.8)
        cb = _ScanCB(out)
        self.a.startLeScan(cb)
        time.sleep(seconds)
        self.a.stopLeScan(cb)

    async def connect(self, addr):
        dev = self.a.getRemoteDevice(addr)
        self.ev.clear()
        self.g = dev.connectGatt(PythonActivity.mActivity, False, self.cb)
        self.ev.wait(25)
        if not self.connected:
            raise RuntimeError("connect failed")

    async def discover(self):
        self.ev.clear()
        self.last_err = 0
        if not self.g.discoverServices():
            raise RuntimeError("discoverServices false")
        self.ev.wait(20)
        if self.last_err:
            raise RuntimeError("discover status %d" % self.last_err)
        res = []
        for s in self.g.getServices():
            for ch in s.getCharacteristics():
                p = ch.getProperties()
                props = []
                if p & 0x08:
                    props.append("write")
                if p & 0x04:
                    props.append("write-without-response")
                if p & 0x10:
                    props.append("notify")
                descs = [x.getUuid().toString() for x in ch.getDescriptors()]
                self._ch[ch.getUuid().toString()] = ch
                res.append({"uuid": ch.getUuid().toString(),
                            "props": props, "descs": descs})
        return res

    async def pair(self):
        dev = self.a.getRemoteDevice(self.g.getDevice().getAddress())
        dev.createBond()
        time.sleep(3)

    async def subscribe(self, char, cccd):
        ch = self._ch[char]
        self.g.setCharacteristicNotification(ch, True)
        d = ch.getDescriptor(CCCD_UUID)
        d.setValue(b"\x01\x00")
        self.ev.clear()
        self.last_err = 0
        self.g.writeDescriptor(d)
        self.ev.wait(10)
        if self.last_err:
            e = RuntimeError("cccd status %d" % self.last_err)
            e.code = self.last_err
            raise e

    async def write(self, char, data, response):
        ch = self._ch[char]
        ch.setWriteType(1 if response else 0)
        ch.setValue(bytes(data))
        self.ev.clear()
        self.last_err = 0
        if not self.g.writeCharacteristic(ch):
            raise RuntimeError("writeCharacteristic false")
        if response:
            self.ev.wait(10)
            if self.last_err:
                e = RuntimeError("gatt status %d" % self.last_err)
                e.code = self.last_err
                raise e

    async def sleep(self, s):
        time.sleep(s)

    async def disconnect(self):
        if self.g:
            self.g.disconnect()
            self.g.close()