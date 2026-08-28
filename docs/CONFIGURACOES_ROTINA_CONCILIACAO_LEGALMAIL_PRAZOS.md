# Configurações da rotina "conciliacao-legalmail-prazos"

Documento de referência técnica com todas as regras, critérios e padrões usados na execução desta rotina, para uso por outro agente (ex. Codex) que vá reimplementar o mesmo fluxo, preferencialmente via código/API em vez de automação de navegador.

## 1. Objetivo

Conciliar diariamente a Entrada do Legalmail (https://app.legalmail.com.br) com a planilha de controle `PRAZOS BECKER 2026.xlsx` do escritório Becker Advogados Associados, em duas partes:

- Parte 1: casos novos na Entrada (criar linha na aba PRAZOS quando o caso for realmente novo, criar tarefa no Legalmail com prazo calculado, preencher aba PERICIA quando houver perícia designada, arquivar o processo da Entrada para o Acervo).
- Parte 2: audiências futuras não cadastradas na aba AUDIÊNCIA da mesma planilha.

Arquivo de regras original (fonte única de verdade): SKILL.md fornecido pelo usuário, com o front-matter:

```
name: conciliacao-legalmail-prazos
description: Concilia diariamente a Entrada do Legalmail com a planilha PRAZOS BECKER 2026.xlsx (casos novos, audiências, perícias) e reporta o resultado.
```

## 2. Arquivos envolvidos

- Planilha alvo (real, não confundir com cópias/nomes parecidos):
  `.../BECKER ADV/01 ADMINISTRATIVO/00 PLANILHAS/1 PRAZOS E AUDIÊNCIAS/PRAZOS BECKER 2026.xlsx`
  Abas relevantes: `PRAZOS`, `ATIVOS ATUAL`, `PERICIA`, `AUDIÊNCIA`.
- `prazos_nums.json`: lista de números de processo já normalizados (somente dígitos, sem pontuação) que já constam na aba PRAZOS. Usada para decidir se um processo da Entrada é caso novo ou caso recorrente.
- Backup obrigatório antes de qualquer alteração: copiar o xlsx original para a pasta de outputs com nome `PRAZOS_BECKER_2026_backup_<timestamp>.xlsx` antes de escrever qualquer coisa.

## 3. Gravação segura do xlsx (limitação de ambiente já observada)

Nunca sobrescrever direto com `wb.save(caminho_original)` (bug observado, pode não persistir). Fluxo correto:

1. Salvar para um arquivo temporário no mesmo diretório (ex. `.tmp_write.xlsx`).
2. `os.replace(tmp, caminho_original)` para substituição atômica.
3. Reabrir o arquivo do zero do disco.
4. Conferir célula a célula que a alteração persistiu antes de reportar sucesso.

## 4. Critério de caso recorrente vs. caso novo

Normalizar o número do processo da Entrada (remover toda pontuação, manter só dígitos) e verificar se esse número normalizado já está em `prazos_nums.json` (ou já existe na coluna B da aba PRAZOS).

- Se já existe (recorrente): não criar nova linha na aba PRAZOS. Criar apenas a tarefa no Legalmail com o prazo correto. Se houver perícia designada, ainda assim criar a entrada na aba PERICIA (isso vale mesmo para casos recorrentes).
- Se não existe (novo): adicionar nova linha ao final da aba PRAZOS com:
  - Coluna A: Tribunal
  - Coluna B: N° do processo
  - Coluna C: Cliente x Parte contrária
  - Coluna F (INTERNO): fórmula `=IF($D{linha}="","",WORKDAY($D{linha},-2))`
  - Coluna G (ADVOGADO): nome completo do advogado, obtido cruzando com a coluna K (ADVOGADO PRINCIPAL) da aba ATIVOS ATUAL (não usar a abreviação da coluna Q ADVOGADA ATUAL, apenas para localizar a linha correspondente)
  - Coluna H: status "PENDENTE"
  - Coluna I: "Segredo de Justiça" quando aplicável
  - Colunas D e E: deixar vazias (preenchimento manual posterior)

## 5. Regras de cálculo de prazo

1. Prazo civil: CPC arts. 218 a 232 — contagem em dias úteis, exclusão do dia do começo, prorrogação se o vencimento cair em dia não útil. Confirmar vigência antes de aplicar.
2. Prazo trabalhista: CLT art. 775 e seguintes, na redação dada pela Lei 13.467/2017 (reforma trabalhista) — contagem em **dias úteis** (não mais dias corridos, que era a regra anterior à reforma). Confirmar vigência.
3. Juizados Especiais Cíveis (Lei 9.099/95): contagem em **dias corridos**, conforme Enunciado FONAJE 165.
4. Identificar sempre o prazo específico do ato/recurso exato da intimação (agravo, embargos, apelação, recurso inominado, cumprimento de sentença etc.), nunca aplicar prazo genérico quando existir prazo próprio.
5. Hipótese de embargos: mesmo que a intimação não use essa palavra, se a decisão comportar embargos de declaração (ou outros), considerar esse prazo no cálculo.
6. Intimação para sessão de julgamento: prazo a lançar é de 5 dias úteis antes do início da sessão, para memoriais e sustentação oral.
7. Margem de segurança interna padrão: 2 dias úteis a menos que o prazo legal calculado, usada como "prazo interno" recomendado, exceto em janelas puramente administrativas de ciência (ex. prazo de 1 dia só para anotação/ciência), onde essa margem não é aplicada.
8. Antes de aplicar qualquer prazo, confirmar que a norma citada ainda está em vigor e considerar o ano vigente para valores atualizáveis anualmente (ex. salário mínimo).
9. Regra de disponibilização eletrônica (DJEN/PJe/eProc): quando a intimação é disponibilizada em um dia útil, ela é considerada realizada no primeiro dia útil seguinte à disponibilização (Resolução CNJ 455/2022 e art. 224 combinado com art. 231, V do CPC), e o prazo começa a correr a partir do primeiro dia útil após essa data, excluindo feriados nacionais e estaduais (ex. 07/09 Independência do Brasil).
10. Sempre que o próprio eProc informar explicitamente "Data inicial da contagem do prazo" e "Data final", usar esses valores diretamente em vez de recalcular manualmente — eles já incorporam feriados e regras internas do tribunal. Usar o cálculo manual apenas como conferência cruzada.
11. Quando o despacho não especificar quantidade de dias, buscar no histórico do próprio processo uma tarefa anterior análoga (mesmo tipo de manifestação) e adotar o mesmo número de dias por analogia, sinalizando isso como estimativa sujeita a confirmação.

## 6. Reaproveitamento de Tipo de tarefa no Legalmail

Nunca criar um Tipo novo (opção "(novo)") sem necessidade real. Antes de criar qualquer tarefa:

1. Abrir o histórico do processo (linha do tempo / eventos anteriores) e procurar tarefas já criadas nesse mesmo processo.
2. Identificar o Tipo usado em tarefas anteriores de teor semelhante (ex. "CIENCIA", "MANIFESTAÇÃO CITAÇÃO", "MANIFESTAÇÃO ENDEREÇO", "MANIFESTAÇÃO SOBRE PERÍCIA/DOCUMENTOS/ESCLARECIMENTOS (CLT)").
3. Reutilizar esse Tipo exato na nova tarefa.

## 7. Segredo de justiça

A tag "Segredo de Justiça" no cabeçalho do processo não significa necessariamente que o conteúdo do despacho está inacessível. Verificar caso a caso se o teor completo está de fato disponível (já houve casos com a tag presente e conteúdo totalmente legível, e casos sem acesso real ao conteúdo). Nunca inventar dados quando o conteúdo estiver genuinamente bloqueado — nesse caso, parar e reportar a limitação.

## 8. Campos obrigatórios da tarefa no Legalmail

- Tipo (obrigatório, reaproveitado do histórico do processo quando possível).
- Encarregado: sempre o advogado responsável pelo processo (localizado na aba ATIVOS ATUAL, coluna K, para casos novos; para casos recorrentes, o advogado já responsável no Legalmail).
- Descrição: resumo objetivo do teor da intimação/decisão e da providência recomendada, sem dois-pontos dentro da frase.
- Prazo: campo obrigatório, calculado conforme seção 5, sempre com a data final legal e, quando aplicável, a data interna com margem de segurança.

## 9. Parte 2 — Audiências

1. Filtrar audiências com data/hora maior que o dia anterior à execução, todas por página.
2. Comparar processo (normalizado) com a coluna B da aba AUDIÊNCIA.
3. Para cada audiência sem linha correspondente, adicionar linha nova (sem deixar linhas em branco no meio) com Cliente em maiúsculas, N° do processo, Evento (AUDIÊNCIA DE INSTRUÇÃO/CONCILIAÇÃO), Área (TRABALHISTA para PJe/TRT, CÍVEL para eProc/TJSC), Data e Horário.
4. Deixar em branco LINK, CONTATO DO CLIENTE, CIENTE, AGENDADO(A), CONFIRMAÇÃO, TESTEMUNHAS, OBSERVAÇÕES. Nunca marcar "SIM" em AGENDADO(A) automaticamente (só manualmente após lançar na agenda do Google).
5. Audiências canceladas também devem ser registradas, para manter histórico.

## 10. Relatório final ao usuário

Nunca usar dois-pontos dentro de frases/parágrafos. Nunca usar bullet points ou tabelas — apenas parágrafos corridos. Reportar quantos casos novos foram cadastrados/arquivados e quantas audiências/perícias foram adicionadas, listando cliente e número de processo de cada item novo. Se algo não pôde ser verificado (login necessário, conteúdo sigiloso inacessível, navegação falhou), parar e explicar exatamente o que impediu a execução, sem inventar dados.

## 11. Observação sobre a camada de automação usada nesta execução

Esta execução foi feita via automação de navegador (Claude in Chrome), clicando na interface web do Legalmail. Os detalhes de coordenadas de clique, fluxo de modais (Nova tarefa, Encarregados, Prazo/calendário) e a necessidade de reclicar no item da lista para recarregar o cabeçalho são específicos dessa camada de UI e não se aplicam a uma implementação via API/código. Caso o Legalmail exponha API própria, a reimplementação em código deve usar os endpoints equivalentes a: listar itens da Entrada, criar tarefa (tipo, descrição, encarregado, prazo, processo vinculado), mover processo da Entrada para o Acervo, e listar/filtrar audiências — preservando toda a lógica de negócio das seções 4 a 10 acima, que é independente da camada de UI.
