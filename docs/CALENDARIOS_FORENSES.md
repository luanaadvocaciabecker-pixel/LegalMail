# Calendários forenses por tribunal

`src/legalmail_prazos/tribunais.py` guarda feriados forenses e suspensões
de prazo específicas de tribunais, para complementar o calendário nacional
genérico (`src/legalmail_prazos/holidays.py`). Diferente do calendário
nacional, essas informações são **republicadas todo ano** pelo próprio
tribunal (portaria/resolução) e por isso são cobertas ano a ano no código,
nunca "de memória" ou por extrapolação.

## Cobertura atual (2026)

| Tribunal | Fonte | O que cobre |
|---|---|---|
| TJSC | Resolução GP TJSC n. 1/2026 (com alterações posteriores) — https://www.tjsc.jus.br/calendario-institucional | Quinta-feira Santa (02/04), Corpus Christi (04/06), Divino Espírito Santo (25/05) |
| TJSC | Resolução TJ n. 30/2025 | Suspensão de prazo de 20/dez/2026 a 20/jan/2027 (mais longa que o recesso genérico do art. 220 CPC, que vai só até 6/jan) |
| TRT12 | Portaria "Calendário Feriados 2026", alterada pela Portaria 57/2025 — https://dspace.trt12.jus.br | Feriados regimentais transferidos: 11/08→10/08, 28/10→30/10, 08/12→07/12 |
| TRT12 | mesma Portaria acima | Suspensão de prazo de 20/dez/2026 a 20/jan/2027, mesmo período do TJSC |

Esses dois tribunais foram priorizados porque respondem por ~85% dos
processos do escritório (ver contagem por tribunal na aba PRAZOS/ATIVOS
ATUAL). Qualquer outro tribunal (STJ, TST, TJSP, TRF4, TJRS, TJRJ, TJPR,
TRT9, TRT15 etc.) usa hoje só o calendário nacional genérico —
`calendario_para_tribunal` retorna `confirmado=False` nesses casos, para
deixar explícito que feriados locais próprios podem estar faltando.

## Como atualizar para um novo ano

1. Pesquisar a portaria/resolução vigente do tribunal para o ano em
   questão (site oficial do tribunal é a fonte primária; buscadores como
   AASP/Legalcloud costumam consolidar isso também, mas confirme na fonte
   oficial antes de usar).
2. Adicionar um novo bloco `if ano == <ano>: return {...}` em
   `feriados_tjsc`/`feriados_trt12`/`suspensao_prazos_tjsc_trt12`, com a
   fonte citada no docstring da função (não sobrescrever o ano anterior —
   manter o histórico).
3. Adicionar testes em `tests/test_tribunais.py` confirmando as novas
   datas.
4. Se o escritório for atuar com frequência em outro tribunal ainda não
   coberto, pesquisar o calendário forense oficial dele e seguir o mesmo
   padrão, adicionando ao mapeamento em `calendario_para_tribunal`.

## Por que isso importa

Um feriado forense tratado como dia útil por engano desloca a data fatal
calculada para depois da data real — o tipo de erro mais perigoso possível
aqui (parece que ainda há prazo quando na verdade já venceu). Por isso
`calendario_para_tribunal` nunca finge ter dado para um tribunal que não
foi pesquisado: prefere avisar (`confirmado=False`) a arriscar um cálculo
incompleto sem sinalização.
