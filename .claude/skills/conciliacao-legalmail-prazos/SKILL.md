---
name: conciliacao-legalmail-prazos
description: Concilia diariamente a Entrada do Legalmail com a planilha PRAZOS BECKER 2026.xlsx (casos novos, audiências, perícias) e reporta o resultado.
---

# Conciliação Legalmail x PRAZOS BECKER

Rotina diária do escritório Becker Advogados Associados para conciliar a
Entrada do Legalmail (https://app.legalmail.com.br) com a planilha de
controle `PRAZOS BECKER 2026.xlsx`, em duas partes.

A especificação completa e a fonte de verdade desta rotina estão em
`docs/CONFIGURACOES_ROTINA_CONCILIACAO_LEGALMAIL_PRAZOS.md`. Este SKILL.md é
o resumo operacional para quem for executar a rotina; qualquer divergência
entre os dois documentos deve ser resolvida a favor do documento de
referência em `docs/`.

A parte mecânica e verificável desta rotina (cálculo de prazos, novo vs.
recorrente, escrita segura da planilha, formato do relatório) está
implementada em código no pacote `legalmail_prazos` (`src/legalmail_prazos`),
para não depender de automação de navegador. Use-o em vez de reescrever essa
lógica manualmente. A leitura e interpretação jurídica de cada intimação
(qual é o ato exato, quantos dias tem o prazo) continua sendo feita por
quem executa a rotina (pessoa ou agente com acesso ao teor da intimação),
que então chama `legalmail_prazos.prazos.calcular_prazo` (ou
`Prazo.a_partir_de_tribunal` quando o eProc/PJe já informa as datas) para
obter as datas corretas.

## Parte 1 — Casos novos na Entrada

Para cada item da Entrada:

1. Verificar se o conteúdo está realmente acessível (segredo de justiça não
   significa necessariamente conteúdo bloqueado). Se estiver genuinamente
   bloqueado, parar esse item e reportar a limitação, nunca inventar dados.
2. Normalizar o número do processo (`legalmail_prazos.planilha.normalizar_processo`)
   e checar em `prazos_nums.json` e na coluna B da aba PRAZOS
   (`eh_caso_novo`) se é caso novo ou recorrente.
3. Caso novo: adicionar linha ao final da aba PRAZOS
   (`adicionar_linha_prazos`), com tribunal, processo, cliente x parte
   contrária, fórmula da coluna INTERNO, advogado (cruzado com a coluna K
   `ADVOGADA ATUAL` da aba ATIVOS ATUAL via `localizar_advogado_por_processo`),
   status PENDENTE e observação de Segredo de Justiça quando aplicável.
   Colunas PRAZO 1 e PRAZO 2 ficam em branco para preenchimento manual.
4. Se houver perícia designada, adicionar entrada na aba PERÍCIA
   (`adicionar_linha_pericia`) — vale tanto para casos novos quanto
   recorrentes. `rotina.sugerir_pericia(item)` detecta a menção a perícia
   no teor e tenta extrair data/horário automaticamente (retorna `None`
   quando o teor não menciona perícia); campos não extraídos com confiança
   ficam em branco na planilha, nunca inventados.
5. Antes de criar a tarefa no Legalmail, abrir o histórico do processo e
   tentar reaproveitar um Tipo já usado (`escolher_tipo_tarefa`). Nunca
   criar um Tipo novo sem necessidade real; se não houver correspondência
   razoável, sinalizar para confirmação manual em vez de adivinhar.
6. Calcular o prazo (seção 5 do documento de referência): identificar o
   prazo específico do ato exato da intimação, considerar hipótese de
   embargos, aplicar a regra de disponibilização eletrônica (D+1 útil como
   marco inicial), preferir as datas do próprio eProc/PJe quando
   informadas, e aplicar a margem de segurança interna de 2 dias úteis
   (exceto em janelas puramente administrativas de ciência).
7. Criar a tarefa no Legalmail com Tipo, Encarregado (advogado responsável),
   Descrição (sem dois-pontos) e Prazo, quando o backend suportar
   (`client.criar_tarefa`). Quando não suportar (é o caso da API pública
   hoje, que não tem esse conceito), `rotina.processar_parte1` não trava
   nisso, registra a limitação e segue em frente.
7.1. Encaminhar ao responsável de qualquer forma: resolver o nome do
   advogado para o id de usuário do Legalmail (`client.localizar_usuario_por_nome`)
   e encarregá-lo diretamente no processo (`client.encarregar_advogado`,
   que na API real chama `POST /api/v1/lawsuit/assign`). Isso funciona
   mesmo quando "criar tarefa" não é suportado — é o mecanismo real de
   roteamento ao responsável.
8. Arquivar o processo da Entrada para o Acervo.

Gravação da planilha sempre via `fazer_backup` + `salvar_com_seguranca`
(arquivo temporário no mesmo diretório + `os.replace` atômico) e conferência
posterior reabrindo o arquivo do disco (`conferir_celula`).

## Parte 2 — Audiências futuras

A API do Legalmail não tem endpoint de audiências (ver seção "Camada de
acesso ao Legalmail" abaixo). Por isso a única forma de identificá-las via
API é classificar as próprias intimações da Entrada:

1. Separar a Entrada com `rotina.triar_entrada(itens)`, que usa
   `classificacao.eh_intimacao_de_audiencia` (prioriza o campo `tipo`
   estruturado da intimação; só cai para busca no `teor` quando `tipo` não
   vier preenchido).
2. Para cada intimação de audiência, `rotina.escrever_audiencias_da_entrada`
   compara o processo normalizado com a coluna B da aba AUDIÊNCIA
   (`processos_na_aba_audiencia`) para não duplicar, e extrai data/horário
   do teor best-effort (`classificacao.extrair_data_e_horario`) — quando a
   extração não é confiável, a célula fica em branco e a limitação é
   sinalizada no relatório, nunca uma data inventada.
3. Adiciona linha nova (`adicionar_linha_audiencia`), com cliente em
   maiúsculas, evento sugerido por palavra-chave (instrução/conciliação),
   área (TRABALHISTA para TRT/TST, CÍVEL para os demais). LINK, CONTATO DO
   CLIENTE, CIENTE, AGENDADO(A), CONFIRMAÇÃO, TESTEMUNHAS e OBSERVAÇÕES
   ficam em branco; AGENDADO(A) nunca é marcado automaticamente.
4. Se o próprio Legalmail vier a expor um endpoint de audiências no
   futuro, `rotina.processar_parte2` já está pronto para consumi-lo
   diretamente (ver `legalmail_client.AudienciaLegalmail`).

## Relatório final

Montar o relatório com `RelatorioConciliacao.texto()`: parágrafos corridos,
sem dois-pontos, sem bullets ou tabelas, informando quantos casos novos
foram cadastrados/arquivados (com cliente e número de processo de cada um),
quantas audiências/perícias foram adicionadas, quais tipos de tarefa ficaram
pendentes de confirmação manual, e qualquer limitação que tenha impedido o
processamento de algum item.

## Camada de acesso ao Legalmail

O Legalmail tem uma API pública real e paga por crédito
(`docs/legalmail-openapi.json`). `legalmail_prazos.legalmail_api_client.LegalmailApiClient`
implementa o contrato `LegalmailClient` sobre ela:

- Suportado pela API: listar a Entrada (`GET /api/v1/notices`, com o teor
  completo da intimação), consultar o processo e seu prazo ativo
  (`GET /api/v1/lawsuit/detail`, campo `data_prazo`, somente leitura),
  arquivar para o Acervo (`POST /api/v1/lawsuit/archive`), encarregar o
  advogado responsável (`POST /api/v1/lawsuit/assign`) e listar usuários do
  workspace (`GET /api/v1/users`).
- Não suportado pela API, continua manual na interface: criar uma tarefa
  com Tipo/Descrição/Prazo (não há endpoint para isso nem para escrever
  `data_prazo` diretamente) e qualquer coisa de audiências (não existe
  endpoint de audiências). `LegalmailApiClient` levanta
  `RecursoNaoSuportadoPelaApiError` nesses métodos, explicando a limitação
  em vez de simular um comportamento que a API não tem.

`GET /api/v1/notices` é cobrado por requisição (R$ 0,05, só em 2xx) —
`listar_entrada` deve ser chamado uma vez por execução diária, nunca em
laço. A chave de API fica em `LEGALMAIL_API_KEY` (variável de ambiente, ver
`.env.example`), nunca em código ou em texto de conversa.
