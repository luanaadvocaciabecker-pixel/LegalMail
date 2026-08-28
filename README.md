# LegalMail

Reimplementação via código da rotina diária de conciliação entre a Entrada
do Legalmail e a planilha de controle `PRAZOS BECKER 2026.xlsx` do
escritório Becker Advogados Associados.

A rotina original (`conciliacao-legalmail-prazos`) foi executada via
automação de navegador. Este repositório separa a lógica de negócio
determinística — cálculo de prazos, identificação de caso novo vs.
recorrente, escrita segura da planilha, formato do relatório — de uma
implementação real da **API pública do Legalmail** (`LegalMail Public API`,
ver `docs/legalmail-openapi.json`), para eliminar a automação de navegador
onde a API já permite.

## O que a API do Legalmail cobre (e o que não cobre)

A partir da especificação OpenAPI real fornecida pelo escritório:

- **Coberto pela API** (`legalmail_prazos.legalmail_api_client.LegalmailApiClient`):
  listar a Entrada (`GET /api/v1/notices`, com o texto completo da
  intimação, `prazo_status` e `tipo_prazo`), consultar o processo incluindo
  seu prazo ativo (`GET /api/v1/lawsuit/detail`, campo `data_prazo`),
  arquivar o processo da Entrada para o Acervo (`POST /api/v1/lawsuit/archive`),
  encarregar o advogado responsável (`POST /api/v1/lawsuit/assign`), listar
  usuários do workspace para resolver nome -> id (`GET /api/v1/users`), e
  listar os autos do processo / obter a URL de um documento específico
  (`GET /api/v1/lawsuit/case-files` e `GET /api/v1/lawsuit/docket-entry/url`)
  para montar o contexto de um esboço de manifestação sem depender do merge
  completo dos autos (limitado a 1x a cada 3 dias pela própria API).
- **Não coberto pela API** (continua manual, na interface do Legalmail):
  criar uma tarefa com Tipo/Descrição/Prazo (não existe endpoint para isso,
  nem para definir `data_prazo` diretamente — é somente leitura, gerido pela
  própria plataforma). `LegalmailApiClient` levanta
  `RecursoNaoSuportadoPelaApiError` nesse método, com a explicação.
- **Audiências não têm endpoint próprio, mas dá para contornar**: como a
  API não expõe uma listagem de audiências, `legalmail_prazos.classificacao`
  identifica intimações de audiência dentro da própria Entrada (pelo campo
  `tipo`, estruturado) e extrai data/horário do teor quando possível
  (`rotina.triar_entrada` + `rotina.escrever_audiencias_da_entrada`).
  Extração de texto livre é best-effort — quando não é confiável, o campo
  fica em branco na planilha e a limitação é reportada.

A API é **paga por crédito do workspace** — `GET /api/v1/notices` custa
R$ 0,05 por requisição (2xx), independente de quantas intimações vierem na
página. Por isso `listar_entrada` só deve ser chamado uma vez por execução
diária, nunca em laço (ver docstring de `legalmail_prazos.api_v1`).

## Configuração

Copie `.env.example` para `.env` e preencha `LEGALMAIL_API_KEY` com o valor
real do token (Painel do Legalmail -> Configurações -> Painel da API ->
Tokens de acesso). **Nunca** cole esse valor em código, commits ou em uma
conversa com um assistente — ele vale créditos reais do workspace.
`legalmail_prazos.legalmail_api_client.cliente_a_partir_do_ambiente()` monta
o cliente real a partir dessa variável de ambiente.

## Documentação

- `docs/CONFIGURACOES_ROTINA_CONCILIACAO_LEGALMAIL_PRAZOS.md`: especificação
  técnica completa e fonte de verdade das regras de negócio da rotina.
- `docs/legalmail-openapi.json`: especificação OpenAPI real da API do
  Legalmail, fornecida pelo escritório.
- `docs/CALENDARIOS_FORENSES.md`: fontes e processo de atualização anual
  dos calendários forenses por tribunal (TJSC, TRT12).
- `.claude/skills/conciliacao-legalmail-prazos/SKILL.md`: resumo operacional
  do skill, referenciando o código deste repositório.

## Estrutura do código

```
src/legalmail_prazos/
  holidays.py             calendário de dias não úteis (feriados nacionais, recesso forense)
  tribunais.py            feriados forenses e suspensões de prazo específicas por tribunal (TJSC, TRT12)
  prazos.py               motor de cálculo de prazos (CPC, CLT, Juizados Especiais)
  planilha.py             leitura/escrita segura da planilha PRAZOS BECKER
  legalmail_client.py     contrato de acesso ao Legalmail (Protocol)
  api_v1.py               cliente HTTP fino para a API pública real do Legalmail
  legalmail_api_client.py implementação do Protocol sobre a API real (api_v1)
  classificacao.py        classifica intimações (audiência/perícia/prazo) e extrai data/horário do teor
  rotina.py               orquestração das partes 1 (casos novos) e 2 (audiências) e relatório final
  cli.py                  utilitários de linha de comando para conferência manual
```

Nenhum dado real de cliente do escritório está neste repositório; os testes
usam apenas planilhas, processos e respostas de API sintéticos (nenhum
teste faz uma chamada de rede real nem consome créditos da API).

## O que ainda depende de decisão humana

- A leitura e interpretação jurídica do teor de cada intimação (qual é o
  ato exato, quantos dias tem o prazo) continua sendo uma decisão humana ou
  de um agente com acesso ao texto da intimação; o código apenas calcula as
  datas a partir dos parâmetros já decididos (`legalmail_prazos.prazos`).
- Criar a tarefa (Tipo/Descrição/Prazo), por não existir endpoint na API —
  ver seção acima. Mesmo sem "tarefa", a rotina encaminha ao responsável de
  verdade via `POST /api/v1/lawsuit/assign`
  (`rotina.processar_parte1` chama isso automaticamente, resolvendo o nome
  do advogado para o id de usuário do Legalmail).
- Feriados estaduais/municipais específicos de cada tribunal/comarca.
  `legalmail_prazos.tribunais.calendario_para_tribunal(tribunal, anos)` já
  cobre TJSC e TRT12 para 2026 (~85% dos processos do escritório, com fonte
  citada no código — Resolução GP TJSC n. 1/2026 e Portaria Calendário TRT12
  2026), incluindo a suspensão de prazo de 20/dez a 20/jan (mais longa que o
  recesso genérico do CPC). Para qualquer outro tribunal, ou para anos
  diferentes de 2026, a função retorna `confirmado=False` — sinal para
  conferir manualmente antes de confiar no cálculo, em vez de assumir que
  não há feriado nenhum. Ver `docs/CALENDARIOS_FORENSES.md` para o processo
  de atualização anual.

## Rodando os testes

```
pip install -e ".[dev]"
pytest
```
