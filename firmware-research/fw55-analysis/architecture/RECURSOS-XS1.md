# Recursos XS1 da MK1: reconstrução offline

Atualizado em 05/11/2026. O equipamento está fechado por decisão do usuário. A investigação prossegue com fotos existentes, datasheets, FW55 oficial e capturas anteriores; medições e leitura física de memória ficam suspensas.

## Resultado reproduzível

`map_xs1_resources.py` lê os valores iniciais dos slots DP dos wrappers já identificados na FW55, verifica o SHA-256 da imagem e traduz os identificadores pela tabela 2, página 32, de [XS1 Ports: use and specification 1.02](https://www.xmos.com/download/XS1-Ports-Specification%281_02%29.pdf). O resultado estruturado está em `xs1-resource-map.json`.

A ordem dos identificadores de portas de um bit não é alfabética: por exemplo, `0x10200` significa `1A`, enquanto `0x10000` significa `1B`. Usar uma sequência alfabética simples produziria um mapa errado.

| Serviço | Contexto de segmento | Portas identificadas | Evidência no código |
|---|---|---|---|
| Flash SPI | 0 | 1A=MISO, 1B=SS, 1C=SCLK, 1D=MOSI | Slots DP 1F–22; estrutura `fl_SPIPorts` e inicialização da biblioteca |
| Display | 1 | 8C, 8A, 1A | Wrapper 0x67A8 chama serviço 0x6570 |
| Aquisição dos pads | 1 | 8B, 1J, 1I, 1H | Wrapper 0x67BC chama serviço 0x6830 |
| Botões | 1 | 1L, 1M, 1K | Wrapper 0x67DC chama serviço 0x62AC |
| LEDs | 1 | 1E, 1C, 1F, 1D, 1N | Wrapper 0x67F8 chama serviço 0x6944 |

Os endereços acima são offsets de arquivo na imagem normalizada. Fora da flash, a lista preserva a ordem dos argumentos de porta do wrapper; ainda não atribui a cada sinal funções como latch, seleção ou clock. Blocos de clock são registrados separadamente nos dados anteriores e não devem ser interpretados como portas.

## O que os datasheets permitem concluir

O AT25DF021 fotografado é compatível com o perfil SPI encontrado na firmware: 256 KiB, páginas de 256 bytes e comandos de identificação, leitura, programação e apagamento já reconstruídos. Isso identifica a interface utilizada, mas não recupera o conteúdo instalado.

O USB3318 identifica a camada física USB/ULPI. A família XMOS L2 é compatível com processamento distribuído entre tiles. A marcação HC14 sugere inversores Schmitt, mas não revela seu uso específico na placa. O controlador exato do LCD e componentes analógicos dos pads continuam sem identificação suficiente.

## Limites do mapa

- Nomes como `1A` e `8B` são recursos locais a um tile, não números de terminais do encapsulamento nem trilhas medidas.
- A ordem dos segmentos ainda não comprova o número físico de cada tile. Portas de mesmo nome em contextos distintos não devem ser fundidas.
- A identificação visual do XMOS não fecha de forma inequívoca o código completo de pedido. Não foi criado um esquema elétrico a partir de suposições.
- Datasheets não contêm o bootloader específico da unidade, conteúdo de OTP ou uma cópia da flash. A imagem oficial de atualização não equivale a um backup integral.

## Continuação sem abrir o equipamento

**Avanço realizado:** o fluxo dos argumentos e as sequências de saída/entrada foram reconstruídos em [SINAIS-E-SEQUENCIAS.md](SINAIS-E-SEQUENCIAS.md), com evidências verificadas nos bytes da FW55. A tabela acima permanece como inventário da etapa inicial; a interpretação funcional atual está nesse novo relatório e em `signal-roles.json`.

1. Seguir cada argumento nos serviços para distinguir dados, seletores, strobes e blocos de clock.
2. Reconstruir sequências e temporização a partir das instruções XS1 e constantes da FW55.
3. Implementar modelos offline dos drivers e comparar suas mensagens com as capturas e calibrações existentes.
4. Separar o código independente de hardware da camada de portas e do processo de boot, mantendo as lacunas documentadas.

Nenhuma escrita na flash ou acesso ao dispositivo foi realizado para produzir este mapa. Ele permite avançar na reconstrução dos drivers, mas ainda não caracteriza uma firmware pronta para gravação.
