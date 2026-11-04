# Explicação das decisões

Cada seção diz o que é a técnica, por que ela está no projeto e como eu explicaria numa entrevista. Os números citados saíram de `resultados/` e `evidencias/`.

## Recorte

A unidade de análise é o município, e a eleição é o 1º turno de 2022 para presidente, com 2018 como comparação. São 5.570 municípios em cada ano. O voto no exterior fica de fora porque não pertence a nenhum município.

Escolhi o município porque as variáveis explicativas (perfil do eleitorado, PIB, população, área) existem nesse nível para o país inteiro. O 1º turno tem todos os municípios votando, e presidente é a mesma disputa em todo lugar.

Numa entrevista, eu diria: "Cada linha é um município. A pergunta é sobre características do lugar, então eu não posso concluir nada sobre o comportamento de uma pessoa a partir disso. Se um município com mais idosos tem mais abstenção, isso não prova que são os idosos que deixaram de votar."

## Agregação de zonas para município

A fonte do TSE vem por zona eleitoral, e uma cidade grande tem várias zonas (em 2022, São Paulo tinha 58 e o Rio de Janeiro, 49). Somei aptos, comparecimento e abstenções das zonas de cada município.

O cuidado está antes da soma. A tabela repete cada zona uma vez por cargo, com os mesmos aptos em cada linha, e mistura eleições suplementares. Somar sem filtrar dá 778.687.320 aptos no 1º turno de 2022, cerca de cinco vezes o eleitorado real (155.758.656 fora do exterior). Por isso a consulta já sai do BigQuery filtrada por cargo, turno e tipo de eleição, e o código confere que nenhum par município/zona aparece duas vezes.

Numa entrevista, eu diria: "Eu filtro o grão antes de agregar. Se a tabela tem uma linha por zona e por cargo, eu fixo o cargo e só então somo as zonas. E eu não confio no filtro: o código para se encontrar uma zona repetida, e há um teste que simula essa duplicação."

## Taxa de abstenção

A taxa é abstenções dividido por aptos, em pontos percentuais na análise (21,3 em vez de 0,213). Assim os coeficientes já saem em pontos percentuais.

Numa entrevista, eu diria: "Eu modelo a taxa e não o número absoluto de abstenções, porque o número absoluto só reflete o tamanho do município."

## Testes de dados

Os testes estão em `tests/test_dados.py` e rodam sobre os Parquet locais, sem BigQuery. São 21 casos (os testes por ano rodam para 2022 e 2018). Mais 4 em `tests/test_espacial.py` conferem o I de Moran em casos de resposta conhecida.

Filtro da extração: confere que só há presidente, 1º turno, eleição ordinária e nenhuma linha do exterior. Se alguém mexer na consulta e esquecer um filtro, o teste falha antes da análise.

Zona única por município: cada par município/zona aparece uma vez. É o teste que pega a repetição por cargo.

Unicidade do município: o código IBGE é único e tem 7 dígitos. Se um join duplicasse linhas, o modelo contaria o mesmo município duas vezes.

Cobertura: são 5.570 municípios e 27 UFs, e o único município do diretório que falta é Boa Esperança do Norte (MT), que não teve votação em 2018 nem em 2022. O teste compara com uma lista explícita de faltantes, então um município perdido no caminho aparece na hora.

Taxas entre 0 e 1: a taxa de abstenção fica entre 0 e 1, e as proporções do perfil entre 0 e 100. Um valor fora disso indicaria divisão pelo número errado.

Conciliação: aptos = comparecimento + abstenções em todo município, com uma exceção documentada (Manaus em 2022, 84 eleitores de diferença na zona 68, que já vem assim da fonte). O teste aceita só essa exceção com esse valor; qualquer divergência nova falha.

Soma das zonas contra a tabela municipal: a soma que eu fiz bate com a tabela municipal da própria Base dos Dados nos três números e nos 5.570 municípios. É uma conferência independente da agregação.

Sem nulos: as variáveis usadas no modelo não têm nulo nem infinito. O infinito apareceria se o logaritmo recebesse zero.

Categorias do perfil: a soma das faixas de instrução e de gênero é igual ao total de eleitores, o que mostra que nenhum código ficou de fora da consulta.

Perfil e votação: o total de eleitores do perfil fica entre 90% e 110% dos aptos em todo município. O perfil é uma fotografia do cadastro e não precisa bater exato; na prática a razão ficou entre 0,94 e 1,03 em 2022.

Numa entrevista, eu diria: "Os testes protegem as premissas que a análise usa. Quando a fonte tem um defeito real, como a zona de Manaus, eu documento a exceção com o valor exato. Assim o teste continua pegando qualquer problema novo."

## Variáveis explicativas

Usei a proporção do eleitorado com 16 ou 17 anos e com 70 anos ou mais (as duas faixas em que o voto é facultativo), a proporção de mulheres, a de analfabetos ou que só leem e escrevem, a de superior completo, o eleitorado apto, o PIB per capita, a razão entre aptos e população e a densidade demográfica, além da região.

O eleitorado, o PIB per capita e a densidade entram em log na base 2. Essas variáveis vão de alguns milhares a milhões, e o log comprime a escala. A base 2 deixa a leitura simples: o coeficiente é o que muda quando a variável dobra.

Numa entrevista, eu diria: "Escolhi a base 2 para poder dizer 'quando o eleitorado dobra, a abstenção sobe tanto', que qualquer pessoa entende."

## Regressão linear

A regressão estima, para cada variável, quanto a abstenção muda em média quando ela aumenta uma unidade e as outras ficam iguais. Usei mínimos quadrados ordinários do statsmodels, com a região como variável categórica e o Sudeste como referência.

Com as variáveis de 2022 o R² é 0,43: o modelo explica 43% da variação da abstenção entre municípios, e 57% fica sem explicação. Só saber a UF já explica 34,5%.

Numa entrevista, eu diria: "Uso a regressão para descrever associações com controle das outras variáveis, e não para provar causa. Um coeficiente diz que, comparando municípios parecidos no resto, os que têm mais de X têm mais abstenção. Não diz que aumentar X aumentaria a abstenção."

## Erro padrão agrupado por UF, comparado ao HC3

O erro padrão diz quanta incerteza há em cada coeficiente. A fórmula comum supõe que os erros do modelo têm a mesma variância em todo município e são independentes entre si. As duas coisas falham aqui.

A variância não é constante: o teste de Breusch-Pagan rejeita essa hipótese com folga (estatística 267,9 em 2022). HC3 corrige isso, mas continua supondo independência. E os erros não são independentes: só a UF explica 18,6% da variação dos resíduos. Municípios do mesmo estado erram juntos, provavelmente por fatores que o modelo não mede e que valem para o estado inteiro. O erro agrupado por UF (cluster) permite essa correlação dentro de cada estado.

A diferença é grande. A proporção de eleitores com 16 ou 17 anos tem p < 0,001 com HC3 e p = 0,38 com cluster por UF. Com HC3 eu teria anunciado uma associação que não se sustenta. Usei o cluster como resultado principal, com correção para poucos grupos e distribuição t com 26 graus de liberdade (27 UFs menos 1). A ressalva é que 27 grupos é pouco para esse método, então os p-valores devem ser lidos com alguma folga. A tabela de coeficientes traz os dois erros lado a lado.

Numa entrevista, eu diria: "Escolhi o cluster por UF porque os resíduos de municípios do mesmo estado são correlacionados, e eu medi isso: a UF explica 18,6% dos resíduos. HC3 só resolve a variância desigual. Com HC3, quatro variáveis (16 ou 17 anos, mulheres, superior completo e PIB per capita) e a região Norte pareciam significativas a 5% e deixaram de ser."

## VIF (multicolinearidade)

O VIF mede quanto a variância de um coeficiente aumenta porque aquela variável é parecida com as outras. VIF 1 significa nenhuma sobreposição; acima de 5 ou 10 os coeficientes ficam instáveis e difíceis de separar.

Escolaridade, PIB per capita e jovens são correlacionados (a correlação entre baixa escolaridade e o log do PIB per capita é -0,65; com o PIB per capita sem log, -0,37), então era preciso medir. O maior VIF foi 3,67 em 2022 (baixa escolaridade) e 3,88 em 2018. Por isso mantive todas as variáveis.

Numa entrevista, eu diria: "Medi o VIF antes de interpretar os coeficientes. Abaixo de 4 em todas as variáveis, então as estimativas não estão se misturando a ponto de inverter sinais."

## Resíduos

Resíduo é a diferença entre a abstenção observada e a prevista. Olhei três coisas: se a variância é constante (não é, por isso o erro robusto), se a distribuição é próxima da normal e se os resíduos se agrupam por UF (se agrupam, por isso o cluster).

O teste de Jarque-Bera rejeita a normalidade, mas o desvio é pequeno: assimetria 0,31 e curtose 3,42 (a normal tem 0 e 3), e 4,8% dos resíduos passam de dois desvios padrão, perto dos 4,6% esperados numa normal. Com 5.570 observações, isso pouco afeta os intervalos dos coeficientes.

Numa entrevista, eu diria: "Com milhares de observações, quase todo teste de normalidade rejeita. Eu olho o tamanho do desvio. Aqui a cauda é só um pouco mais pesada que a normal, e a variância desigual eu já trato com o erro robusto."

## Efeito do 1º ao 3º quartil

Os coeficientes estão em unidades diferentes (ponto percentual de idosos, dobra do eleitorado), então não dá para comparar um com o outro direto. Multipliquei cada coeficiente pela distância entre o 1º e o 3º quartil da variável. O resultado é quanto a abstenção muda ao sair de um município típico "baixo" para um "alto" naquela variável, com as outras fixas.

Numa entrevista, eu diria: "É uma forma de pôr todas as variáveis numa régua só, sem padronizar e perder a unidade original."

## Robustez com efeito fixo de UF

Rodei o mesmo modelo trocando região por UF. Assim cada estado tem seu próprio nível de abstenção, e os coeficientes passam a comparar só municípios dentro do mesmo estado. O R² sobe para 0,54. Baixa escolaridade, 70 anos ou mais, eleitorado e densidade mantêm o sinal e continuam com p < 0,01; superior completo passa a ter p < 0,001.

Numa entrevista, eu diria: "Se um resultado só aparecesse comparando estados diferentes, ele poderia ser efeito do estado. Os principais aparecem também dentro de cada estado."

## Baselines

Antes do modelo de árvores, rodei dois modelos simples. A média prevê a mesma abstenção para todo município; qualquer modelo útil tem que errar menos que ela. A regressão linear é o mesmo modelo da análise inferencial, agora avaliado em dados que não viu.

Numa entrevista, eu diria: "Sem baseline eu não sei se um MAE de 3 é bom. Contra a média, que erra 3,8 pontos, eu sei."

## Modelos de árvores

Gradient boosting (`HistGradientBoostingRegressor`) e random forest captam relações não lineares e interações sem que eu precise escrevê-las. Usei os parâmetros padrão do gradient boosting e 300 árvores com folha mínima de 5 no random forest, sem busca de hiperparâmetros.

Numa entrevista, eu diria: "Não ajustei hiperparâmetros para não otimizar em cima da própria validação. A comparação com a regressão mostra quanto se ganha só com a flexibilidade do modelo."

## KFold e GroupKFold por UF

Validação cruzada divide os dados em partes, treina em quatro e testa na quinta, cinco vezes. No KFold comum as partes são sorteadas, então municípios da mesma UF caem no treino e no teste ao mesmo tempo. Como municípios do mesmo estado são parecidos, o modelo acerta parte do teste por já ter visto os vizinhos.

No GroupKFold por UF, cada estado inteiro fica só no treino ou só no teste. A pergunta respondida passa a ser "o modelo funciona num estado que ele não viu?". A diferença foi grande: o gradient boosting tem R² 0,56 no KFold e 0,32 no GroupKFold. Considero o GroupKFold o número honesto para a pergunta do projeto, porque a relação entre as características e a abstenção deveria valer fora do estado onde foi aprendida.

Numa entrevista, eu diria: "Quando os dados têm grupos, o KFold aleatório vaza informação do grupo para o teste. Eu rodei os dois e reporto os dois, mas o resultado que eu defendo é o por grupo: R² de 0,32. O KFold mede outra coisa."

## Dependência espacial (I de Moran)

O erro agrupado por UF supõe que os erros de municípios de estados diferentes são independentes. Mas a divisa entre estados é uma linha no mapa: um município no sertão de Pernambuco pode se parecer mais com o vizinho do lado paraibano do que com a capital do próprio estado. Medi isso em `src/espacial.py`.

Para cada município, peguei os 8 mais próximos pelo centroide (a mediana da distância até eles é 27 km) e comparei o resíduo do município com a média dos resíduos desses vizinhos. O I de Moran resume essa comparação numa escala de -1 a 1: perto de zero, os vizinhos não têm nada a ver um com o outro; perto de 1, vizinhos erram para o mesmo lado. O valor-p vem de 999 sorteios em que os resíduos trocam de lugar entre os municípios ao acaso.

Em 2022 o I dos resíduos foi 0,475, e o maior valor entre os 999 sorteios foi 0,022. Com 5 e com 10 vizinhos, deu 0,506 e 0,460, então o resultado não depende da escolha de 8. A média dos vizinhos explica 46,0% da variação dos resíduos, bem mais que os 18,6% da UF. Tirando de cada resíduo a média do seu estado, o I ainda fica em 0,365. E olhando só os vizinhos do outro lado da divisa (1.309 municípios têm pelo menos um), a correlação entre o resíduo e a média desses vizinhos é 0,29. Parte disso vem do nível de cada estado; tirando a média da UF dos dois lados, fica em 0,22.

Fiz duas checagens para ver se isso muda alguma conclusão.

1. **Inferência.** Rodei a mesma regressão com o erro agrupado por grupos de municípios próximos, formados a partir das coordenadas e sem olhar a divisa (27 e 60 grupos). Usei t com G − 1 graus de liberdade, como na regressão principal, para comparar iguais. Os valores-p ficaram menores do que com a UF: 70 anos ou mais foi de 0,043 para 0,018 (27 grupos) e 0,0045 (60 grupos). A região Norte, que tinha 0,087 com a UF, fica em 0,071 com 27 grupos e 0,018 com 60: é a única mudança de lado do limite de 5%. As outras variáveis sem associação clara continuam sem. Mantive a UF como resultado principal porque é o agrupamento mais conservador.
2. **Previsão.** Repeti a validação cruzada com os grupos espaciais no lugar da UF. O random forest teve R² de 0,43 com 27 grupos e 0,45 com 60, contra 0,33 deixando o estado inteiro de fora. O GroupKFold por UF continua sendo a validação mais severa. Não dá para dizer só com isso que a divisa pesa mais que a distância, porque os grupos por UF e os do k-means têm tamanhos e formas diferentes.

O que fica: há um padrão regional que o modelo não mede, e ele atravessa as divisas. Não ajustei um modelo espacial (de erro ou de defasagem espacial). Ele mudaria a pergunta e seria difícil de interpretar com segurança.

Numa entrevista, eu diria: "Testei se os erros de municípios vizinhos se parecem, e se parecem: I de Moran de 0,48, muito acima do que o acaso dá. Então conferi se isso derrubava alguma conclusão. O agrupamento por estado já era o mais conservador para os valores-p, e a validação deixando o estado de fora já era a mais dura para a previsão. O diagnóstico mostra o que falta no modelo. Nenhuma associação que eu afirmei desaparece; a única mudança é a região Norte passar a ter associação com 60 grupos."

## Métricas: MAE e R²

O MAE é o erro absoluto médio, na mesma unidade do alvo: um MAE de 3,10 quer dizer que o modelo erra, em média, 3,1 pontos percentuais de abstenção. O R² compara o erro do modelo com o erro de prever a média; 0 é igual à média, 1 é acerto perfeito, e pode ser negativo quando o modelo erra mais que a média.

Calculei as duas de duas formas: juntando as previsões fora da amostra das cinco partes e calculando uma vez sobre os 5.570 municípios, e fazendo a média das cinco partes. No GroupKFold o R² médio por parte é menor (0,23 para o gradient boosting, desvio de 0,17), porque cada parte tem poucos estados e uma variação própria menor. Os números do README são os empilhados.

Numa entrevista, eu diria: "Uso o MAE para comunicar o tamanho do erro e o R² para comparar com a média. Reporto também a variação entre partes, que mostra que o desempenho depende de quais estados ficam de fora."

## Importância por permutação

Para cada variável, embaralho os valores dela na parte de teste e meço quanto o MAE piora. Se piorar muito, o modelo dependia dela. Fiz isso nas partes de teste do GroupKFold, com 10 embaralhamentos por variável, e tirei a média das cinco partes.

Preferi esse método à importância interna das árvores porque ele é medido em dados que o modelo não viu e na unidade do erro. O limite é que, quando duas variáveis são correlacionadas, embaralhar uma deixa a outra carregar parte da informação, e as duas parecem menos importantes do que são.

Em 2022 a ordem foi eleitorado apto (o MAE sobe 0,44 ponto quando ele é embaralhado), 70 anos ou mais (0,36), baixa escolaridade (0,25) e região (0,24). PIB per capita e razão aptos/população quase não mudam o erro (0,01).

Numa entrevista, eu diria: "Importância por permutação mostra de que o modelo depende para prever, e não o que causa a abstenção. E eu calculo em dados de teste, para não premiar variável que só ajudou a decorar o treino."

## Seed fixa

Todos os sorteios (divisão das partes, árvores, embaralhamentos) usam `random_state=42`. Rodar o pipeline de novo gera os mesmos números, e eu conferi isso: a segunda execução do zero reproduziu as métricas.

Numa entrevista, eu diria: "Fixei a seed para que qualquer pessoa reproduza exatamente os meus números."

## Sem ponderação por tamanho

Cada município pesa igual na regressão e no modelo, de Borá (SP), com 1.039 eleitores aptos em 2022, a São Paulo, com 9.320.706. A pergunta é sobre características dos municípios, e não sobre o eleitor médio do país. Uma regressão ponderada pelo eleitorado responderia outra pergunta e ficou fora do MVP.

Numa entrevista, eu diria: "Com peso igual, um município de mil eleitores conta tanto quanto São Paulo. Isso é coerente com a pergunta, mas o resultado não descreve o eleitor brasileiro médio."
