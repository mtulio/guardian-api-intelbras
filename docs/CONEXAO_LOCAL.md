# Conexão Local Direta — AMT 2018 E Smart

## Visão Geral

Esta funcionalidade permite conectar diretamente a uma central de alarme AMT 2018 E Smart pela rede local (porta 9009), sem depender da nuvem Intelbras Guardian.

## Pré-requisitos

- Central AMT 2018 E Smart conectada à mesma rede local
- IP local da central (ex: `192.168.1.5`)
- **Senha de acesso remoto** de 6 dígitos (configurada no painel)

> **IMPORTANTE**: A senha de acesso remoto é diferente da senha master do painel.
> Para configurar: `Enter + Senha Master + 5 + 0 + XX XX XX` (6 dígitos).

## Como Funciona

### Protocolo ISECProgram

A comunicação local usa o protocolo **ISECProgram** encapsulado em **IsecNet** (`0xe7`).
Diferente da conexão via nuvem, não há necessidade de MAC, conta, ou autenticação no servidor.

### Fluxo de Conexão

```
Cliente                            Central AMT
   |                                  |
   |--- INITIATE (0x10) ------------>|
   |<-- Ready (0x90) ----------------|
   |                                  |
   |--- AUTH (0x11, BCD+0x99) ------>|
   |<-- Success (0x53) --------------|
   |                                  |
   |--- CONFIRM (0x19) ------------->|
   |<-- (pode dar NACK, é normal) ---|
   |                                  |
   |--- STATUS (0x15) -------------->|
   |<-- Status data (0x95) ----------|
```

### Formato do Pacote

```
[outer_size][0xe7][isecprog_size][cmd][data...][CRC16_hi][CRC16_lo][XOR_checksum]
```

- **outer_size**: tamanho do conteúdo após este byte
- **0xe7**: marcador do protocolo IsecNet
- **isecprog_size**: número de bytes de comando + dados
- **cmd**: código do comando ISECProgram
- **data**: dados do comando (opcional)
- **CRC16**: checksum CRC16 sobre `[isecprog_size, cmd, data...]`
- **XOR_checksum**: XOR de todos os bytes anteriores ⊕ 0xFF

### Codificação da Senha (BCD)

A senha é codificada em formato **BCD (Binary Coded Decimal)**:

| Senha   | BCD              | + Sufixo 0x99    |
|---------|------------------|-------------------|
| 123456  | `12 34 56`       | `12 34 56 99`     |
| 001234  | `00 12 34`       | `00 12 34 99`     |

### CRC16

Algoritmo customizado da Intelbras:
- Registrador de 24 bits
- Constante XOR: `0x00800500`
- Dados de entrada + 2 bytes zero de trailing
- Resultado: 16 bits (2 bytes: high, low)

## Uso via API

### Obter Status
```bash
curl -X POST http://localhost:8000/api/v1/alarm/local/status \
  -H "Content-Type: application/json" \
  -d '{"local_ip":"192.168.1.5","local_port":9009,"password":"123456"}'
```

### Resposta
```json
{
  "device_id": 0,
  "is_armed": false,
  "arm_mode": "disarmed",
  "is_triggered": false,
  "message": "OK"
}
```

## Uso via Interface Web

1. Acesse `http://localhost:8000/`
2. Na seção **"Método 3: Conexão Local (IP Receiver)"**
3. Preencha o **IP** da central
4. Deixe o campo **MAC vazio** (opcional para Local IP)
5. Insira a **senha de acesso remoto de 6 dígitos**
6. Clique em **"Obter Status"**

## Referências

- PCAP capturado do app oficial AMT Remoto (`intelbras-login.pcap`)
- SDK Centrais de Alarme Intelbras v1.0.1
- Manual de Instalação AMT 2018 E Smart
