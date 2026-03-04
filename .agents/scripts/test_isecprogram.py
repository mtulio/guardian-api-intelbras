"""Test ISECProgram protocol with correct CRC16 and packet format.

Packet format (from PCAP analysis):
  [outer_size][0xe7][isecprog_size][cmd][data...][CRC16_hi][CRC16_lo][outer_XOR_checksum]

Handshake (from ANTIGRAVITY.md + PCAP):
  Step 1: INITIATE  (0x10) → response 0x90 (Ready)
  Step 2: AUTH      (0x11) → BCD password + 0x99 suffix → response 0x53 (Success)
  Step 3: CONFIRM   (0x19) → data=[0x11] → confirms auth
  Step 4: STATUS    (0x15) → get status

Usage:
  python3 test_isecprogram.py <6-digit-password> [ip] [port]

Example:
  python3 test_isecprogram.py 123456
  python3 test_isecprogram.py 123456 192.168.1.100 9009
"""
import asyncio
import sys

HOST = sys.argv[2] if len(sys.argv) > 2 else "192.168.1.5"
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 9009
PASSWORD = sys.argv[1] if len(sys.argv) > 1 else "123456"


def calculate_crc16(data):
    """Calculate ISECProgram CRC16.

    Uses a 24-bit register with XOR constant 0x00800500.
    Validated against PCAP known-good packets from AMT Remoto app.
    """
    crc_register = 0
    crc_byte_count = 0

    all_data = list(data) + [0, 0]

    for byte_val in all_data:
        if crc_byte_count == 0:
            crc_register = (crc_register & ~0x00FF0000) | ((byte_val & 0xFF) << 16)
        elif crc_byte_count == 1:
            crc_register = (crc_register & ~0x0000FF00) | ((byte_val & 0xFF) << 8)
        elif crc_byte_count == 2:
            crc_register = (crc_register & ~0x000000FF) | (byte_val & 0xFF)

        if crc_byte_count < 2:
            crc_byte_count += 1
        else:
            for _ in range(8):
                crc_register <<= 1
                if crc_register & 0x1000000:
                    crc_register ^= 0x00800500

    final_crc = (((crc_register >> 16) & 0xFF) << 8) | ((crc_register >> 8) & 0xFF)
    return final_crc & 0xFFFF


def xor_checksum(data):
    """XOR checksum ^ 0xFF (IsecNet outer checksum)."""
    result = 0
    for b in data:
        result ^= b
    return result ^ 0xFF


def build_isecprogram_packet(cmd, data=None):
    """Build a full ISECProgram-over-IsecNet packet.

    Format: [outer_size][0xe7][isecprog_size][cmd][data...][CRC16_hi][CRC16_lo][outer_XOR_checksum]
    """
    if data is None:
        data = []

    # ISECProgram inner: [size][cmd][data...]
    isecprog_size = 1 + len(data)  # cmd + data
    isecprog = [isecprog_size, cmd] + list(data)

    # CRC16 over the ISECProgram content
    crc = calculate_crc16(isecprog)
    crc_hi = (crc >> 8) & 0xFF
    crc_lo = crc & 0xFF

    # Outer packet: [outer_size][0xe7][isecprog...][crc_hi][crc_lo]
    outer_content = [0xe7] + isecprog + [crc_hi, crc_lo]
    outer_size = len(outer_content)

    packet = [outer_size] + outer_content
    packet.append(xor_checksum(packet))

    return bytes(packet)


def password_to_bcd(password_str):
    """Convert password string to BCD bytes.

    '123456' → [0x12, 0x34, 0x56]
    '1234'   → [0x12, 0x34]
    """
    # Pad to even length
    if len(password_str) % 2:
        password_str = '0' + password_str
    result = []
    for i in range(0, len(password_str), 2):
        hi = int(password_str[i])
        lo = int(password_str[i + 1])
        result.append((hi << 4) | lo)
    return result


async def test_handshake():
    print(f"Connecting to {HOST}:{PORT}...")
    reader, writer = await asyncio.open_connection(HOST, PORT)
    print("Connected!\n")

    async def send_recv(pkt, label, timeout=3):
        print(f"→ {label}: {pkt.hex()} ({len(pkt)} bytes)")
        writer.write(pkt)
        await writer.drain()
        try:
            resp = await asyncio.wait_for(reader.read(256), timeout=timeout)
            print(f"← Response: {resp.hex()} ({list(resp)})")
            return resp
        except asyncio.TimeoutError:
            print(f"← TIMEOUT")
            return None

    # Step 1: INITIATE (0x10) - no data
    pkt_init = build_isecprogram_packet(0x10)
    print(f"Expected (from PCAP): 05e7011006606a")
    resp1 = await send_recv(pkt_init, "INITIATE (0x10)")

    if not resp1:
        print("\nFailed: no response to INITIATE")
        writer.close()
        return

    # Check for 0x90 (Ready) in response
    if 0x90 in resp1:
        print("✓ Got 0x90 (Ready)")
    else:
        print(f"WARNING: Expected 0x90 (Ready) in response")

    print()

    # Step 2: AUTH (0x11) - BCD password + 0x99 suffix
    print(f"Password: {PASSWORD!r} ({len(PASSWORD)} digits)")
    bcd_pwd = password_to_bcd(PASSWORD)
    print(f"BCD bytes: {[f'0x{b:02x}' for b in bcd_pwd]}")
    auth_data = bcd_pwd + [0x99]
    print(f"Auth payload (BCD+0x99): {[f'0x{b:02x}' for b in auth_data]}")

    pkt_auth = build_isecprogram_packet(0x11, auth_data)
    resp2 = await send_recv(pkt_auth, f"AUTH (0x11) BCD+0x99")

    if not resp2:
        print("\nFailed: no response to AUTH")
        writer.close()
        return

    if 0x53 in resp2:
        print("✓ Got 0x53 ('S' = Success)")
    elif 225 in resp2 or 0xe1 in resp2:
        print("✗ Got 0xe1 (Invalid password)")
        writer.close()
        return
    else:
        print(f"Unknown response")

    print()

    # Step 3: CONFIRM (0x19) - data=[0x11] to confirm the auth step
    pkt_confirm = build_isecprogram_packet(0x19, [0x11])
    resp3 = await send_recv(pkt_confirm, "CONFIRM (0x19) data=[0x11]")
    if resp3:
        print(f"Note: CONFIRM may NACK (known issue), session still works")

    print()

    # Step 4: STATUS (0x15) - get partial status
    pkt_status = build_isecprogram_packet(0x15)
    print(f"Expected (from PCAP): 05e70115067e71")
    resp4 = await send_recv(pkt_status, "STATUS (0x15)")

    if resp4:
        print(f"\nStatus response ({len(resp4)} bytes)")
        if len(resp4) > 4:
            status_byte = resp4[4]
            print(f"Status byte: 0x{status_byte:02x} = {status_byte:08b}b")
            is_armed = bool(status_byte & 0x01) or bool(status_byte & 0x02)
            print(f"  Armed: {is_armed}")
            if status_byte & 0x02:
                print(f"  Mode: armed_stay")
            elif status_byte & 0x01:
                print(f"  Mode: armed_away")
            else:
                print(f"  Mode: disarmed")

    writer.close()
    print("\nDone!")


asyncio.run(test_handshake())
