# Imagem de atualização da MK1: identificação do contêiner

Atualização posterior de 05/11/2026: os campos 0x04/0x08 foram identificados e seus CRCs reproduzidos, com validação em nove imagens oficiais. Consulte [CRC-LEGADO.md](CRC-LEGADO.md). As classificações como desconhecidos e a ausência de validação de CRC abaixo registram a etapa anterior; o inspetor atual já verifica esses dois campos. A compatibilidade de gravação e a recuperação continuam sem validação.

Análise offline de 05/11/2026. Não foram abertos dispositivos USB, parado o serviço NI ou enviados comandos DFU nesta etapa.

## Avanço confirmado

A imagem oficial FW55 usa a assinatura do formato legado de imagem XMOS: `0x01A551E5` após normalização. O código-fonte público de `sc_flash` define essa mesma assinatura e usa `byterev(bitrev(word))`, equivalente à inversão de bits em cada byte que já tornava nossa imagem legível.

O mesmo código interpreta a word no offset 0x10 como versão da imagem e a word no offset 0x14 como seu tamanho para navegação entre imagens. A variante posterior tem outra assinatura e offsets diferentes. Esta correspondência identifica o formato, não a revisão exata do compilador nem o chip físico.

Referência fixada: [XMOS sc_flash, flashlib.c, commit c39116c](https://github.com/xcore/sc_flash/blob/c39116c1e2269ec31f29c810f4158a9c50983d6c/module_flash/src/flashlib.c), funções `fl_getFactoryImage` e `fl_getNextBootImage`. Cópia local e hash: `evidence/xmos-sc-flash-pinned.c` e `.json`. A assinatura aparece na linha 10; normalização nas linhas 15–18; interpretação dos campos nas linhas 554–558 e 574–580 da cópia.

## Campos da nossa imagem

Offsets abaixo são posições no arquivo normalizado, não endereços de flash ou RAM.

| Offset | Valor | Interpretação e confiança |
|---|---|---|
| 0x00 | 0x01A551E5 | Assinatura legada XMOS, correspondência com fonte pública |
| 0x04 | 0x672E96EC | Não resolvido; não chamar de CRC ou assinatura criptográfica sem prova |
| 0x08 | 0x48351D0A | Não resolvido |
| 0x0C | 32196 | Fim do conteúdo neste arquivo, inferência pelos segmentos |
| 0x10 | 1 | Versão do contêiner segundo a convenção da biblioteca; não é a versão NI 55 |
| 0x14 | 32196 | Tamanho usado para navegação entre imagens na biblioteca |
| 0x18 | 2 | Quantidade inferida de entradas da tabela |
| 0x1C–0x33 | Duas entradas de 12 bytes | Offset, flags ainda desconhecidas, tamanho em words; inferência estrutural consistente |

Segmentos: 0x34–0x61A4 (24944 bytes) e 0x61A4–0x7DC4 (7200 bytes), com limites finais exclusivos. Ambos contêm código xCORE já analisado. O payload tem 32256 bytes e termina com 60 bytes zero após a área declarada. Não inferir tamanho de setor físico a partir desse padding.

O payload começa pela assinatura de imagem. Já a rotina genérica XMOS para encontrar a imagem de fábrica primeiro interpreta um comprimento de carregador no início da flash e só depois procura a assinatura. Isso reforça a distinção entre nosso payload de atualização e uma cópia integral da flash. Não determina sozinho o que o atualizador NI grava ou quais regiões ele preserva.

## Integridade: resultado limitado

Foi criado `firmware-research/inspect_boot_container.py`, que apenas lê arquivos e produz `boot-container.json`. Verifica assinatura, limites, contiguidade dos segmentos, hashes e padding. Não valida autenticidade ou aceitação pelo bootloader.

As últimas words dos segmentos são 0xCF5553B5 e 0x0863DF7C. Foram testadas 840 combinações de CRC32 padrão para cada segmento, variando início, prefixos, ordem de bytes por word, estado inicial e XOR final. Nenhuma coincidiu. Isso rejeita apenas essas hipóteses: as últimas words ainda não foram estabelecidas como CRCs. Não há conclusão de criptografia ou bloqueio.

A arquitetura XMOS possui instrução CRC cuja incorporação de bits difere do algoritmo direto habitual. Referência primária: [The XMOS XS1 Architecture](https://www.xmos.com/download/The-XMOS-XS1-Architecture%281.0%29.pdf), seção CRC. Essa diferença deve ser considerada ao rastrear as rotinas reais; não justifica escolher uma variante apenas por tentativa.

Cinco testes passaram: imagem conhecida, reversibilidade da transformação, rejeição de truncamento, rejeição de segmento fora de limites e demonstração explícita de que uma alteração em código não é detectada como erro de CRC pelo inspetor estrutural.

## O próximo marco para firmware própria

1. Rastrear quem verifica os campos 0x04/0x08 e quais regiões entram no cálculo. O payload sozinho pode não conter o primeiro estágio responsável.
2. Relacionar o contêiner ao caminho de download do atualizador oficial sem executar gravação.
3. Confirmar modelo do xCORE, flash e pinagem. Dois segmentos não provam dois chips nem dois tiles físicos.
4. Obter backup integral ou demonstrar recuperação independente da aplicação. O upload DFU vazio anterior continua sem fornecer esse backup.

Ainda não há imagem modificada pronta para instalação. O avanço desta etapa é um formato de contêiner identificado com referência verificável e um inspetor reproduzível, mantendo explícitos os campos que faltam resolver.
