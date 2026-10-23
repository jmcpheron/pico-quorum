# The ceremony on the Feather ESP32-S3 Reverse TFT

Written by `node tools/board/shots_feather_setup.mjs`: `setup_s.py` on the emulator, C1-C10 on a
virtual 608C, 240 × 135, three buttons down the left edge (the grey dots: D0, D1, D2).

- **D0**: back; on a result, OK.
- **D0 + D1 held 3 s**: the arm, for 60 s (the Pico's B+Y). D2 is never part of it.
- **D2**: do a step; on a permanent or GenKey step, held 3 s once armed. On a result, OK.

ALLOW_LOCK and ALLOW_GENKEY in the board's `secrets.py` still gate every permanent step.

### banner

The banner: a fresh chip on the dual image. Not a signing console. D2 opens PROVISION.

![01-banner](01-banner.png)

### c1

C1, the pre-flight: reads only. D0 back, D2 does it.

![02-c1](02-c1.png)

### c1 result

C1's checks: the 608C, both zones open, the factory table, saved as a snapshot. D2: OK.

![03-c1-result](03-c1-result.png)

### c2 result

C2 wrote quorum v1 and read it back. Compare the CRC with tools/check_config --summary on the laptop.

![04-c2-result](04-c2-result.png)

### c3

C3, permanent: red. Not armed: D0+D1 held 3 s arms it (D2 does nothing until then).

![05-c3](05-c3.png)

### c3 arming

D0+D1 held: the rail fills; 3 s to arm. Let go early and it isn't armed.

![06-c3-arming](06-c3-arming.png)

### c3 armed letgo

The arm took: let go of both.

![07-c3-armed-letgo](07-c3-armed-letgo.png)

### c3 armed

Armed for 60 s: hold D2 3 s to lock.

![08-c3-armed](08-c3-armed.png)

### c3 hold

D2 held: the rail fills red. Let go before 3 s and nothing happens.

![09-c3-hold](09-c3-hold.png)

### c3 result

C3 done: the config is locked, still quorum v1.

![10-c3-result](10-c3-result.png)

### c4

C4: GenKey, armed and held like a permanent step.

![11-c4](11-c4.png)

### c4 result

The new key, made inside the chip.

![12-c4-result](12-c4-result.png)

### c5 result

C5: two test signatures checked here; counter 0 up by 2.

![13-c5-result](13-c5-result.png)

### c6

C6, permanent: seal slot 0 so the key can never be replaced.

![14-c6](14-c6.png)

### c6 arm again

Under 10 s of the arm left: no hold starts, arm again. Chip 3's first C6 ran out partway.

![14-c6-arm-again](14-c6-arm-again.png)

### c6 result

Slot 0 sealed: FE FF, the same key, it signs and verifies.

![15-c6-result](15-c6-result.png)

### c7 result

C7: the owner address, to compare on the laptop with tools/fw verify --baseline.

![16-c7-result](16-c7-result.png)

### c8 result

C8: zeros into slots 1-15, the record into OTP; the data CRC.

![17-c8-result](17-c8-result.png)

### c9

C9, permanent: lock the data and OTP zones.

![18-c9](18-c9.png)

### c9 result

C9 done.

![19-c9-result](19-c9-result.png)

### c10

C10: the summary.

![20-c10](20-c10.png)

### c10 result

Sealed: quorum v1 locked 00/00, slot 0 sealed, the record matches; set ALLOW_* back to False.

![21-c10-result](21-c10-result.png)

### c3 allow off

With ALLOW_LOCK False on the board, a permanent step says so and nothing arms it.

![22-c3-allow-off](22-c3-allow-off.png)
