# Plano de Implementação — AMT 2018 E Smart

## Status Atual

**Implementado e testado:**
- [x] Conexão local via ISECProgram (porta 9009)
- [x] Handshake: INITIATE (0x10) → AUTH (0x11 BCD) → STATUS (0x15)
- [x] CRC16 validado contra PCAP
- [x] API endpoint `/api/v1/alarm/local/status`
- [x] Frontend com MAC opcional
- [x] Router fix (alarm_local antes de alarm)

## Próximos Passos

### Prioridade Alta

#### 1. Refinar interpretação do byte de status (0x15)
O comando `0x15` retorna apenas 1-2 bytes. Precisamos mapear os bits corretamente:
- **Bit 0**: Armado total?
- **Bit 1**: Armado parcial?
- **Bit 3**: Alarme disparado?
- **Bit 6**: Partição A armada?

**Ação**: Testar armando/desarmando o painel e coletando o byte de status em cada estado.

#### 2. Implementar GET_COMPLETE_STATUS via ISECProgram
O PCAP mostra comando `0x17` que pode ser uma consulta de status estendido.
Testar enviando `0x17` e analisar a resposta.

**Alternativa**: Enviar os comandos V1 tradicionais (`0x5A`, `0x5B`, `0x5D`) encapsulados
em ISECProgram para obter status completo com zonas e partições.

#### 3. Arm/Disarm via ISECProgram
Implementar os comandos de armar/desarmar localmente:
- Descobrir o código ISECProgram equivalente ao ARM/DISARM
- Pode ser `0x41` ('A') ou outro código no formato ISECProgram
- Testar com PCAP comparativo (capturar tráfego do AMT Remoto ao armar/desarmar)

### Prioridade Média

#### 4. Status de Zonas
Obter lista de zonas abertas/fechadas/violadas.
Provavelmente requer comando ISECProgram adicional ou status estendido.

#### 5. Status de Partições
Para centrais com partições habilitadas, obter estado individual de cada partição.

#### 6. Bypass de Zonas
Implementar anulação temporária de zonas via ISECProgram local.

#### 7. Reconexão automática
A conexão local não mantém sessão persistente — cada request reconecta.
Considerar pool de conexões com keep-alive para melhorar performance.

### Prioridade Baixa

#### 8. PGM (Saídas Programáveis)
Controle de PGMs via conexão local.

#### 9. Leitura de Eventos
Obter histórico de eventos (aberturas, fechamentos, alarmes) via local.

#### 10. Detecção automática de modelo
Ao conectar, identificar automaticamente o modelo da central para
usar o comando de status correto (`0x5A` vs `0x5D`).

## Comandos ISECProgram Conhecidos

| Código | Nome          | Dados              | Resposta       |
|--------|---------------|---------------------|----------------|
| 0x10   | INITIATE      | (nenhum)            | 0x90 (Ready)   |
| 0x11   | AUTH          | BCD pwd + 0x99      | 0x53 (Success) |
| 0x15   | STATUS        | (nenhum)            | 0x95 + data    |
| 0x17   | ??? (PCAP)    | (nenhum)            | ???            |
| 0x19   | CONFIRM       | [cmd_confirmado]    | 0x99 ou NACK   |

## Como Capturar Novos Comandos

1. Conecte o celular na mesma rede da central
2. Inicie captura com `tcpdump -i any -w captura.pcap port 9009`
3. Use o app AMT Remoto para executar a ação desejada (armar, desarmar, etc.)
4. Pare a captura e analise com `tshark`:
   ```bash
   tshark -r captura.pcap -T fields -e ip.src -e tcp.payload
   ```
5. Decodifique os pacotes usando o formato ISECProgram documentado
