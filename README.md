# LegalMail

Reimplementação via código da rotina diária de conciliação entre a Entrada
do Legalmail (https://app.legalmail.com.br) e a planilha de controle
`PRAZOS BECKER 2026.xlsx` do escritório Becker Advogados Associados.

A rotina original (`conciliacao-legalmail-prazos`) foi executada via
automação de navegador. Este repositório separa a lógica de negócio
determinística — cálculo de prazos, identificação de caso novo vs.
recorrente, escrita segura da planilha, formato do relatório — de qualquer
camada de acesso ao Legalmail, para permitir uma reimplementação via
código/API em vez de automação de UI.

## Documentação

- `docs/CONFIGURACOES_ROTINA_CONCILIACAO_LEGALMAIL_PRAZOS.md`: especificação
  técnica completa e fonte de verdade de todas as regras da rotina.
- `.claude/skills/conciliacao-legalmail-prazos/SKILL.md`: resumo operacional
  do skill, referenciando o código deste repositório.

## Estrutura do código

```
src/legalmail_prazos/
  holidays.py          calendário de dias não úteis (feriados nacionais, recesso forense)
  prazos.py            motor de cálculo de prazos (CPC, CLT, Juizados Especiais)
  planilha.py           leitura/escrita segura da planilha PRAZOS BECKER
  legalmail_client.py   contrato de acesso ao Legalmail (Protocol, sem implementação de API real)
  rotina.py             orquestração das partes 1 (casos novos) e 2 (audiências) e relatório final
  cli.py                utilitários de linha de comando para conferência manual
```

Nenhum dado real de cliente do escritório está neste repositório; os testes
usam apenas planilhas e processos sintéticos.

## O que ainda depende de implementação específica do escritório

- Um backend real para `legalmail_prazos.legalmail_client.LegalmailClient`
  (API do Legalmail, se/quando exposta, ou outro mecanismo de integração).
  Não há confirmação de API pública documentada do Legalmail.
- A leitura e interpretação jurídica do teor de cada intimação (qual é o
  ato exato, quantos dias tem o prazo) continua sendo uma decisão humana ou
  de um agente com acesso ao texto da intimação; o código apenas calcula as
  datas a partir dos parâmetros já decididos (`legalmail_prazos.prazos`).
- Feriados estaduais/municipais específicos de cada tribunal/comarca, que
  devem ser informados via `Calendario(feriados_extra=...)` — só feriados
  nacionais e o recesso forense do art. 220 do CPC vêm prontos.

## Rodando os testes

```
pip install -e ".[dev]"
pytest
```
