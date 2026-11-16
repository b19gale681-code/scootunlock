# Scoot Unlock
BLE unlocker for rental micromobility units. Desktop backend uses bleak,
Android backend uses BluetoothGatt via pyjnius.

Desktop: py -m pip install -r requirements.txt ; py main.py
Android: buildozer -v android debug (or the GitHub Actions workflow)

Paste the unlock frame hex, scan, tap, confirm.
ATT 0x05/0x0F then success = crypto gate, handled.
ATT 0x08 = cloud token, replay cannot work, go physical.