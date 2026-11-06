# MASCHINE MIKRO MK1 MOD

Pesquisa independente, editor de controles e preparação de uma implementação própria para a **Native Instruments MASCHINE MIKRO MK1**. Alvo normal USB `17CC:1110`; modo DFU observado `17CC:1112`. Não confundir com a MASCHINE grande ou com a MIKRO MK2/MK3.

**Estado em 05/11/2026:** editor local e integração FL Studio funcionais na unidade de referência; rotinas de encoder e PWM dos LEDs traduzidas em modelos offline. **Ainda não existe uma firmware própria compilada e validada para gravação.** A imagem oficial de atualização não é um backup completo da unidade.

## Comece aqui

- [Plano completo e critérios de conclusão](PLANO.md)
- [Prompt para continuar o projeto](PROMPT-CONTINUIDADE.md)
- [Estado atual, evidências e lacunas](docs/ESTADO-ATUAL.md)
- [Arquitetura pretendida](docs/ARQUITETURA-PROPOSTA.md)
- [Materiais locais e fontes](docs/MATERIAIS-E-FONTES.md)
- [Regras para alterações neste repositório](AGENTS.md)

## Executar o editor no Windows

Requer Python 3.10+ e o driver NI apropriado instalado separadamente. O driver é necessário para a comunicação física; a interface pode ser aberta sem equipamento.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe build_editor.py
.\.venv\Scripts\python.exe mikro_bridge.py
```

Abra `http://127.0.0.1:8765/`. A ponte escuta somente no loopback. Ela inicia desconectada; **Conectar USB** pode pausar NIHardwareService para assumir HID, e **Devolver à NI** restaura o serviço. Esse modo não equivale a roteamento MIDI ao FL. O perfil MIDI do FL usa o serviço NI e a configuração correspondente no Controller Editor.

O build público contém o editor básico e o mapa físico de referência. Presets NI originais, templates XML completos, instaladores e firmware não acompanham o repositório. Os importadores podem trabalhar com arquivos obtidos localmente; `integrar_presets.py` é uma ferramenta específica do ambiente original, não um requisito para abrir o editor. Builds locais existentes com presets são preservados por `build_editor.py`.

## Verificação sem hardware

```powershell
python test_16_pads.py
python test_display.py
node test_encoder.cjs
```

`test_display.py` usa um dispositivo falso; não escreve no equipamento. Os modelos `firmware-research/encoder_model.py` e `led_pwm_model.py` não acessam USB. Os verificadores diferenciais dependem de arquivos locais da firmware oficial e de sua desmontagem, ausentes no pacote público; veja [materiais](docs/MATERIAIS-E-FONTES.md).

Teste opcional de interface: instale dependências com `npm install`, instale Edge ou o navegador adequado ao teste, inicie a ponte e execute `npm run test:browser`. O teste usa replay isolado e não envia comandos ao dispositivo. `test_bridge.py` verifica os limites HTTP de uma ponte já em execução.

## Organização

| Pasta/arquivo | Responsabilidade |
|---|---|
| `control-studio/src/` | Fonte do editor e mapa de referência sem identidade da unidade |
| `control-studio/dist/` | Interface estática; `app.js` e calibração local são gerados |
| `mikro_bridge.py` | Ponte HID/HTTP local existente |
| `fl-integration/` | Script de integração com as APIs do FL Studio |
| `firmware-research/` | Modelos, verificadores, análises e documentação da reconstrução |
| `tests/fixtures/` | Amostras mínimas de entrada para testes sem hardware |

Não há gravação automática de firmware, execução de capturas físicas na CI nem cópia de firmware proprietária neste pacote. A seleção pública está registrada em `publication-manifest.json`. Documentos de pesquisa registram etapas históricas; para decisões atuais, prevalecem `PLANO.md` e `docs/ESTADO-ATUAL.md`.

Projeto independente, sem afiliação à Native Instruments ou à Image-Line. Nomes de produtos pertencem aos respectivos titulares. Nenhuma licença geral foi atribuída nesta publicação inicial; permissões de redistribuição de materiais externos não devem ser presumidas.
