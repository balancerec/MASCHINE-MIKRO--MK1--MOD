# Identificação física da placa MK1

**Escopo atualizado em 05/11/2026:** o usuário fechou a MK1 e determinou continuar somente com documentação e evidências existentes. O plano de bancada abaixo é um registro anterior, suspenso; não é uma etapa solicitada agora. A reconstrução offline está em `../fw55-analysis/architecture/RECURSOS-XS1.md`.

Fotos fornecidas em `C:\Users\balancerec\Pictures\MK1`, examinadas em 05/11/2026. Foram vistas as 11 imagens. `photo-inventory.json` conserva caminhos, tamanhos, hashes e níveis de confiança. As fotos originais não foram modificadas.

## Identificação visual

| Peça | Leitura nas fotos | Resultado |
|---|---|---|
| Placa | MaschineMikro - PCB01-04-00 | Revisão impressa visível na vista geral |
| U5, oito terminais | ATMEL / 25DF021 / SSH | AT25DF021; identificação visual do modelo confirma a hipótese anterior da firmware |
| U1 | XMOS / US1136L2 C5 / PBW750.00 | Família XMOS L2; código de pedido XS1-L02A-QF124-C5 é uma inferência compatível, ainda não uma identificação inequívoca de encapsulamento |
| Chip acima de U1 | SMSC / USB3318 | Transceptor USB; designador da PCB não determinado com segurança |
| U25 | Logotipo TI / HC14 | Família 74HC14 provável; resto da marcação não está legível o suficiente para fechar o código de pedido |
| Traseira do LCD | U.R.T. No.110921-0005; trecho G574JD-2F | Identificação parcial da montagem, não do controlador LCD |

As imagens mais úteis para U5 são `19.44.24` e `19.44.37 (1)`; para U1, `19.44.22`; para SMSC, `19.44.37`; para a revisão da placa, `19.44.40 (1)` e `19.44.41`.

A AT25DF021 é uma flash SPI de 2 Mbit, equivalente a 256 KiB, com páginas de 256 bytes, de acordo com seu datasheet original. Isso coincide com o perfil de 112 bytes reconstruído da FW55. O componente instalado agora tem identificação visual; ainda não houve leitura elétrica de ID JEDEC, conferência de tensão ou extração de conteúdo.

O [datasheet USB3318 da Microchip](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/3318.pdf) confirma sua função de PHY USB com interface ULPI. A [documentação TI HC14](https://www.ti.com/product/SN74HC14) descreve inversores com entrada Schmitt; a marcação vista não autoriza atribuir a U25 uma função específica no circuito sem seguir suas trilhas. Não foi identificado um ADC pelas fotos.

A [referência de marcações XMOS](https://www.xmos.com/file/xmos-part-numbers-and-part-markings/?version=latest) e o [datasheet XS1-L02A-QF124](https://www.xmos.com/download/XS1-L02A-QF124-Datasheet%28N%29.pdf) dão contexto à marcação L2/C5. O nome do fabricante e a marcação transcrita são a evidência direta; a interpretação do código de pedido permanece separada.

## Pinagem de U5: referência de bancada

Foi obtido o datasheet original AT25DF021, revisão 3677F–DFLASH–5/2013, por seu [espelho na DigiKey](https://media.digikey.com/pdf/Data%20Sheets/Adesto/AT25DF021.pdf). A página 4 foi renderizada e conferida visualmente: `pinout-at25df021.png`.

Vista de cima do encapsulamento, com a orientação do pino1 previamente identificada:

| Pino | Função |
|---|---|
| 1 | CS, seleção ativa em nível baixo |
| 2 | SO / MISO |
| 3 | WP, proteção ativa em nível baixo |
| 4 | GND |
| 5 | SI / MOSI |
| 6 | SCK |
| 7 | HOLD, ativo em nível baixo |
| 8 | VCC |

Não aplicar essa tabela como “esquerda/direita” diretamente à fotografia: U5 aparece girado em algumas imagens e a marca física do pino1 ainda precisa ser localizada com segurança. A rotação do texto não substitui a marcação do encapsulamento.

## Plano anterior com o multímetro — suspenso

O usuário dispõe somente de multímetro. Ele permite conferir continuidade, resistência e tensão, mas não realizar o protocolo SPI necessário ao dump de 262144 bytes.

Etapa de continuidade proposta, ainda não realizada:

1. Remover USB e qualquer alimentação. Não usar continuidade/resistência na placa energizada.
2. Identificar a marca do pino1 de U5 e conferir orientação com o desenho do datasheet.
3. Identificar um ponto de GND pela continuidade ao pino4 de U5. A carcaça metálica do USB não deve ser assumida como GND sem medição.
4. Registrar quais pontos acessíveis têm continuidade com os pinos 1, 2, 5 e 6; considerar possíveis resistores em série e anotar resistência, não apenas presença de bip.
5. Mapear o pino8 a um ponto de alimentação acessível. Um ponto ser rotulado +3V3 na placa não comprova, sozinho, sua ligação ao pino8.

Não medir os terminais apertados do XMOS diretamente nem fazer pontes. Testes com alimentação, montagem de pinça e conexão de programador ficam para depois da orientação e alimentação confirmadas. Não foi escolhido um leitor ou uma tensão de operação a partir apenas das fotos.

## O que muda para a firmware própria

Agora conhecemos fisicamente a localização da flash U5 e seu modelo. Isso abre um caminho concreto para um backup SPI integral, mas ainda não fornece esse backup. A leitura em circuito pode alimentar outras partes da placa ou sofrer disputa no barramento; sua viabilidade precisa ser determinada, não presumida.

As ilhas em duas colunas próximas ao XMOS e TP1/TP2/TP3 são locais de investigação. Nenhum foi identificado como JTAG ou ligação segura para um adaptador. Falta uma vista do outro lado da PCB e detalhes legíveis da marca do pino1 de U5 e das ilhas para preparar o mapa de continuidade específico.
