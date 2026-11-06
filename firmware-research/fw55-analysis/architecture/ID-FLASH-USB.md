# Consulta de identificação no host: descoberta e limite na MK1

Análise offline de 05/11/2026. Nenhum dispositivo foi aberto, nenhum comando novo foi enviado e nenhuma firmware foi gravada.

## Consulta encontrada

No atualizador 1.2.0, após montar um registro de enumeração, o código em 0x42E174–0x42E20B constrói duas requisições vendor/device IN. A montagem foi executada em Unicorn com a chamada externa 0x434640 interceptada, sem executar o programa Windows nativamente:

| Campo | Primeira consulta | Segunda consulta |
|---|---|---|
| bmRequestType | C0 | C0 |
| bRequest | B3 | B3 |
| wValue | 0 | 0 |
| wIndex | 2 | 1 |
| wLength | 1 | 4 |
| Setup completo | C0 B3 00 00 02 00 01 00 | C0 B3 00 00 01 00 04 00 |
| Destino no registro do host | +0x6A | +0x6C |

O segundo destino é o mesmo campo consumido pelo materializador e pela política de compatibilidade, em que o host compara valores como 0x1F430000 e 0x1F440100 em certos modelos. Isso sustenta a interpretação de identificação da flash nesse campo. A interpretação exata da primeira resposta permanece sem confirmação.

A rotina é parte da enumeração compartilhada do atualizador. Sua existência não prova que todos os produtos NI implementem o comando; a MK1 tem um ramo próprio na política de compatibilidade que não exige essas comparações de ID. A análise ainda não localizou o handler correspondente a B3 na FW55.

## Auditoria das capturas

`audit_vendor_b3.py` leu as 12 capturas PCAP existentes em `firmware-research` e `controller-editor-research`. Foram examinados 2098070 pacotes. Entre os estágios de setup USB control reconhecidos pelo parser USBPcap, não houve uma requisição com os bytes iniciais C0 B3.

Não foi detectada uma resposta anterior bem-sucedida que permitisse confirmar esse método na unidade. A captura não cobre toda a vida do equipamento; ausência nessas janelas não prova inexistência do comando.

`vendor-query/audit.json` preserva o inventário por arquivo, contagens e os dois setups recuperados. `host-request-builder.asm` contém o recorte do executável fixado por hash.

## O que pode ser afirmado agora

- O perfil compilado da FW55 espera ID1F4300 e uma flash compatível com AT25DF021 de 256 KiB; esses dados continuam sendo inferência estática.
- Existe no host uma consulta IN com campo de resposta destinado à identificação usada pela política de compatibilidade.
- Não foi demonstrado que a MK1 responda a essa consulta nem que seu handler seja exclusivamente de leitura. A direção IN sozinha não estabelece a semântica interna de um comando vendor.
- Nenhuma consulta B3 foi executada no hardware e a lista de operações permitidas do coletor DFU permaneceu inalterada.
- Continua sem existir um método validado de leitura arbitrária da flash ou backup integral do primeiro estágio pelo USB disponível.

O próximo avanço verificável exige encontrar o handler da consulta na imagem/código do driver, registrar uma consulta legítima do software NI na MK1, ou confirmar a memória por acesso físico de leitura. Repetir o upload DFU que já retornou zero bytes não substitui essa evidência. O backup do carregador e a recuperação após falha ainda não estão comprovados.
