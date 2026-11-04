# Validação da fonte

Consultas executadas em 04/11/2026. As de votação estão em `src/validar_fonte.py` e o resultado em `evidencias/validacao_fonte.json`. As do perfil do eleitorado estão em `src/extracao.py` e os testes em `tests/test_dados.py`.

## Tabelas usadas

| Tabela (Base dos Dados) | Uso | Organização física |
|---|---|---|
| `br_tse_eleicoes.detalhes_votacao_municipio_zona` | aptos, comparecimento e abstenções por zona | partição por `ano` (faixa de 2 em 2 anos), clustering por `sigla_uf` |
| `br_tse_eleicoes.detalhes_votacao_municipio` | só para conferir a soma das zonas | igual à anterior |
| `br_tse_eleicoes.perfil_eleitorado_municipio_zona` | idade, escolaridade e gênero do eleitorado | partição por `ano`, clustering por `sigla_uf`, cerca de 3 GB no total |
| `br_tse_eleicoes.dicionario` | significado dos códigos do perfil | tabela pequena |
| `br_ibge_pib.municipio` | PIB municipal de 2018 e 2022 | sem partição, 8,4 MB |
| `br_ibge_populacao.municipio` | população de 2018 | clustering por `ano`, `sigla_uf`, `id_municipio` |
| `br_ibge_censo_2022.municipio` | população e área em 2022 | sem partição, 0,56 MB |
| `br_bd_diretorios_brasil.municipio` | nome, região, capital e centroide | sem partição |

Nomes de tabelas e colunas foram conferidos em `INFORMATION_SCHEMA.TABLES` e `INFORMATION_SCHEMA.COLUMNS` do dataset `br_tse_eleicoes` e nos metadados das tabelas do IBGE antes de escrever as consultas.

## A repetição por cargo

Na tabela de votação por zona, cada zona aparece uma vez por cargo, e os aptos se repetem em cada linha. No 1º turno de 2022, somar a coluna `aptos` sem filtrar o cargo dá 778.687.320. Fixando presidente e retirando o exterior, o total é 155.758.656. A soma sem filtro conta cada eleitor cerca de cinco vezes.

A tabela também mistura eleições que não são a ordinária: um conselho distrital em um único município (`eleicao conselho distrital 2018 fn` e `eleicao conselho distrital 2022`) e a eleição suplementar para senador em Mato Grosso em 2018 (146 linhas em 141 municípios). Por isso a extração filtra `cargo = 'presidente'`, `turno = 1` e `tipo_eleicao = 'eleicao ordinaria'` antes de qualquer soma, e `src/features.py` confere que não sobrou nenhum par município/zona repetido.

## Por que presidente

Governador, senador e deputado federal também cobrem os 5.570 municípios. Escolhi presidente porque é a mesma disputa em todo o país e porque é o cargo do Eleições em Dados, o que permite conferir os números com o projeto anterior. Os aptos de presidente são sempre maiores ou iguais aos de governador no mesmo município: a diferença soma 201.153 eleitores em 2022 (em 1.581 municípios, incluindo as 27 capitais) e 55.426 em 2018 (939 municípios). Em nenhum município presidente tem menos aptos que governador. O padrão é compatível com o voto em trânsito para presidente, mas não verifiquei essa explicação nos dados. A diferença é de 0,13% do eleitorado em 2022.

## Exterior

As linhas com `sigla_uf = 'ZZ'` são o voto no exterior (181 linhas em 2022, 171 em 2018). Elas não têm `id_municipio` e ficam fora do recorte. Nelas aparecem linhas com aptos e sem comparecimento nem abstenção registrados (41 em 2022 e 33 em 2018), que não fecham a conta aptos = comparecimento + abstenções.

## Conciliação aptos = comparecimento + abstenções

Fora do exterior, uma única linha de presidente no 1º turno não fecha: Manaus (AM), zona 68, em 2022, com 87.671 aptos, 72.962 comparecimentos e 14.625 abstenções (84 eleitores sem destino). Nos outros cargos dessa zona a diferença é de 81 eleitores; na tabela municipal de presidente, os mesmos 84. Mantive o dado como está: a taxa de abstenção é calculada como abstenções / aptos, e o teste de conciliação aceita só essa exceção, com esse valor. Em 2018 todas as linhas fecham.

A soma das zonas de cada município é igual, em aptos, comparecimento e abstenções, à tabela `detalhes_votacao_municipio` para os 5.570 municípios nos dois anos.

## Conferência com o Eleições em Dados

O projeto anterior mediu a abstenção do DF no 1º turno para presidente: 18,7025% em 2018 e 17,5395% em 2022. Aqui, Brasília (o DF é um município só, com 19 zonas) tem 18,7025% e 17,5395%.

## Perfil do eleitorado

Os códigos vêm da tabela `dicionario`:

- `grupo_idade`: `1600` e `1700` são 16 e 17 anos; de `7074` a `9999` são 70 anos ou mais; `-3` é inválido.
- `instrucao`: `0` não informado, `1` analfabeto, `2` lê e escreve, `3` fundamental incompleto, `4` fundamental completo, `5` médio incompleto, `6` médio completo, `7` superior incompleto, `8` superior completo.
- `genero`: `0` não informado, `2` masculino, `4` feminino.

A soma das categorias de instrução e de gênero é igual ao total de eleitores em todos os municípios, então nenhum código ficou de fora. O perfil tem uma linha sem município (o exterior), com 697.078 eleitores em 2022 e 500.727 em 2018, que foi descartada.

O perfil é uma fotografia do cadastro e não coincide exatamente com os aptos da votação. A razão eleitores do perfil / aptos ficou entre 0,9413 e 1,0284 em 2022 (mediana 1,0016) e entre 0,9926 e 1,0141 em 2018 (mediana 1,0003). Isso também mostra que a partição de cada ano tem um único retrato: se tivesse dois, a razão ficaria perto de 2.

## Cobertura

O diretório de municípios tem 5.571 linhas. A votação de 2018 e de 2022 tem 5.570 municípios. O que falta é Boa Esperança do Norte (MT, código 5101837), que não aparece em nenhuma das duas eleições. PIB, população e Censo 2022 cobrem os 5.570 municípios sem nulos.

## Socioeconômico

Procurei IDHM na Base dos Dados. O dataset `mundo_onu_adh` existe, mas as tabelas `municipio`, `uf` e `brasil` aparecem com 0 linhas nos metadados, então ficaram de fora. Usei PIB per capita (PIB do ano dividido pela população) e densidade demográfica (população do Censo 2022 dividida pela área). Para 2022 a população vem do Censo 2022; para 2018, de `br_ibge_populacao.municipio` no ano de 2018. A área é a do Censo 2022 nos dois anos.
