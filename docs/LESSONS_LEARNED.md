# Lições Aprendidas — Protocolo Intelbras

Registro de descobertas, armadilhas e nuances identificadas durante o desenvolvimento do Guardian API Intelbras. Este documento serve como base de conhecimento para evitar repetir investigações futuras.

---

## 1. Porta 9009 tem DOIS protocolos diferentes

A porta 9009 é usada tanto para conexão **via nuvem/IP Receiver** quanto para **conexão local direta**, mas com protocolos completamente diferentes:

| Cenário | Protocolo | Senha | Handshake |
|---------|-----------|-------|-----------|
| Nuvem/IP Receiver | ISECNet V1 (`0xE9 + 0x21 + ASCII`) | ASCII no comando | GET_BYTE → CONNECT → AUTH |
| Local direto | ISECProgram (`0xe7` wrapper + CRC16) | BCD + 0x99 | INITIATE → AUTH → CONFIRM |

**Armadilha**: Enviar comandos ISECNet V1 diretamente ao painel local resulta em "Incorrect Password" (0xE1) — o painel aceita o pacote mas rejeita a senha ASCII. O formato correto para local é ISECProgram com senha BCD.

---

## 2. CRC16 é obrigatório para ISECProgram

Todos os pacotes ISECProgram necessitam de CRC16 após os dados. Sem CRC16 válido, **o painel ignora silenciosamente o pacote** (sem resposta, causa timeout).

- **Algoritmo**: Registrador de 24 bits, constante XOR `0x00800500`
- **Dados de entrada**: `[isecprog_size, cmd, data...]` + 2 bytes zero trailing
- **Validação**: CRC16 foi validado contra 4 pacotes do PCAP do AMT Remoto com 100% de match

---

## 3. Senha Local vs Nuvem

| Tipo | Dígitos | Codificação | Uso |
|------|---------|-------------|-----|
| Senha master | 4-6 | N/A | Teclado do painel |
| Senha nuvem (V1) | 4-6 | ASCII | Comandos ISECNet V1 (0xE9) |
| Senha acesso remoto | 6 | BCD + sufixo 0x99 | ISECProgram (local) |

**Armadilha**: A "senha de acesso remoto" configurada no painel é diferente da senha master. Para descobrir qual é: `Enter + Senha Master → Programação → Acesso Remoto`.

---

## 4. BCD (Binary Coded Decimal)

- Cada dígito ocupa 4 bits (um nibble)
- Dois dígitos por byte
- Sempre seguido do sufixo `0x99`
- Nibble > 9 (ex: 0xA-0xF) NÃO é BCD válido

Exemplo: `"123456"` → `[0x12, 0x34, 0x56, 0x99]`

---

## 5. CONFIRM (0x19) retorna NACK mas funciona

O passo CONFIRM do ISECProgram frequentemente retorna `03 e7 00 00 1b` (NACK). Este é um comportamento **documentado e esperado** — a sessão continua funcional e os comandos seguintes (STATUS, ARM, etc.) são executados normalmente.

A hipótese é que o CONFIRM exige um "session-level link" (possivelmente E3/E4 do IP Receiver) que não é necessário para o fluxo local básico.

---

## 6. FastAPI Router Order (Bug de Deploy)

A rota `/api/v1/alarm/local/*` DEVE ser registrada ANTES de `/api/v1/alarm/{device_id}/*` no FastAPI:

```python
# ✅ Correto
api_router.include_router(alarm_local_router, prefix="/alarm/local")
api_router.include_router(alarm_router, prefix="/alarm")

# ❌ Errado — "local" é capturado como device_id
api_router.include_router(alarm_router, prefix="/alarm")
api_router.include_router(alarm_local_router, prefix="/alarm/local")
```

**Sintoma**: Retorna erro `422 Unprocessable Entity` porque tenta validar "local" como device_id.

---

## 7. Docker Container Rebuild

O `docker-compose.yml` copia o código para dentro da imagem (não monta volumes). Toda alteração de código requer:

```bash
podman-compose down && podman-compose up -d --build
```

Apenas restartar o container **NÃO aplica** as mudanças.

---

## 8. Verificação de Protocolo via PCAP

Ferramenta mais confiável para descobrir novos comandos:

```bash
# Capturar tráfego enquanto usa o app AMT Remoto:
tcpdump -i any -w captura.pcap port 9009

# Extrair payloads:
tshark -r captura.pcap -T fields -e ip.src -e ip.dst -e tcp.payload

# Decodificar pacotes (ver .agents/scripts/test_isecprogram.py)
```

---

## 9. Referências de código APK

O aplicativo Guardian Android (APK) foi a fonte primária para engenharia reversa:

- `ISECNetServerProtocol.kt` — Handshake de servidor V1
- `ISECNetProtocol.kt` — Protocolo ISECNet V1
- `ISECNetV2Protocol.java` — Protocolo ISECNet V2
- `ISECNetParserHelper.java` — Parser de status
- `SDKListExtensionsKt.checkSum()` — Checksum XOR ^ 0xFF
- `AlarmModel.java` — Códigos de modelos

O protocolo ISECProgram (local) NÃO está no APK Guardian — foi descoberto via PCAP do AMT Remoto.
