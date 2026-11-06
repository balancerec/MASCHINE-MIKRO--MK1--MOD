# Caminho da imagem MK1 no atualizador NI 1.2.0

Atualização posterior: [CRC-LEGADO.md](CRC-LEGADO.md) reproduz os campos 0x04/0x08 do contêiner. A rotina real do carregador que os verifica ainda não foi localizada; o resultado da emulação do transporte abaixo permanece válido e não testa aceitação pelo dispositivo.

Análise de 05/11/2026. Fonte local: `evidence/updater120/Device Updater/DeviceUpdater.exe`, SHA256 `6c4f456e58456de73f972974a90bb57ff201343930326ddbdf29066b5ef07a28`. Todos os endereços abaixo são VAs desse PE x86 com base 0x400000; não são endereços da firmware nem se aplicam automaticamente ao atualizador 1.7.0.

Nenhum executável NI foi iniciado nesta etapa. Não houve abertura USB, chamada real DeviceIoControl, mudança de modo ou gravação de flash. Executou-se somente uma função x86 isolada em Unicorn, com interceptação obrigatória de toda chamada externa.

## Seleção e compatibilidade

O construtor em 0x412FB0 associa VID17CC/PID1110 ao objeto de modelo 0x7C06AC. O seletor em 0x42D800 percorre 14 registros de 20 bytes, a partir de 0x72C410. Compara VID/PID com campos do objeto de modelo. Para PIDs com o nibble inferior 2, normaliza para o correspondente nibble 0, com uma exceção específica de outro produto. Assim, 1112 pode usar a entrada 1110.

Entrada MK1, índice 2, em 0x72C438:

| Deslocamento na entrada | Valor | Papel |
|---|---|---|
| +0x00 | 0x7C06AC | Objeto do modelo |
| +0x04 | 55 | Versão NI disponível |
| +0x08 | 32256 / 0x7E00 | Quantidade de bytes |
| +0x0C | 0x6210B0 | Ponteiro para o payload |
| +0x10 | 0 | Flag usada pelo caminho chamador |

Precisão sobre o extrator antigo: ele começa em file offset 0x32AC34 e lê um zero anterior ao objeto do modelo, seguido pelos quatro campos úteis. O registro lógico começa quatro bytes depois, file offset 0x32AC38 / VA0x72C438, e a flag própria fica no fim. O payload e seu hash já extraídos permanecem corretos; o zero anterior não deve ser apresentado como o primeiro campo da entrada.

Em 0x42D870, o materializador chama esse seletor e a política de compatibilidade 0x42D9F0. O desvio de PID1110 ou PID1112 retorna verdadeiro em 0x42DB0B. Essa é uma política de seleção/compatibilidade, não evidência de validação de CRC do conteúdo. Em seguida, retorna ponteiro, tamanho e flag da entrada.

## Da imagem ao driver

O chamador em 0x430620 obtém esses dados em 0x43069C. Após preparar o objeto DFU e outras precondições, chama 0x436640 em 0x430740, passando ponteiro, tamanho e área para o status. Nesse trajeto visível não há recompactação ou normalização da imagem.

O método 0x436240 consulta informações DFU pelo IOCTL 0x80862400 e guarda o tamanho de transferência em objeto+0x7C. O método de envio 0x436640 divide o comprimento por esse tamanho, copia cada bloco e usa:

| Operação | Formato no host |
|---|---|
| 0x80862408 | Buffer de 516 bytes: uint16 índice, uint16 comprimento válido, área de até 512 bytes |
| 0x80862410 | Consulta de status, resposta esperada de 6 bytes |

São inteiros little endian. O tamanho de 516 pertence ao buffer entre programa e driver; não é o tamanho de cada transferência USB. O driver usa apenas o comprimento válido ao enviar a área de dados.

Após cada bloco de dados, o código exige retorno de transporte sem erro, status DFU zero e estado 5. Ao terminar, envia comprimento válido zero e consulta novamente o status; na verificação final observada exige status zero, sem a mesma comparação explícita com estado 5.

O wrapper 0x434580 encaminha a 0x434310. Este chama o import Windows `DeviceIoControl` em 0x4343C7. O driver local `mmxusb.sys` já desmontado confirma 0x80862408 → rotina 0x15290, que monta uma requisição USB classe/interface OUT, bmRequestType21, bRequest1 (DFU_DNLOAD), com índice do bloco em wValue. Isso é rastreamento estático de código; não foi enviado um download real.

## Execução emulada da função original

`firmware-research/emulate_updater_transfer.py` carrega o PE em memória emulada. Executa somente 0x436640–0x4368A5; substitui memcpy, a checagem de cookie do compilador e o wrapper de I/O. Qualquer outro destino de execução gera erro. O arquivo não importa bibliotecas USB ou APIs de dispositivo.

O tamanho 64 foi tomado de uma leitura DFU anterior da unidade, não medido novamente nesta etapa. O simulador devolve sucesso de transporte e status controlados; não modela tempo de gravação, busy/manifestation, controlador USB, flash ou bootloader.

| Cenário | Resultado observado |
|---|---|
| Payload oficial, respostas simuladas de sucesso | 504 blocos de 64 bytes, terminal índice504 com comprimento0, 505 consultas de status |
| Reconstrução dos dados dos blocos | 32256 bytes idênticos à fonte; SHA256 3cbfb13ff2e884d4eb3a3ec9546121c2e29c2fc42f6189c5d1df9dedccb88003 |
| Alteração de um byte em memória | A função isolada também encaminha todos os bytes e retorna sucesso com respostas simuladas |
| Status de erro injetado após bloco2 | Retorno falso após três blocos; nenhum bloco terminal |

O caso alterado demonstra a ausência de verificação de integridade nessa função de transporte. Não demonstra que todos os caminhos do host ou o dispositivo aceitem conteúdo modificado. Nenhuma imagem modificada foi salva como pacote instalável.

## Evidências e reprodução

- `updater-transfer/static-path.json`: campos, chamadas e asserts sobre bytes/imports do PE.
- `updater-transfer/emulation.json`: resultados dos três cenários.
- `updater-transfer/*.asm`: recortes do seletor, materializador, política, chamador, informações DFU e transferência.
- `firmware-research/audit_updater_path.py`: reconstitui a trilha estática com verificação do hash da fonte.
- `firmware-research/disassemble_updater120.py`: leitor de intervalos do PE, sem execução nativa.

O passo pendente para entender a aceitação da firmware está no lado do carregador: localizar a verificação de integridade do contêiner, explicar os campos 0x04/0x08 e estabelecer um caminho real de recuperação. A descoberta do transporte não resolve esses pontos nem autoriza inferir segurança de uma primeira gravação.
