# DFU, flash e imagem de fábrica dentro da FW55

Atualização física de 05/11/2026: as fotos da unidade identificaram U5 como Atmel 25DF021, confirmando visualmente a hipótese de modelo abaixo. Ainda não há leitura elétrica de ID ou backup. Consulte `firmware-research/physical-board/PLACA-MK1.md`.

Análise estática offline de 05/11/2026. Todas as posições de código neste texto são offsets do arquivo FW55 normalizado, não endereços físicos. A imagem oficial continua inalterada. Não foi acessado o USB, parado o serviço NI ou enviado comando de leitura/gravação nesta etapa.

## Perfil de flash identificado

Em `DP+3 words`, correspondente à área inicializada do arquivo em 0x53E4, há uma estrutura de 112 bytes. O startup da interface SPI em 0x10C–0x1B8 passa essa tabela para 0x3A76 e fornece contagem 1. O código de conexão usa passo 0x70 entre perfis e compara a identificação retornada pelo SPI com o campo de ID esperado.

O layout coincide com `fl_DeviceSpec` da biblioteca pública XMOS. Os campos da nossa imagem são:

| Campo | Valor configurado |
|---|---|
| Comando de identificação | 0x9F |
| Bytes de ID | 3 |
| ID esperado | 0x1F4300 |
| Página | 256 bytes |
| Número de páginas | 1024 |
| Capacidade calculada | 262144 bytes / 256 KiB |
| Bytes de endereço | 3 |
| Comando de leitura / dummy | 0x0B / 1 byte |
| Comando de programação | 0x02 |
| Unidade de apagamento pelo comando 0x20 | 4096 bytes |
| Setor lógico regular configurado | 65536 bytes |

Esses parâmetros correspondem ao perfil **ATMEL AT25DF021** publicado pela XMOS. O divisor de clock na NI é 4, enquanto o exemplo de referência usa 8; o identificador interno `flashId` também não deve ser confundido com o ID JEDEC. A capacidade acima pertence ao perfil compilado, não a uma medição atual da memória da unidade.

Referências primárias fixadas no commit `c39116c1e2269ec31f29c810f4158a9c50983d6c`:

- [Estrutura flash.h](https://github.com/xcore/sc_flash/blob/c39116c1e2269ec31f29c810f4158a9c50983d6c/module_flash/include/flash.h).
- [Perfil AT25DF021](https://github.com/xcore/sc_flash/blob/c39116c1e2269ec31f29c810f4158a9c50983d6c/module_flash/specs/ATMEL_AT25DF021.spispec).
- [Operações de imagem em flashlib.c](https://github.com/xcore/sc_flash/blob/c39116c1e2269ec31f29c810f4158a9c50983d6c/module_flash/src/flashlib.c).

O conhecimento do perfil permite planejar uma futura identificação física, mas não confirma fabricante/modelo do componente instalado nem revisão de PCB.

## Recursos SPI

O conjunto de argumentos e a estrutura de portas da biblioteca associam os recursos iniciais abaixo. São identificadores xCORE, não números de pinos:

| Sinal lógico | Recurso |
|---|---|
| MISO | 0x00010200 |
| SS | 0x00010000 |
| SCLK | 0x00010100 |
| MOSI | 0x00010300 |
| Clock block | 0x00000206 |

A relação desses recursos com pinos e trilhas da placa depende da identificação do processador exato.

## Entrada/saída do DFU

O dispatcher em 0x2264 compara os códigos de requisição padrão DFU e extensões F0–F6. O ramo USB F2 em 0x267C grava `0x11042011` no slot DP0x550; o ramo USB F3 em 0x268E limpa esse slot. Ambos marcam um retorno de controle. A inicialização em 0x2170 compara o mesmo marcador e, quando ele coincide, coloca o estado DFU em 2.

Isso liga o marcador ao modo DFU observado anteriormente, mas não prova que ele sobreviva a qualquer tipo de reset ou desligamento. Não identificamos seu endereço absoluto de RAM, e o código não deve ser descrito como alteração de flag na flash.

Os códigos internos do backend reutilizam números F1–F8 com outros papéis. Não confundir, por exemplo, o comando USB F3 de saída de modo com um F3 encaminhado internamente para acumular dados. A função 0x2784 pode enviar a operação por canal ou chamar o dispatcher local 0x2704.

## Escrita por páginas e conferência

O caminho local de dados chega a 0x2EC. Cada trecho de 64 bytes é copiado para `buffer + contador*64`. Ao atingir quatro trechos, chama 0x39E0 com o buffer de página.

Na função 0x39E0 é possível seguir a programação, a leitura de volta por 0x501C e a comparação por 0x4F2C, usando o tamanho da página do perfil. Assim, existe conferência de leitura após escrita nesse caminho compilado. Essa comparação local da página não substitui a verificação dos CRCs do contêiner nem comprova inicialização bem-sucedida após atualização.

O contador e a área de página são estado de runtime. O agrupamento 4×64→256 é coerente com o tamanho de transferência DFU que já foi medido na unidade e com o perfil de flash; não foi exercitada uma escrita física para validá-lo.

## Fábrica, atualização e proteção

| Rotina | Evidência |
|---|---|
| 0x38FE | Lê uma word no endereço flash0, normaliza seus bits e calcula `(word+2)*4`; lê o cabeçalho nesse offset e preenche um descritor com flag de fábrica=1 |
| 0x37F4 | Começa após início+tamanho do descritor fornecido, percorre limites de setores procurando a assinatura de imagem e preenche descritor com flag de fábrica=0 |
| 0x34AE / 0x34F4 | Inicializa cursor/limite de leitura e avança por páginas |
| 0x36C8 | Retorna recusa quando `descriptor[3]` indica fábrica; somente no outro caso segue o caminho de exclusão |
| 0x1F0 | Obtém descritor de fábrica, procura o próximo e ativa um indicador de atualização válida apenas quando essa procura tem sucesso |

Os formatos e o fluxo correspondem às funções públicas de localização de fábrica, próxima imagem, início de leitura e exclusão da biblioteca XMOS. Não foi demonstrado que o primeiro estágio de boot da NI seja idêntico a essa biblioteca ou que uma proteção nesse caminho impeça qualquer outro tipo de escrita.

O indicador em 0x1F0 também fortalece a hipótese para o upload DFU vazio anterior: a leitura pode depender de encontrar uma imagem de atualização separada. Ainda falta observar o valor desse indicador na unidade; não é uma conclusão sobre o conteúdo atual de sua flash.

## Procura do primeiro estágio nos arquivos locais

`scan_legacy_images.py` examinou seis binários explicitamente listados: dois atualizadores, Controller Editor, NIHardwareService e dois drivers. Encontrou 17 ocorrências da assinatura legada em cada atualizador, das quais nove tinham os dois CRCs consistentes no formato testado. Não encontrou essa assinatura nos outros quatro binários.

Essa varredura **não identifica um primeiro estágio sem cabeçalho legado**, conteúdo comprimido ou outra representação. Não foi recuperado um bootloader separado por esse método, e não se conclui que esteja ausente dos pacotes. O primeiro estágio continua sem backup.

## Reprodução e próximo marco

`audit_flash_backend.py` confere o hash da imagem, reconstrói o layout C da estrutura e verifica os 112 bytes contra os campos esperados. Exporta `flash-backend/analysis.json` e dez recortes de código. `legacy-image-inventory.json` conserva hashes, offsets e resultados da varredura dos seis binários.

Já há uma hipótese concreta de flash e recursos SPI para orientar a investigação. Os próximos passos são identificar o ID real por uma operação de leitura comprovada no código existente, ou confirmar o componente fisicamente; obter os bytes do primeiro estágio e o mapa real de regiões; e testar uma recuperação independente antes de uma gravação modificada. Nenhum comando novo foi acrescentado à lista permitida do coletor DFU.
