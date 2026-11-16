import os, platform, threading, asyncio, traceback

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.gridlayout import GridLayout

import engine, store

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ


def backend():
    if IS_ANDROID:
        from transport_android import Android
        return Android()
    from transport_desktop import Desktop
    return Desktop()


class Root(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=8, spacing=6, **kw)
        self.profiles = store.load()
        self.t = backend()
        self.stop_flag = False
        self.t.on_notify = self._notify

        self.add_widget(Label(text="Scoot Unlock", size_hint=(1, .07),
                              bold=True, font_size="22sp"))
        self.hexbox = TextInput(text=self.profiles.get("_last_hex", ""),
                                hint_text="unlock frame hex",
                                multiline=False, size_hint=(1, .07))
        self.add_widget(self.hexbox)
        self.add_widget(Button(text="SCAN", size_hint=(1, .1),
                               on_release=self.scan))
        self.sv = ScrollView(size_hint=(1, .5))
        self.list = GridLayout(cols=1, size_hint_y=None, spacing=4)
        self.list.bind(minimum_height=self.list.setter("height"))
        self.sv.add_widget(self.list)
        self.add_widget(self.sv)
        self.logbox = TextInput(size_hint=(1, .22), readonly=True,
                                multiline=True, font_size="11sp")
        self.add_widget(self.logbox)

    def log(self, msg):
        Clock.schedule_once(
            lambda *_: setattr(self.logbox, "text", self.logbox.text + str(msg) + "\n"))

    def _notify(self, u, d):
        self.log("  <- " + u + " " + bytes(d).hex())

    def bg(self, coro):
        def run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(coro)
            except Exception:
                self.log(traceback.format_exc())
            finally:
                loop.close()
        threading.Thread(target=run, daemon=True).start()

    def scan(self, *_):
        self.list.clear_widgets()
        self.log("scanning 10s")
        seen = set()

        def add(r):
            if r["addr"] in seen:
                return
            seen.add(r["addr"])
            tag = (" [" + "/".join(r["tags"]) + "]") if r["tags"] else ""
            b = Button(text=(r["name"] or "?") + "  " + str(r["rssi"]) + "dBm" + tag,
                       size_hint_y=None, height=48)
            b.bind(on_release=lambda *_, r=r: self.confirm(r))
            self.list.add_widget(b)

        async def go():
            await self.t.scan(10, lambda r: Clock.schedule_once(lambda *_: add(r)))
            await self.t.disconnect()
        self.bg(go())

    def confirm(self, r):
        box = BoxLayout(orientation="vertical", padding=10, spacing=10)
        box.add_widget(Label(text=(r["name"] or "?") + "\n" + r["addr"] + "\n\nUnlock it?"))
        row = BoxLayout(size_hint=(1, .4), spacing=8)
        p = Popup(title="Confirm", content=box, size_hint=(.85, .45))
        row.add_widget(Button(text="NO", on_release=lambda *_: p.dismiss()))
        row.add_widget(Button(text="YES",
                              on_release=lambda *_: (p.dismiss(), self.run_unlock(r))))
        box.add_widget(row)
        p.open()

    def run_unlock(self, r):
        hexf = self.hexbox.text.strip()
        if not hexf:
            self.log("no hex frame entered")
            return
        self.profiles["_last_hex"] = hexf
        prof = self.profiles.get(r["addr"], {"addr": r["addr"]})
        prof["addr"] = r["addr"]
        prof["hex"] = hexf
        self.profiles[r["addr"]] = prof
        store.save(self.profiles)
        self.stop_flag = False

        async def go():
            ok, why = await engine.unlock(self.t, prof, self.log)
            store.save(self.profiles)
            self.log("RESULT: " + ("OK - rideable" if ok else "FAIL - " + why))
            if ok:
                await engine.keepalive(self.t, prof, self.log, lambda: self.stop_flag)
        self.bg(go())


class App1(App):
    def build(self):
        self.title = "Scoot Unlock"
        if IS_ANDROID:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.BLUETOOTH_SCAN,
                                 Permission.BLUETOOTH_CONNECT,
                                 Permission.ACCESS_FINE_LOCATION])
        return Root()

    def on_stop(self):
        try:
            self.root.stop_flag = True
        except Exception:
            pass


App1().run()