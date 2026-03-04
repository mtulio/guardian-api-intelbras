# PR: feat: implementar conexão local direta via ISECProgram (AMT 2018 E Smart)

## Descrição

Implementa suporte à conexão local direta com centrais de alarme AMT 2018 E Smart pela porta 9009,
sem necessidade de nuvem Intelbras Guardian ou conta de IP Receiver (MAC).

Utiliza o protocolo **ISECProgram** encapsulado em IsecNet (`0xe7`), validado contra capturas
PCAP do aplicativo oficial AMT Remoto.

## Mudanças

### Backend (`isecnet_protocol.py`)
- **CRC16**: Implementação do algoritmo CRC16 customizado da Intelbras (registrador 24-bit, constante XOR `0x00800500`), validado contra 4 pacotes PCAP conhecidos
- **BCD Password**: Conversão de senha para formato BCD (ex: "123456" → `[0x12, 0x34, 0x56]`)
- **ISECProgram Packet Builder**: Construção de pacotes no formato `[size][0xe7][isecprog_size][cmd][data][CRC16][checksum]`
- **Handshake Local**: 3 passos: INITIATE(0x10) → AUTH(0x11, BCD+0x99) → CONFIRM(0x19)
- **Status Local**: Comando ISECProgram `0x15` para obter estado da central
- **_is_local_ip flag**: Diferenciação entre IP Receiver (com MAC) e Local IP (sem MAC)

### Backend (`alarm_local.py`)
- Campo `mac` agora é `Optional[str]` (antes era obrigatório)
- Default `mac = ""` quando não informado

### Backend (`__init__.py`)
- `alarm_local_router` incluído ANTES de `alarm_router` para evitar que "local" seja capturado como `{device_id}`

### Frontend (`index.html`)
- Campo MAC marcado como "Opcional para Local IP"
- Botões de ação habilitados sem MAC preenchido (apenas IP + senha são obrigatórios)

## Testes Realizados

1. ✅ PCAP validation: CRC16 validado contra 4 pacotes do AMT Remoto (100% match)
2. ✅ Script standalone (`test_isecprogram.py`): handshake completo INITIATE→AUTH→STATUS
3. ✅ API curl: `POST /api/v1/alarm/local/status` retorna JSON com estado da central
4. ✅ Router fix: endpoint local não é mais capturado como `/{device_id}`

## Resultado da API

```json
{
  "device_id": 0,
  "is_armed": false,
  "arm_mode": "disarmed",
  "message": "OK"
}
```

## Limitações Conhecidas

- O byte de status (0x15) retorna apenas 1-2 bytes — mapeamento de bits precisa refinamento
- CONFIRM (0x19) retorna NACK, mas a sessão funciona normalmente
- Arm/Disarm via local ainda não implementado (próximo passo)
- Não há keep-alive — cada request reconecta

## Arquivos

| Arquivo | Alteração |
|---------|-----------|
| `intelbras-guardian-api/app/services/isecnet_protocol.py` | CRC16, BCD, ISECProgram, connect local |
| `intelbras-guardian-api/app/api/v1/alarm_local.py` | MAC opcional |
| `intelbras-guardian-api/app/api/v1/__init__.py` | Router order fix |
| `intelbras-guardian-api/app/static/index.html` | Frontend MAC opcional |
| `.agents/scripts/test_isecprogram.py` | Script de teste standalone |
| `AGENTS.md` | Guia para agentes de IA |
| `docs/CONEXAO_LOCAL.md` | Documentação em português |
| `docs/IMPLEMENTATION_PLAN.md` | Próximos passos |
