import re

GATE_CODES = {0x05, 0x0F, 0x0C}
AUTHZ_CODES = {0x08}
DFU_HINTS = ("00001530", "fe59", "8ec90003", "8ec90002")
NUS_WRITE = "6e400002"


def att_code(e):
    c = getattr(e, "code", None)
    if isinstance(c, int):
        return c
    m = re.search(r"0x([0-9a-fA-F]{2})", str(e))
    return int(m.group(1), 16) if m else None


def pick_char(chars):
    scored = []
    for ch in chars:
        u = ch["uuid"].lower()
        if any(h in u for h in DFU_HINTS):
            continue
        w = "write" in ch["props"] or "write-without-response" in ch["props"]
        if not w:
            continue
        s = 1
        if "write" in ch["props"]:
            s += 1
        if any("2902" in d for d in ch["descs"]):
            s += 3
        if u.startswith(NUS_WRITE):
            s += 5
        scored.append((s, ch))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def pick_cccd(ch):
    for d in ch["descs"]:
        if "2902" in d.lower():
            return d
    return None


async def unlock(t, prof, log):
    payload = bytes.fromhex(prof["hex"].replace(" ", "").replace(":", ""))
    paired = False
    hard = False

    await log("connecting")
    await t.connect(prof["addr"])
    await log("connected; discovering")
    chars = await t.discover()
    uuids = {c["uuid"] for c in chars}

    if prof.get("char") not in uuids:
        ch = pick_char(chars)
        if not ch:
            await log("no writable non-DFU characteristic")
            return False, "no target characteristic"
        prof["char"] = ch["uuid"]
        prof["cccd"] = pick_cccd(ch)
        await log("target " + ch["uuid"] + " cccd=" + str(prof["cccd"]))

    async def gated(fn, label):
        nonlocal paired, hard
        try:
            await fn()
            return True
        except Exception as e:
            code = att_code(e)
            if code in AUTHZ_CODES:
                hard = True
                await log(label + ": ATT 0x08 - cloud token required")
                return False
            if code in GATE_CODES and not paired:
                await log(label + ": ATT 0x%02X - pairing" % code)
                try:
                    await t.pair()
                    paired = True
                    await log("paired; re-discovering")
                    await t.discover()
                    await fn()
                    return True
                except Exception as e2:
                    await log(label + ": still failing after pair: " + str(e2))
                    return False
            await log(label + ": fail " + str(e))
            return False

    if prof.get("cccd"):
        if not await gated(lambda: t.subscribe(prof["char"], prof["cccd"]), "cccd"):
            return False, "subscribe failed"

    chunks = [payload[i:i + 20] for i in range(0, len(payload), 20)]
    for i, c in enumerate(chunks):
        if not await gated(lambda p=c: t.write(prof["char"], p, True), "probe[%d]" % i):
            return False, ("token gate" if hard else "write rejected")

    for c in chunks:
        try:
            await t.write(prof["char"], c, False)
        except Exception:
            break

    await log("frame accepted - keepalive on")
    return True, "ok"


async def keepalive(t, prof, log, stop, period=0.6):
    payload = bytes.fromhex(prof["hex"].replace(" ", ""))
    while not stop():
        try:
            await t.write(prof["char"], payload, False)
        except Exception:
            await log("keepalive write failed")
            return
        await t.sleep(period)