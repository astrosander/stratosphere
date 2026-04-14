# ============================================================
#  GPS TRACKER BASE STATION — Feather M0 RFM95x
#  CircuitPython 5.x — no DS18B20
#  Save as main.py on the LAPTOP board
#
#  Packet: pkt,lat,lon,alt,sats  or  pkt,NOFIX,0,0,0
# ============================================================

import gc
gc.collect()

import adafruit_rfm9x
gc.collect()

import time, board, digitalio
gc.collect()

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

led = digitalio.DigitalInOut(board.D13)
led.direction = digitalio.Direction.OUTPUT

rx = lost = 0

print("=== Base Station ready ===")
print("Waiting for tracker...")
print("")

while True:
    led.value = False
    packet = rfm.receive(timeout=8.0)

    if packet is None:
        lost += 1
        print("!! No packet  rx={}  lost={}".format(rx, lost))
        print("")
        continue

    led.value = True
    rx += 1

    try:
        raw = str(packet, "utf-8").strip()
    except Exception:
        raw = str(packet, "ascii").strip()

    rssi = rfm.rssi
    f = raw.split(",")

    print("================================")
    print("  Packet : #{}  rx={}  lost={}".format(f[0], rx, lost))
    print("  RSSI   : {} dBm".format(rssi))

    if len(f) >= 5:
        if f[1] == "NOFIX":
            print("  GPS    : searching...")
        else:
            print("  Lat    : {}".format(f[1]))
            print("  Lon    : {}".format(f[2]))
            print("  Alt    : {} m".format(f[3]))
            print("  Sats   : {}".format(f[4]))
            print("  Maps   : maps.google.com/?q={},{}".format(f[1], f[2]))
    else:
        print("  Raw    : {}".format(raw))

    print("================================")
    print("")

    ack = "ACK|{}|{}".format(f[0], rssi)
    time.sleep(0.05)
    rfm.send(bytes(ack, "utf-8"))
    gc.collect()
