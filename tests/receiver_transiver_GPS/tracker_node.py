# ============================================================
#  GPS TRACKER NODE — Feather M0 RFM95x + GPS FeatherWing
#  CircuitPython 5.x — no DS18B20
#  Save as main.py on the BATTERY board
# ============================================================

import gc
gc.collect()

import adafruit_rfm9x
gc.collect()

import time, board, busio, digitalio
gc.collect()

# ── Radio ────────────────────────────────────────────────────
spi = board.SPI()
cs  = digitalio.DigitalInOut(board.RFM9X_CS)
cs.deinit()
rst = digitalio.DigitalInOut(board.RFM9X_RST)
rst.deinit()
cs  = digitalio.DigitalInOut(board.RFM9X_CS)
rst = digitalio.DigitalInOut(board.RFM9X_RST)
rfm = adafruit_rfm9x.RFM9x(spi, cs, rst, 915.0)
rfm.tx_power         = 23
rfm.spreading_factor = 7
rfm.signal_bandwidth = 125000
rfm.coding_rate      = 5
rfm.enable_crc       = True
gc.collect()

# ── GPS raw UART ──────────────────────────────────────────────
uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=0)
uart.write(b"$PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0*28\r\n")
uart.write(b"$PMTK220,1000*1F\r\n")
gc.collect()

led = digitalio.DigitalInOut(board.D13)
led.direction = digitalio.Direction.OUTPUT

# ── GPS state ─────────────────────────────────────────────────
gps_buf = b""
lat = lon = alt = None
sats = 0
fix  = False

def parse(line):
    global lat, lon, alt, sats, fix
    try:
        if "*" in line: line = line[:line.index("*")]
        f = line.split(",")
        if f[0] in ("$GPRMC","$GNRMC") and len(f)>=7:
            if f[2]=="A" and f[3] and f[5]:
                d=int(f[3][:2]); m=float(f[3][2:])
                lat=(d+m/60)*(-1 if f[4]=="S" else 1)
                d=int(f[5][:3]); m=float(f[5][3:])
                lon=(d+m/60)*(-1 if f[6]=="W" else 1)
                fix=True
            else:
                fix=False
        elif f[0] in ("$GPGGA","$GNGGA") and len(f)>=10:
            if f[6]!="0":
                sats=int(f[7]) if f[7] else 0
                alt=float(f[9]) if f[9] else 0.0
    except Exception: pass

def read_gps():
    global gps_buf
    data = uart.read(64)
    if not data: return
    gps_buf += data
    while b"\n" in gps_buf:
        i = gps_buf.index(b"\n")
        parse(str(gps_buf[:i], "ascii").strip())
        gps_buf = gps_buf[i+1:]
        if len(gps_buf) > 256: gps_buf = b""

print("=== Tracker ready  mem:{} ===".format(gc.mem_free()))

pkt  = 0
last = time.monotonic()

while True:
    read_gps()
    if time.monotonic() - last < 5.0: continue
    last = time.monotonic()

    if fix and lat is not None:
        msg = "{},{:.6f},{:.6f},{:.1f},{}".format(
            pkt, lat, lon, alt or 0, sats)
    else:
        msg = "{},NOFIX,0,0,0".format(pkt)

    led.value = True
    print("TX -> {}".format(msg))
    rfm.send(bytes(msg, "utf-8"))
    led.value = False

    ack = rfm.receive(timeout=2.0)
    if ack is not None:
        try: print("  ACK <- {}".format(str(ack, "utf-8")))
        except Exception: pass
    else:
        print("  (no ACK)")

    pkt += 1
    gc.collect()
    print("")
