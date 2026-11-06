# CRCs do contêiner XMOS da FW55: fórmula validada

Resultado de 05/11/2026, obtido offline. Nenhum acesso ao equipamento, comando DFU ou gravação foi realizado.

## Descoberta

Os campos anteriormente não resolvidos no cabeçalho normalizado foram reproduzidos exatamente:

| Campo | Cobertura, início incluído e fim excluído | Armazenado | Calculado |
|---|---|---|---|
| uint32 em 0x04 | bytes 0x10–0x100 | 0x672E96EC | 0x672E96EC |
| uint32 em 0x08 | bytes 0x10–0x7DC4 | 0x48351D0A | 0x48351D0A |

O fim da segunda região vem do uint32 em 0x0C: 32196 bytes. A primeira região cobre os 240 bytes finais da primeira página de 256 bytes, incluindo metadados e início do código. A segunda inclui a mesma área inicial e o resto do conteúdo declarado. Os primeiros 16 bytes e os 60 bytes finais de padding não entram nessas regiões.

Essa identificação é uma inferência computacional fortemente corroborada. Não é um trace da rotina do carregador da unidade nem identifica seu endereço em flash.

## Algoritmo reproduzido

Primeiro, inverter os bits dentro de cada byte do payload oficial. Interpretar words little endian. Inicializar o registrador CRC com FFFFFFFF e usar o polinômio refletido EDB88320. Incorporar os dados com a semântica da instrução CRC32 XMOS; ao final, incorporar mais uma word FFFFFFFF.

Para cada bit de uma word de dados, do bit 0 ao 31:

```
old_low = crc & 1
crc = (crc >> 1) | (data_bit << 31)
if old_low:
    crc ^= 0xEDB88320
```

Isso insere os bits no topo do registrador, em vez de usar diretamente o algoritmo usual de zlib. A rotina de referência usa os passos bit a bit; uma segunda implementação usa tabela de 256 entradas. Ambas reproduziram os resultados sobre as duas regiões da MK1.

A semântica da instrução é descrita no documento primário [The XMOS XS1 Architecture](https://www.xmos.com/download/The-XMOS-XS1-Architecture%281.0%29.pdf), seção CRC. A pista da primeira página veio da [AN00109 — Multiple Firmware Booting](https://www.xmos.com/file/an00109-multiple-firmware-booting?version=1.0.0): o carregador genérico ali descrito verifica a primeira página antes de avaliar uma imagem candidata. O código exato da NI não foi identificado por essa referência.

## Validação cruzada e alterações controladas

O verificador percorreu as 14 entradas da tabela do atualizador 1.2.0. Nove payloads foram compatíveis com esta interpretação do formato, incluindo a MK1. Os dois CRCs coincidiram em todos os nove, sem ajustar a fórmula por produto. Cinco outras entradas ficaram fora do formato/limites tratados; não foram classificadas como corrompidas.

Sete alterações de um byte foram testadas somente em memória:

- Offsets 32, 128 e 255: falharam os dois CRCs.
- Offsets 256, 500 e 32195: o CRC da primeira página continuou válido e o do conteúdo falhou.
- Offset 32255, no padding: ambos continuaram válidos, conforme as regiões inferidas.

O último teste evidencia que verificar esses CRCs não detecta todas as alterações do arquivo inteiro. O hash SHA256 da fonte continua sendo necessário para identificar exatamente o payload oficial.

## Artefatos e consequência prática

`firmware-research/verify_xmos_image_crc.py` verifica sem reescrever arquivos de firmware. `legacy-crc-validation.json` conserva valores esperados/calculados, hashes, entradas de validação cruzada e resultados dos sete testes. `inspect_boot_container.py` agora inclui esses resultados, e os cinco testes estruturais foram atualizados para exigir CRCs válidos na imagem oficial e CRC inválido numa alteração de código.

Este resultado substitui a classificação de 0x04/0x08 como desconhecidos nos relatórios anteriores. As words finais dos segmentos continuam sem semântica identificada; as tentativas anteriores de tratá-las como CRC não encontraram correspondências porque a hipótese de localização não estava estabelecida.

Já podemos verificar a consistência desses campos de um contêiner legado da MK1. Isso não comprova ausência de outras verificações, compatibilidade elétrica, assinatura criptográfica, comportamento de secure boot ou recuperação após falha. A imagem oficial foi preservada; nenhum pacote modificado instalável ou ferramenta de gravação foi gerado.

O próximo alvo é o primeiro estágio de boot e a ligação desse mecanismo de CRC à seleção de imagens na flash real. Sem backup desse estágio ou identificação física da memória, a recuperação continua não comprovada.
