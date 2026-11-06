# Editor conectado à MASCHINE MIKRO MK1

## Usar

1. Execute `Iniciar-MIKRO.ps1` no Windows (clique com o botão direito, Executar com PowerShell).
2. Abra http://127.0.0.1:8765/ no computador conectado à MK1.
3. Feche o Controller Editor e outros aplicativos NI que estejam usando o equipamento.
4. Clique em **Conectar USB**. Se o serviço NI estiver ativo, a ponte pede elevação do Windows para pausá-lo.
5. Use **Acender todos**, **Apagar todos**, **Enviar LEDs** ou **Testar selecionado**. Marque **Enviar ao editar** para enviar mudanças automaticamente.
6. Ao terminar, clique **Devolver à NI**. A ponte apaga os LEDs, fecha o HID e reinicia o NIHardwareService. Reabra Controller Editor para voltar ao fluxo oficial.

O endereço publicado continua sendo o editor hospedado. Seu botão **Abrir conexão local** abre a versão servida no próprio computador, com o mesmo desenho e acesso ao USB. A ponte não fica exposta à rede e não é instalada como serviço de inicialização automática.

## Resultado físico verificado em 04/11/2026

- A escrita HID só teve efeito físico depois de pausar NIHardwareService.
- Acender/apagar todos os LEDs: confirmado pelo usuário.
- Comando de pulso enviado pela página ao pad 16: confirmado pelo usuário.
- A foto enviada confirmou o pad 12 aceso durante a calibração.
- Report de saída real da unidade: **0x80**, **60 valores**, intensidade **0–31**, extraído do descritor HID. No Windows HIDAPI retorna 265 bytes escritos por causa do tamanho máximo de report de saída do dispositivo.
- Mapa confirmado (índices no payload, sem contar o report ID): RESTART = 0; pad 16 = 28; pad 12 = 44.
- O descritor comunitário anterior (48 bytes, prefixo 0) não corresponde ao descritor desta unidade. Ele permanece nos arquivos como referência, não é usado pela ponte.

## Calibrar outros controles

1. Clique **Calibrar LEDs**.
2. Escolha um endereço de 0 a 59 e clique **Acender este endereço**.
3. Observe qual LED acendeu no aparelho e clique no controle correspondente no desenho.
4. Clique **Associar ao selecionado**. Use **Próximo** para avançar.
5. Feche o painel ou clique **Enviar LEDs** para sair do teste.

As associações ficam neste navegador. **Exportar mapa** salva uma cópia JSON. Os controles sem endereço confirmado continuam editáveis no template, mas não recebem comandos individuais no hardware. O pulso é gerado pela ponte; não é gravado no firmware.

## Escopo atual

Funcionam a conexão HID, os LEDs globais e os LEDs individuais calibrados, com intensidade e pulso. Não há gravação de firmware, alteração de driver, acesso arbitrário a USB ou escrita de display. Nota/CC, canal e velocity continuam como configuração do template: a ponte ainda não implementa roteamento MIDI.

A leitura HID recebeu 390 mudanças reais do fluxo 0x20 enquanto o usuário tocava, com valores variáveis nos dados de pressão. Evidência em `docs/bridge-eventos-confirmados.json`. O monitor mostra report e bytes alterados. A associação semântica entre canais do fluxo e todos os pads/botões ainda precisa ser calibrada; isso não constitui roteamento MIDI. O monitor diferencia comandos de prévia e relatórios USB reais.

O ciclo **Devolver à NI** foi verificado: conexão HID fechada e NIHardwareService novamente em execução. Depois a ponte foi reconectada para uso no editor.

## Arquivos e verificação

- `mikro_bridge.py`: servidor e acesso HID; depende do hidapi 0.15.0 já instalado em `.deps/`.
- `control-studio/dist/hardware.js`: cliente e calibração.
- `Iniciar-MIKRO.ps1`: inicialização da ponte e abertura da página.
- `python test_bridge.py`: 6 testes de validação HTTP, origens, token e limites dos comandos, com a ponte conectada.
- `node --check control-studio/dist/app.js` e `node --check control-studio/dist/hardware.js`: sintaxe validada.

O servidor aceita apenas o Host e a origem `http://127.0.0.1:8765`, usa token de sessão para comandos e só expõe os arquivos do editor. Os únicos comandos HID de saída implementados são reports de LEDs com ID 0x80 e valores limitados a 0–31. Não existe endpoint para enviar bytes USB arbitrários.
