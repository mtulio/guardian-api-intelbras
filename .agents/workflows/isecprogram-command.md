---
description: How to implement a new ISECProgram command for local connection to AMT 2018 E Smart
---

# Adding a New ISECProgram Command

This workflow describes how to add support for a new ISECProgram command for direct local connection to Intelbras AMT 2018 E Smart panels via port 9009.

## Prerequisites
- Access to the alarm panel on the local network
- The 6-digit remote access password
- PCAP capture of the command from AMT Remoto app (recommended)

## Steps

### 1. Capture the command (if unknown)

```bash
# On a machine on the same network:
tcpdump -i any -w capture.pcap port 9009

# Use AMT Remoto app to perform the action
# Stop capture (Ctrl+C)
# Extract payloads:
tshark -r capture.pcap -T fields -e ip.src -e tcp.payload
```

### 2. Decode the packet

ISECProgram packet format:
```
[outer_size][0xe7][isecprog_size][cmd][data...][CRC16_hi][CRC16_lo][XOR_checksum]
```

- `isecprog_size` = number of bytes in `[cmd] + [data]`
- CRC16 is calculated over `[isecprog_size, cmd, data...]`
- XOR_checksum = XOR of all preceding bytes ^ 0xFF

### 3. Test with standalone script

Use `.agents/scripts/test_isecprogram.py` as a template. Add your new command:

```python
pkt = build_isecprogram_packet(0xNEW_CMD, [data_bytes])
resp = await send_recv(pkt, "MY_COMMAND")
```

// turbo
### 4. Run the test

```bash
podman exec -i intelbras-guardian-api python3 < .agents/scripts/test_isecprogram.py
```

### 5. Implement in isecnet_protocol.py

Add the command to `ISECNetProtocol` class:
1. Use `self._build_isecprogram_packet(cmd, data)` to build the packet
2. Use `await self._send_and_receive(cmd, timeout=5.0)` to send
3. Parse the response (response cmd = request cmd + 0x80)

### 6. Add API endpoint

If needed, add a new endpoint in `app/api/v1/alarm_local.py`.

// turbo
### 7. Rebuild and test

```bash
cd docker && podman-compose down && podman-compose up -d --build
```

## Key Reference

- **CRC16**: `ISECNetProtocol._crc16()` — 24-bit register, XOR constant `0x00800500`
- **BCD Password**: `ISECNetProtocol._password_to_bcd()` — "123456" → `[0x12, 0x34, 0x56]`
- **Packet Builder**: `ISECNetProtocol._build_isecprogram_packet(cmd, data)`
- **Password suffix**: Always append `0x99` after BCD password bytes
