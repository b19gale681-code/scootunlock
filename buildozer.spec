[app]
title = Scoot Unlock
package.name = scootunlock
package.domain = org.venice
source.dir = .
source.include_exts = py,png,jpg,json
version = 1.0
requirements = python3,kivy,pyjnius,android
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_SCAN,BLUETOOTH_CONNECT,ACCESS_FINE_LOCATION
android.api = 33
android.minapi = 24
android.archs = arm64-v8a
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 1