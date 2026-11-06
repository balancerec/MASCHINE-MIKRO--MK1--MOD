# Prompt para continuar o projeto

Copie o bloco abaixo para uma nova sessão trabalhando neste repositório.

```text
Você está desenvolvendo o projeto MASCHINE-MIKRO--MK1--MOD com o proprietário
da unidade de referência. Leia primeiro AGENTS.md, README.md, PLANO.md e
docs/ESTADO-ATUAL.md; confira git status e o histórico antes de editar.

Objetivo: implementar drivers e processamento musical próprios para a
MASCHINE MIKRO MK1, preservando o editor local e o fluxo musical do FL Studio.
Alvo normal 17CC:1110; DFU observado 17CC:1112. Não usar definições de MK2/MK3
ou da MASCHINE grande como se fossem da MIKRO MK1.

Estamos na fase de reconstrução e implementação offline. A unidade está
fechada; não há programador externo, backup integral da flash nem recuperação
comprovada. A firmware oficial FW55 de atualização foi analisada localmente,
mas não está neste repositório e não equivale a um dump da unidade.
Não gravar, apagar, entrar em DFU nem alterar drivers por iniciativa própria.

Já existem: editor HID local, script FL para 16 pads musicais e botões de
função, mapas físicos, modelo de encoder e modelo de PWM dos LEDs. O encoder
foi medido com dois cliques delimitando dez detentes: direita = +1 por detente,
posição HID de quatro bits, clique no bit 11 de botões. Não confundir esse
campo com o acumulador interno de oito bits. A esquerda foi testada no modelo,
não fisicamente. Os quatro cantos (1,4,13,16) deram seis respostas isoladas cada,
sem saturação nem atividade vizinha acima do limiar diagnóstico de 100.
Não tratar esse limiar como configuração musical calibrada ou equiparar
picos manuais diferentes a diferenças de sensibilidade.

O núcleo C99 já existe em core/: encoder, PWM, parser de amostras e detector
experimental próprio de ataque/pico/soltura, com eventos NOTE_ON/OFF em memória.
Leia core/README.md e core/PAD-DETECTOR.md e execute os testes de host antes de
modificar. O replay local dos quatro cantos gerou 24 pares corretos, mas isso
não calibra limiares, latência ou curva dos 16 pads. O adaptador C de fluxo já
existe: leia core/PAD-STREAM.md; ordem, gaps, geração, watchdog e reconexão são
testados offline. A fila/codificação MIDI também existe: leia core/MIDI-OUTPUT.md.
Ela usa callback síncrono ainda simulado, com RETRY e entrega incerta; não há
ACK do sintetizador. O backend WinMM e coordenador síncrono agora existem em
host/: leia host/README.md. loopMIDI foi instalado, o usuário criou MIKRO MOD FL
e confirmou sua entrada habilitada no FL. A porta passou em abertura/fechamento
real sem mensagens de nota. Ainda não houve teste musical ao vivo.
O leitor HID e a supervisão agora existem: leia host/SUPERVISION.md. O runner
tools/run_host.py usa memória por padrão, processos separados e limites de buffer,
idade e duração. A leitura real sem saída passou; o modo live ainda não foi
ensaiado musicalmente. A próxima entrega é um teste curto combinado com o operador:
evitar entrada NI duplicada no FL, selecionar instrumento e confirmar contagem.
Preservar endpoint, sessões e limpeza; não abrir destino arbitrário ou tratar
sucesso da API como ACK físico. Pressão contínua e calibração completa seguem pendentes.
Preserve o caminho NI/FL já funcional e não emita notas de teste para um projeto
aberto sem alinhar o ensaio com o operador. Não aplicar ganhos inferidos de força
manual nem afirmar que o build de host compila para XMOS ou é gravável.
Mantenha portas/tiles separados e a pesquisa do toolchain XS1 como item distinto.

Use somente evidência existente ou documentação primária para fatos de hardware.
Classifique achados como observados, reconstruídos ou hipóteses. Verificadores
diferenciais dependem de materiais locais opcionais; testes padrão/CI não podem
depender deles ou acessar o hardware. Se faltarem arquivos, informe exatamente
quais e continue o trabalho independente deles; não invente resultados.

Não redistribua instaladores, executáveis, firmware NI, desmontagens completas,
originais de presets, capturas brutas ou dados pessoais. Respeite o manifesto
de publicação. Preserve originais e o funcionamento local; não use git add .
sem revisar o que entrará. Uma licença de terceiros não é uma licença do projeto.

Comunique-se em português, com atualizações objetivas. Trabalhe até concluir
a entrega autorizada. Ao terminar, diga o que mudou, como foi testado, o que
permanece incerto e qual é o próximo item concreto do plano. Não afirme que
há firmware própria pronta enquanto não houver build e validação no alvo.
```
