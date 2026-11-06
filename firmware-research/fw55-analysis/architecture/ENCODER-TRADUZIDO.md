# Encoder MK1: tradução da máquina de estados

`encoder_model.py` traduz a função `0x6250–0x62A8` da FW55. Ela recebe o segundo byte da leitura serial dos botões (`0x6324–0x6328`) e extrai `(byte >> 1) & 3`: bits 1 e 2.

O modelo conserva quatro estados: última leitura (DP4), estado de liberação/armação (DP5), posição de oito bits (DP2E) e contador de retornos ambíguos (DP2D, nome descritivo inferido).

| Percurso, após armação | Resultado lógico |
|---|---|
| 3 → 1 → 0 | Posição +1, módulo 256 |
| 3 → 2 → 0 | Posição −1, módulo 256 |
| 3 → 0 | Incrementa contador ambíguo; posição preservada |
| Após contar: 0 → 1 → 0 | Não conta novamente sem passar por 3 |

O sentido físico horário/anti-horário não decorre desses números: depende da ligação dos contatos. A quantidade de transições por detente físico também exige observação externa. A leitura HID fornece a posição processada, não os dois contatos brutos.

O verificador `verify_encoder.py` interpreta as instruções do pequeno decodificador, cujos bytes são conferidos contra a FW55 fixada por SHA-256. Passaram 40.960 comparações de passo individual e 10.000 amostras em sequência, cobrindo as 33 instruções do decodificador. Inclui overflow da posição e do contador ambíguo. Resultado: `encoder-validation.json`.

É uma verificação limitada da tradução, não emulação integral do processador nem teste elétrico. Valores padrão dos contadores do modelo não comprovam toda a inicialização de boot da MK1.

Em 05/11/2026 o usuário ofereceu girar o encoder para a direita. Foi preparada captura passiva normal HID em `physical-check/encoder-right-*`, sem escritas nem mudança do serviço NI. O sentido e a relação por passo só devem ser preenchidos após a análise dos eventos e a confirmação da contagem física pelo usuário.

## Resultado físico: giro à direita e clique final

A captura `encoder-right-20261105-211604` contém 43 transições de posição observadas antes do clique final, todas +1 módulo 16, incluindo duas passagens de 15 para 0. Portanto, giro à direita corresponde ao sinal positivo na interface HID. A primeira posição recebida é apenas a referência inicial; não foi contada como transição.

O relatório HID 01 apresenta a posição no nibble baixo do byte 5 (índices incluindo o ID). O descritor confirma campos de quatro bits, máximo 15. Isso difere do acumulador interno de oito bits reconstruído no decodificador. A função `hid_position_delta` conserva essa diferença e trata corretamente 15→0 como +1.

O clique final ativou o bit 11 dos 32 bits de botões e foi solto cerca de 233 ms depois, sem mudar a posição. Isso coincide com a calibração anterior de ENCODER PUSH. Foram ignorados bytes posteriores ao sexto byte válido do relatório 01.

O usuário confirmou o término, mas não declarou quantos detentes físicos contou. Assim, a relação exata detente/incremento permanece aberta. A captura HID não valida os estados elétricos intermediários. O resultado reproduzível está em `physical-check/encoder-right-20261105-211604/analysis.json`, gerado por `analyze_encoder_capture.py`.

## Segundo ensaio: dez passos contados

Na captura `encoder-right-20261105-212019`, o usuário confirmou dez passos para a direita e um clique final. Foram recebidos dez relatórios de posição: `13, 14, 15, 0, 1, 2, 3, 4, 5, 6`, seguidos de pressionamento e soltura sem alteração da posição. As nove transições entre relatórios são todas +1 módulo 16. O clique durou aproximadamente 1,015 segundo.

O ensaio sustenta a configuração operacional **um incremento positivo por detente para a direita**. Limite: a captura não recebeu uma referência nova antes do primeiro movimento; por isso são dez relatórios de posição e nove transições diretamente mensuradas, não dez diferenças independentes. O valor final anterior conhecido era 12, coerente com o primeiro 13, mas não substitui uma referência contemporânea. Não houve saltos nas transições observadas. Resultado e contagem do usuário preservados no `analysis.json` desse ensaio.

## Terceiro ensaio: referência delimitada por dois cliques

Na captura `encoder-right-20261105-212346`, o primeiro clique confirmou posição 6 antes do giro. Após dez detentes para a direita, o segundo clique confirmou posição 0. Foram observadas exatamente dez transições: `6→7→8→9→10→11→12→13→14→15→0`, todas +1 módulo 16. Os dois cliques ocorreram sem mudança de posição.

**Calibração confirmada neste ensaio: um detente à direita produz +1 incremento HID.** Não há mais a lacuna de referência inicial dos ensaios anteriores. Isso não constitui medição da quadratura elétrica nem validação de giros rápidos ou do sentido esquerdo. O resultado completo está no `analysis.json` desse terceiro ensaio, reproduzível com `analyze_encoder_capture.py --capture encoder-right-20261105-212346 --detents 10 --two-clicks`.
