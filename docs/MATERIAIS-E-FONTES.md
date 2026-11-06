# Materiais locais e fontes primárias

## O que não acompanha o Git

Instaladores NI, firmware oficial, normalizados, desmontagens completas, PDFs, fotos, capturas USB/HID/MIDI brutas, backups de configurações Windows e bibliotecas clonadas são materiais locais. O repositório contém ferramentas e análises próprias, não uma autorização para redistribuir os originais.

Os scripts de pesquisa conservam caminhos relativos de referência para que o ambiente original seja reproduzível. Ausência de um arquivo num clone público não é falha comprovada de algoritmo; os testes que dependem dele são opcionais. Obtenha ferramentas e arquivos nos fornecedores correspondentes conforme suas condições de uso.

## Identificadores das imagens usadas na pesquisa

| Arquivo local esperado | SHA-256 |
|---|---|
| `firmware-research/official-firmware/Maschine-Mikro-MK1-FW55.official-payload.bin` | `3cbfb13ff2e884d4eb3a3ec9546121c2e29c2fc42f6189c5d1df9dedccb88003` |
| `firmware-research/fw55-analysis/FW55.bit-normalized.bin` | `8b9363b6155fcd230151ed67bc7d9708cfcd6b912800c2ac6f4ace4c4e0ecb5c` |

O segundo é a reversão dos bits de cada byte do primeiro; offsets preservados. Não é imagem autorizada para gravação. Para os verificadores diferenciais também é necessário o listing `firmware-research/fw55-analysis/architecture/segment1.annotated.asm`; ele não é redistribuído. `trace_fw55.py` documenta a geração local a partir da imagem normalizada usando Capstone. Outros auditores podem exigir o executável oficial pinado pelos próprios scripts.

## Referências

- [NI: drivers e arquivos](https://support.native-instruments.com/support/solutions/articles/69000882238-native-instruments-drivers-other-files)
- [XMOS: XS1 Ports, tabela de recursos](https://www.xmos.com/download/XS1-Ports-Specification%281_02%29.pdf)
- [XMOS: XS1-L02A-QF124](https://www.xmos.com/download/XS1-L02A-QF124-Datasheet%28N%29.pdf)
- [Microchip: USB3318](https://www.microchip.com/en-us/product/usb3318)
- [Datasheet AT25DF021, documento do fabricante hospedado na DigiKey](https://media.digikey.com/pdf/Data%20Sheets/Adesto/AT25DF021.pdf)
- [TI: SN74HC14](https://www.ti.com/product/SN74HC14)
- [XMOS sc_flash, revisão usada na comparação](https://github.com/xcore/sc_flash/tree/c39116c1e2269ec31f29c810f4158a9c50983d6c)
- [Image-Line: MIDI scripting](https://www.image-line.com/fl-studio-learning/fl-studio-online-manual/html/midi_scripting.htm)
- [HIDAPI](https://github.com/libusb/hidapi)

As URLs são referências de origem do trabalho, não uma alegação de que cada página foi novamente consultada nesta publicação. As datas e os limites dos ensaios estão nos relatórios. A fixture de dez detentes é uma redução de dados próprios, sem caminho ou identidade da unidade.
