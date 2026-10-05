# Workflow do n8n — Conciliação Legalmail x PRAZOS BECKER

`conciliacao-legalmail-prazos.workflow.json` é um workflow do n8n que porta
a Parte 1 da rotina (já implementada e testada em Python neste repositório)
para rodar de forma agendada, sem depender de uma sessão de chat para
executar: ler a Entrada do Legalmail, classificar cada intimação, calcular
o prazo com o calendário do tribunal, conciliar com a aba PRAZOS (caso novo
vs. recorrente), resolver o advogado responsável, pedir aprovação humana e
só então encarregar + arquivar.

**Isto não foi testado contra uma instância real de n8n** (este ambiente não
tem n8n rodando). A lógica determinística (cálculo de prazo e calendário
forense) foi portada de Python para JavaScript e **validada rodando os dois
lado a lado** com os mesmos casos de teste — ver seção "Validação" abaixo.
O que não dá para garantir sem importar de verdade é a sintaxe exata de
cada nó (nomes de campo, `typeVersion`) para a versão de n8n que vocês
usam — pode ser preciso ajustar node a node depois de importar.

## Antes de importar

1. **Planilha PRAZOS BECKER em Google Sheets**, não mais em .xlsx — os nós
   de Google Sheets (`Ler PRAZOS`, `Ler ATIVOS ATUAL`, `Adicionar linha em
   PRAZOS`) esperam isso. Se a planilha real ainda estiver em OneDrive/Excel,
   seria preciso trocar esses três nós por nós de Microsoft Excel/SharePoint
   equivalentes (existem nós nativos no n8n para isso).
2. **Credenciais a criar no n8n** (os nós do workflow só referenciam o nome,
   vocês criam o valor real):
   - `Legalmail API Key` — tipo "Query Auth" (genérica), nome do parâmetro
     `api_key`, valor a chave real do Painel da API do Legalmail.
   - `Anthropic API Key` — tipo "Header Auth" (genérica), nome do cabeçalho
     `x-api-key`, valor a chave da API da Anthropic.
   - `Google Sheets - Becker` — credencial OAuth2 do Google Sheets.
   - `Slack - Becker` — credencial de app do Slack (com permissão de enviar
     mensagem e usar "aprovação" em um canal).
3. **Substituir os placeholders**: `SUBSTITUA_PELO_ID_DA_PLANILHA` (ID da
   planilha do Google Sheets, nos três nós de Google Sheets) e os nomes de
   canal do Slack (`#legalmail-aprovacoes`, `#legalmail-relatorios`).

## O que o workflow cobre (e o que não cobre)

Mesmas regras e as mesmas limitações já documentadas no pacote Python
(`docs/CALENDARIOS_FORENSES.md`, `legalmail_api_client.py`):

- **Cobre**: casos novos vs. recorrentes, cálculo de prazo (CPC/CLT/Juizados),
  calendário forense específico de TJSC e TRT12 para 2026 (qualquer outro
  tribunal/ano fica com `calendario_confirmado: false`, avisando no Slack),
  escrita da aba PRAZOS, encarregar o advogado responsável (`POST
  /lawsuit/assign`), arquivar para o Acervo (`POST /lawsuit/archive`).
- **Não cobre nesta versão**: a Parte 2 (audiência/perícia) só é separada
  (nó "TODO Parte 2") mas não escreve nada ainda — é o próximo passo, usando
  a mesma lógica de `classificacao.py` já portada para dentro deste
  workflow. "Criar tarefa" continua não existindo na API do Legalmail —
  "encarregar o responsável" é o equivalente real mais próximo.
- **O passo de IA** (`IA - interpretar intimação`) decide quantidade de dias
  e regime a partir do teor da intimação — isso é a parte que exige leitura
  jurídica do texto, e por isso vem seguida de um nó de aprovação humana no
  Slack antes de qualquer ação que grave algo real (encarregar/arquivar).
  Nunca remova esse nó de aprovação sem ter outra camada de revisão humana
  no lugar.

## Validação feita (sem n8n real)

A função JavaScript do nó "Calcular prazo (feriados-tribunal)" foi extraída
e executada em Node.js com os mesmos parâmetros usados nos testes do
pacote Python (`tests/test_tribunais.py`, `tests/test_cli.py`), comparando
a saída da CLI Python (`conciliacao-legalmail-prazos calcular-prazo`) com a
função JS lado a lado. Casos conferidos, todos batendo exatamente:

- TJSC, cruzando a suspensão de virada de ano (20/dez a 20/jan).
- TJSC, caso simples sem feriado específico no meio.
- TJSC, cruzando o feriado de Divino Espírito Santo (25/05/2026).
- TRT12, regime trabalhista.
- STJ (tribunal não pesquisado), confirma `calendario_confirmado: false`.
- Juizado Especial, dias corridos.

Isso garante que a matemática de prazos está certa; não garante que o
JSON do workflow importa sem ajuste em qualquer versão de n8n.
