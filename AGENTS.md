# AGENTS.md

## Project overview

Guardian API Intelbras is a FastAPI middleware that proxies between applications and Intelbras alarm panels.
It supports Cloud (Intelbras Guardian API), IP Receiver (ISECNet V1/V2), and direct Local IP (ISECProgram on port 9009) connections.

## Setup commands

- Build and start: `cd docker && podman-compose up -d --build`
- Rebuild after code changes: `cd docker && podman-compose down && podman-compose up -d --build`
- View logs: `podman logs -f intelbras-guardian-api`
- Health check: `curl http://localhost:8000/api/v1/health`

## Code style

- Python 3.11+, FastAPI, Pydantic
- Use `async/await` for all network operations
- Logging via `logger = logging.getLogger(__name__)`
- Type hints on all function signatures

## Project structure

```
intelbras-guardian-api/
├── app/
│   ├── api/v1/
│   │   ├── __init__.py           # Router registration (order matters!)
│   │   ├── alarm.py              # Cloud/IP Receiver endpoints
│   │   └── alarm_local.py        # Local IP endpoints (MAC optional)
│   ├── services/
│   │   ├── isecnet_protocol.py   # Protocol: ISECNet V1/V2 + ISECProgram
│   │   └── isecnet_client.py     # Connection manager
│   └── static/
│       └── index.html            # Web UI (Alpine.js)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
└── .agents/
    ├── scripts/                  # Standalone test/investigation scripts
    │   ├── test_isecprogram.py   # ISECProgram handshake test
    │   └── test_direct.py        # Raw V1/V2 command test
    └── workflows/
        └── isecprogram-command.md
```

## Testing

```bash
# Test local connection via curl (no MAC required):
curl -s -X POST "http://localhost:8000/api/v1/alarm/local/status" \
  -H "Content-Type: application/json" \
  -d '{"local_ip":"192.168.1.5","local_port":9009,"password":"YOUR_6_DIGIT_PASSWORD"}' | jq

# Test ISECProgram handshake standalone:
python3 .agents/scripts/test_isecprogram.py YOUR_6_DIGIT_PASSWORD 192.168.1.5 9009
```

## Important conventions

- **Router order**: `alarm_local_router` MUST be included BEFORE `alarm_router` in `__init__.py`, otherwise `/alarm/local/*` is captured as `/{device_id}/*`
- **Docker rebuild required**: Code is copied into the image, not mounted. Every change needs `podman-compose up -d --build`
- **Password types**: Local ISECProgram uses a 6-digit remote access password (BCD encoded), which is different from the panel master password

## Protocol reference

Detailed protocol documentation is in:

- `docs/CONEXAO_LOCAL.md` — Local ISECProgram protocol (packet format, CRC16, BCD, handshake flow)
- `docs/IMPLEMENTATION_PLAN.md` — Next steps and known ISECProgram commands
- The workflow `.agents/workflows/isecprogram-command.md` describes how to implement new ISECProgram commands

### Quick protocol summary

| Protocol | Use Case | Port | Password Format |
|----------|----------|------|-----------------|
| ISECNet V2 | Cloud | 9009 (relay) | V2 auth packet |
| ISECNet V1 | IP Receiver / V1 Cloud | 9009/9015 | ASCII in each command |
| ISECProgram | Direct Local IP | 9009 (panel) | BCD + 0x99 suffix |

### ISECProgram packet format

```
[outer_size][0xe7][isecprog_size][cmd][data...][CRC16_hi][CRC16_lo][XOR_checksum]
```

- CRC16: 24-bit register, XOR constant `0x00800500` (see `_crc16()` in `isecnet_protocol.py`)
- XOR checksum: XOR all preceding bytes ^ 0xFF
- BCD password: "123456" → `[0x12, 0x34, 0x56]`, always followed by `0x99`

### ISECProgram handshake

1. `0x10` INITIATE → response `0x90` (Ready)
2. `0x11` AUTH (BCD password + `0x99`) → response `0x53` (Success)
3. `0x19` CONFIRM → may NACK (known issue, session works anyway)
4. `0x15` STATUS → response `0x95` + status byte
