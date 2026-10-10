# Guia da Agente Ana

Este é o guia de uso da **Agente Ana**, o sistema que emite notas fiscais de serviço (NFS-e) pelo Emissor Nacional e ajuda a controlar o dinheiro da empresa.

**Como usar este guia com uma inteligência artificial:** você pode enviar este arquivo pra uma IA de sua preferência e fazer perguntas em português simples, do tipo "como eu corrijo o CEP de um tomador?". Peça pra ela responder **só com o que está escrito aqui**. Se a resposta não estiver no guia, o certo é ela dizer que não sabe e indicar o suporte da Ana.

**Cuidados importantes:**

- Nunca cole senha, arquivo de certificado digital nem dados dos seus clientes em uma IA de terceiros.
- A IA pode errar. Na dúvida sobre imposto, código de serviço ou regime tributário, confirme com seu contador.
- Os nomes de botões e telas aparecem aqui **entre aspas**, do jeito que estão escritos no sistema.

---

## Como a Ana é organizada

A Ana tem dois produtos (módulos), vendidos separadamente:

- **Notas**: emissão de NFS-e. Telas: "NFS-e", "Notas em lote", "Tomadores" e "Calendário".
- **Financeiro**: recebimentos, despesas, contas do mês, extrato do banco e conciliação. Telas: "Painel" e "Conciliação" (e "Clientes", pra quem tem só o Financeiro).

Você só vê no menu as telas dos módulos que a sua empresa tem ligados.

Telas que todo mundo tem:

- **"Visão geral"**: o resumo do mês, no topo do menu.
- **"Empresa"**: os dados da empresa (CNPJ ativo), e-mails das notas, alíquota, certificado e módulos.
- **"Minha conta"**: seu nome, senha, aparelhos conectados, assinatura e o "Indique e ganhe".
- **"Ajuda"**: as perguntas frequentes e este guia.

Algumas palavras que aparecem muito:

- **Tomador**: é o seu cliente, a empresa pra quem você emite a nota (quem "toma" o serviço).
- **Competência**: o mês a que a nota se refere.
- **Prefeitura / Receita**: a nota só vale depois que é enviada e autorizada. A Ana faz esse envio pelo Emissor Nacional da NFS-e.
- **Certificado digital A1**: o arquivo que assina as notas em nome da empresa.
- **Dar baixa**: registrar que uma nota foi paga.

---

## 1. Primeiros passos e certificado digital

### A Ana funciona na minha cidade?

A emissão de notas depende de a prefeitura da sua cidade usar o **Emissor Nacional da NFS-e**. Na tela de cadastro, assim que você digita o CNPJ, a Ana preenche os dados da empresa e já confere se emite nota na sua cidade, pela lista publicada pela Receita.

Desde a versão 2026.10.7 a Ana consulta o CNPJ e mostra o resultado na hora, antes de criar a conta:

- **MEI**: a Ana atende em qualquer cidade.
- **Empresa do Simples Nacional (ME/EPP)**: a Ana atende quando a prefeitura usa o Emissor Nacional (lista publicada pela Receita). Você vai precisar do certificado digital A1 da empresa.
- **Empresa fora do Simples (Lucro Presumido ou Real)** ou **CNPJ que não está ativo**: a Ana ainda não atende.
- **Cidade ou regime que a Ana ainda não atende**: dá pra entrar na **lista de espera** com o seu e-mail. Quando a sua cidade entrar na lista, a Ana manda um e-mail avisando.
- Se a consulta da Receita estiver fora do ar, o cadastro segue normalmente e a equipe da Ana confere depois.

### Criar a conta

Na tela de cadastro você informa o CNPJ (o resto é preenchido sozinho), a razão social, a cidade, o e-mail e uma senha com pelo menos 8 caracteres. Também dá pra usar "Continuar com Google".

Depois de "Criar conta", a Ana manda um link de confirmação pro seu e-mail. Abra a caixa de entrada e clique no link pra ativar a conta. Se não achar, olhe no spam. Se não chegou, use o botão "Não chegou? Reenviar e-mail". Se você digitou o e-mail errado, faça o cadastro de novo com o e-mail certo.

A conta nova começa com um período de teste gratuito de 14 dias, sem precisar cadastrar cartão.

### Simulação

Existe um ambiente de simulação pra conhecer o sistema sem cadastro. Nele nada é enviado à Receita nem a ninguém, e a conta de exemplo é apagada automaticamente em 24 horas. Senha, assinatura e certificado digital só existem na conta de verdade.

### Entrar no sistema

Você pode entrar de três jeitos: com e-mail e senha, com "Continuar com Google" ou com "Entrar com código por e-mail". Nesse último, a Ana manda um código de 6 dígitos pro seu e-mail, válido por 10 minutos, e você entra sem precisar de senha.

### Primeiros passos de uma conta nova

Enquanto falta alguma coisa pra emitir, a Visão geral mostra o cartão "Primeiros passos pra emitir sua nota", com três passos, nesta ordem:

1. **Certificado digital A1**: clique em "Enviar o certificado". Sem certificado válido a emissão fica travada: os botões "Nova emissão" e "Enviar relatório da Shopee" ficam desligados e a tela mostra o aviso com o caminho pra Empresa › Certificado.
2. **Dados da empresa**: só o **regime tributário** é obrigatório (vai em toda nota) — o botão "Puxar pelo CNPJ" busca na Receita. Endereço (só aparece no PDF da nota) e alíquota do Simples (referência pra já vir preenchida) são opcionais: o cartão avisa, mas deixar em branco não trava nada.
3. **Seus tomadores**: "Escolher tomadores" abre o cadastro. Os tomadores mais comuns já vêm pré-cadastrados, com o serviço e a descrição prontos.

O cartão some sozinho quando os três passos estão feitos.

### Trazer notas antigas do Emissor Nacional

Se a empresa já emitia notas pelo Emissor Nacional, a Ana consegue trazer as notas antigas. Isso fica em "Empresa", aba "Notas" (não aparece na Visão geral), e precisa do certificado A1 carregado. O melhor é cadastrar os seus tomadores primeiro e importar depois.

É só leitura: nada é enviado à prefeitura nem aos tomadores. Antes de gravar, a Ana mostra o que encontrou e **você escolhe de quais tomadores trazer**. Já vêm marcados só os tomadores que você tem e os pré-cadastrados; os outros ficam de fora ("Não importar") até você marcar. Isso evita, por exemplo, trazer de uma vez centenas de vendedores da Shopee como se fossem tomadores seus. As notas importadas entram como já entregues ao tomador.

### Certificado digital A1

O certificado digital A1 é o arquivo com que a Ana assina as notas da empresa. É o mesmo que o contador costuma usar. Sem ele não dá pra assinar nem enviar nota.

Pra enviar o certificado:

1. Abra "Empresa" e vá na aba "Certificado".
2. Escolha o arquivo (termina em .pfx) e digite a senha do certificado.
3. Clique em "Enviar certificado".

A tela mostra se o certificado está "Carregado", a data de validade e avisa quando estiver "Vencido". Pra trocar por um novo, faça o mesmo caminho: o botão passa a se chamar "Substituir certificado".

Cuidados que a Ana toma com o certificado:

- **Vencido não entra nem assina**: um certificado vencido é recusado no envio, e nenhuma nota é assinada com ele. A mensagem diz que é preciso renovar com a certificadora.
- **Tem que ser da mesma empresa**: o certificado precisa ser do mesmo CNPJ da empresa (o da matriz serve para a filial). Certificado de outro CNPJ é recusado.
- **Aviso antes de vencer**: 30 dias antes do vencimento, a Ana manda um e-mail pros donos da conta e mostra o aviso em "Precisa da sua atenção".
- **Ainda não tem certificado?** Na aba Certificado e nos avisos aparece como conseguir um: a Ana tem um parceiro com preço especial (o botão abre o WhatsApp).

O certificado fica guardado de forma criptografada.

### Dados da empresa (emitente)

Em "Empresa", aba "Dados da empresa", ficam os dados que aparecem nas notas: razão social, nome fantasia, inscrição municipal, e-mail, telefone, endereço e o regime tributário (Simples Nacional, MEI, regime especial). O CNPJ não muda — outro CNPJ é outra empresa. O regime tributário vai em toda nota e é **obrigatório**: sem ele a Ana não gera a nota e mostra onde preencher. Na dúvida, confirme com seu contador. Depois de mexer, clique em "Salvar dados do emitente".

**MEI**: a nota do MEI sai sem alíquota e sem os campos que o MEI não pode mandar; o campo de alíquota nem aparece pra ele. O MEI também não tem retenção de ISS.

**Alíquota do ISS nas notas com ISS retido**: só para empresa do Simples que tem tomador que retém o ISS. É a parte do ISS na sua faixa do Simples (de 2% a 5%); quem sabe é o seu contador.

### IBS e CBS (reforma tributária)

Para a empresa do Simples Nacional (ME/EPP), a aba "Dados da empresa" tem o bloco "IBS e CBS (reforma tributária)". A partir de janeiro de 2027 a nota da empresa do Simples passa a levar IBS e CBS. Quem calcula os valores é o próprio sistema da nota (a Ana não calcula); a empresa só informa como recolhe:

- IBS e CBS pelo Simples Nacional (o mais comum, e o padrão);
- CBS pelo Simples e IBS pelo regime regular;
- IBS e CBS pelo regime regular.

A escolha vale por semestre ("Vale a partir de"). Clique em "Salvar e confirmar". Nos dois meses antes da virada do semestre (maio e junho, novembro e dezembro), "Precisa da sua atenção" pede pra confirmar de novo. O MEI não escolhe.

Por enquanto a nota ainda não leva esses campos: o governo ainda não publicou o formato final. Quando publicar, a Ana usa o que você já deixou guardado. Quando a nota autorizada trouxer os valores de IBS e CBS, o PDF mostra.

### Como você emite? (perfil)

No cadastro (ou na primeira vez que você entra depois da versão 2026.10.7), a Ana pergunta como você costuma emitir: muitas notas de uma vez, clientes fixos todo mês, fechamento do mês ou nota avulsa. Dá pra marcar mais de um (o primeiro é o principal), buscar pela sua profissão, escrever em "Não me encontrei" ou pular. A Visão geral ganha um atalho pro seu jeito de emitir. Pra mudar depois: "Empresa", aba "Dados da empresa", bloco "Como você costuma emitir suas notas?".

### Alíquota do Simples Nacional

Em "Empresa", aba "Dados da empresa", no bloco "Alíquota do Simples Nacional", você informa a alíquota do Simples Nacional. Ela serve só pra já vir preenchida no campo de alíquota quando você cria uma nota nova. A Ana não calcula imposto nem gera boleto: é pra você não esquecer de conferir o número todo mês. O Calendário mostra um lembrete de "Revisar alíquota do Simples Nacional". Depois de conferir, clique em "Confirmar".

### Notas de teste (homologação)

Em "Empresa", aba "Notas", existe a opção "Gerar notas de teste (homologação)".

- Desligada (o normal): as notas novas são de verdade.
- Ligada: as notas novas vão pro ambiente de teste da Receita e **não valem como nota fiscal**. Ligue só pra testar.

Quando está ligada, a tela de gerar nota avisa que a conta está gerando notas de teste.

### Preencher os dados da empresa pelo CNPJ

Não precisa digitar endereço e regime tributário. Em "Empresa", aba "Dados da empresa", o botão "Preencher pelo CNPJ" busca os dados na Receita e preenche só o que estiver em branco (endereço, cidade, regime tributário, nome fantasia, telefone e e-mail). O que você já escreveu não é trocado. Na "Visão geral", o passo "Dados da empresa" dos primeiros passos tem o mesmo atalho: "Puxar pelo CNPJ". A alíquota do Simples a Receita não informa: essa você (ou o seu contador) preenche.

### Depois do teste grátis (fase sem cobrança)

Enquanto a cobrança pelo painel não está no ar, ninguém "assina": quando o teste grátis termina, a pessoa abre "Minha conta" › "Assinatura" e clica em "Pedir liberação". A equipe da Agente Ana recebe o pedido, fala com ela pelo WhatsApp e autoriza o uso. Até lá a empresa fica só pra consulta (nada é apagado). O cadastro pede o WhatsApp justamente pra isso; quem já tinha conta informa em "Minha conta" › "Perfil".

### Novidades e versão

Quando sai uma atualização, ao entrar eu aviso ("Tem novidade desde a sua última visita") e ofereço um passeio rápido: "Ver o que mudou" passa por cada novidade, abrindo a tela e apontando o lugar; "Agora não" fecha. Quem acabou de criar a conta não recebe esse convite — vê as dicas normais de primeira visita. O sino no topo abre a tela "Novidades", com o que mudou em cada atualização (cada pessoa vê o que é do perfil dela: empresa, contador ou os dois). Uma bolinha no sino avisa quando saiu versão nova. O número da versão fica no rodapé do menu.

### Escolher o que importar do Emissor Nacional

Na revisão da importação dá pra **buscar** (nome, CPF/CNPJ, descrição), **ordenar** (maior valor, mais notas, nota mais recente, nome) e marcar ou desmarcar de uma vez só o que apareceu na busca.

### Desfazer uma importação

Importou a coisa errada ou ficou bagunçado? Dá pra desfazer a importação inteira:

- **Extrato do banco e planilha de controle**: em "Financeiro" › "Conciliação", no fim da tela, o bloco "Importações feitas" lista cada importação com o botão "Desfazer". Desfazer um extrato tira as linhas dele da conciliação, apaga os recebimentos e despesas que ele criou (as notas voltam a ficar a receber) e reabre as contas que ele tinha dado como pagas. O que foi lançado à mão continua.
- **Notas trazidas do Emissor Nacional**: em "Empresa" › "Notas e e-mails", o bloco "Importações feitas". Desfazer tira da Ana as notas que aquela importação trouxe e os tomadores que ela criou e ficaram sem nota. Nada muda no Emissor Nacional (as notas continuam válidas lá) e dá pra importar de novo. Notas geradas pela Ana nunca são apagadas por aqui.

### Mais de uma empresa (CNPJ) no mesmo login

No topo do menu fica o seletor "Empresa". Clique nele pra trocar de empresa ou em "Adicionar empresa" pra pôr outro CNPJ no mesmo login. Há dois caminhos: "Importar do Emissor Nacional" (com o certificado da empresa, a Ana traz o cadastro, os tomadores e as notas) ou "Cadastrar do zero" (você digita o CNPJ e confere os dados). Cada empresa tem seus próprios tomadores, notas e certificado.

### Dicas de cada tela

Na primeira vez que você abre uma tela, a Ana mostra dicas rápidas do que dá pra fazer nela. O botão de interrogação no topo mostra de novo as dicas da tela em que você estiver. Pra desligar essas dicas, ou pedir pra ver todas de novo, vá em "Minha conta", aba "Preferências".

---

## 2. Tomadores

### O que é a tela "Tomadores"

É a lista de quem você fatura: em que dia do mês, e o que já foi gerado. No topo, a barra "Notas de (mês)" mostra quantas notas do mês já foram geradas; dá pra trocar o mês pra conferir meses anteriores.

A lista tem duas abas: "Meus tomadores" (os seus) e "Todos os tomadores" (o catálogo, de onde você pode escolher com "Usar este tomador").

### Cadastrar um tomador

Clique em "Adicionar tomador". Há três jeitos:

1. **Enviar uma nota antiga.** Se você já emitiu nota pra esse cliente, clique em "Enviar uma nota antiga" e mande o PDF ou o XML. A Ana preenche o cadastro inteiro: quem é o cliente, o código do serviço e a descrição. Você só confere. É o jeito mais fácil.
2. **"Digitar o CNPJ".** A Ana busca na Receita a razão social e o endereço.
3. **"Escolher do catálogo".** Se o tomador já está no catálogo, a Ana mostra uma "Sugestão de preenchimento" com o que já foi usado com ele (código de serviço, descrição, dia). Use "Usar todas" ou escolha uma a uma.

Confira os campos e clique em "Cadastrar tomador".

### Os campos de "Como a nota sai"

- **"Apelido"**: como você chama esse tomador.
- **"Código do serviço"**: o tipo de serviço, pela lista nacional. Busque por número ou por palavra (por exemplo, "publicidade"). Só vale código da lista oficial. Afiliados costumam usar 17.06.01 (propaganda e publicidade) — confirme com seu contador.
- **"Código de tributação municipal"**: só é preciso se a sua prefeitura exigir. Escolha "Nenhum" se não souber.
- **"Item da NBS"**: opcional.
- **"O que vai escrito na nota"**: a descrição do serviço (veja abaixo).
- **"Mais opções"** (quase ninguém precisa mexer): "Cidade onde o serviço é prestado" (normalmente é a sua própria cidade), "Série da nota" (deixe 1 se não souber), "Quero revisar cada nota antes de assinar" e "Declarar o marketplace como intermediário".

Na edição de um tomador, o que você muda vale pras **próximas** notas dele — não altera notas já emitidas. Depois de mudar, clique em "Salvar alterações".

### Descrição que muda sozinha todo mês

Em "O que vai escrito na nota", você escreve o texto (por exemplo, "Comissão de vendas") e marca o que muda de uma nota pra outra:

- "Colocar o mês e o ano no fim do texto". Aí você escolhe "Qual mês aparece?" (o mês da nota, o mês anterior, dois ou três meses antes) e "Escrito como?" (por extenso ou em número).
- "Colocar o número da ordem de pagamento". A Ana pede esse número toda vez que você gerar a nota.

Embaixo aparece a prévia de como a descrição vai sair. Se precisar de algo diferente, clique em "Preciso de um texto diferente (escrever livre)" e use os botões pra colocar o mês, o ano ou o número da ordem no ponto certo do texto.

### O "Dia" de gerar a nota

Na lista de Tomadores, a coluna "Dia" é o dia do mês em que você costuma gerar a nota de cada tomador. Digite o número ali mesmo. Ele vira um lembrete no Calendário e a lista fica nessa ordem.

A coluna "Neste mês" mostra a situação:

- "Emitida" ou "Gerada" (verde): a nota do mês existe. Clique pra abrir.
- "Gerar hoje": chegou o dia.
- "Não gerada" (vermelho): passou do dia e ainda não foi gerada. Use o botão "Gerar" na mesma linha.
- "Dia 10" (por exemplo): ainda não chegou o dia.
- "Sem dia definido": você não informou o dia.

### Ativo, inativo ou excluído

- **Desligar "Ativo"**: use quando parou de faturar alguém por um tempo. Ele vai pro fim da lista, sem perder nada.
- **Excluir (lixeira)**: tira o tomador da sua lista e do calendário. As notas já geradas pra ele continuam guardadas na tela NFS-e.

### Tomador que retém o ISS

Alguns tomadores (geralmente empresas maiores e órgãos públicos) retêm o ISS: eles pagam o imposto direto à prefeitura e descontam do valor. No cadastro do tomador, ligue "Este tomador retém o ISS". As notas dele passam a sair com a retenção e com a alíquota do ISS guardada em Empresa (dá pra mudar numa nota só, na hora de gerar).

Cuidados:

- O MEI não tem retenção de ISS (a opção não aparece).
- A prefeitura precisa prever a retenção para esse tomador ou serviço. Se não previr, a nota volta recusada e a Ana explica o que fazer.
- A alíquota da retenção fica entre 2% e 5% (a parte do ISS na sua faixa do Simples). Confirme com o seu contador.

### Código NBS e classificação de IBS e CBS

Com a reforma tributária, o **código NBS** (Nomenclatura Brasileira de Serviços) passa a ser obrigatório na nota. Hoje a nota ainda sai sem ele, mas a conferência avisa quando o tomador está sem NBS — complete no cadastro do tomador, campo "Item da NBS".

Para a empresa do Simples (ME/EPP), o cadastro do tomador também tem a **classificação tributária (cClassTrib)** e o **código da operação (cIndOp)**, de 6 números cada. São opcionais por enquanto: a Ana guarda pra quando a nota passar a levar IBS e CBS. Quem informa é o seu contador. Nas notas de 2027 em diante, a conferência avisa quando faltar.

### Conferência do cadastro

A Ana confere o cadastro de cada tomador. Na lista aparecem os selos "a corrigir" (a nota sairia errada) e "a conferir" (algo diferente, pra você olhar). Clique no selo pra abrir a ficha: no bloco "Conferência" a Ana diz o que achou e como resolver. Enquanto houver ponto em vermelho, a Ana não gera nota pra esse tomador. Depois de corrigir e salvar, ela confere de novo.

### Corrigir o nome, o endereço ou o CEP do tomador

Abra a ficha do tomador e, em "Dados do tomador", clique em "Editar nome e endereço". O CNPJ não muda. A Ana ajuda de três jeitos:

- "Puxar os dados da Receita": preenche tudo com o que está na Receita.
- Digitar o CEP: a Ana preenche a rua, o bairro e a cidade.
- "Achar o CEP pelo endereço": com a rua e a cidade preenchidas, a Ana mostra os CEPs encontrados e você clica no certo.

No fim, clique em "Salvar dados do tomador". O que você salvar vale pras próximas notas — e pra nota recusada, se você clicar em "Corrigir e reenviar" nela.

### Cliente que está "Sem nota" (só controle)

Alguns clientes aparecem na lista com o selo "Sem nota": você só controla o que eles te pagam e não emite nota pra eles pela Ana. Isso acontece, por exemplo, quando o cliente foi criado ao lançar um recebimento no Financeiro. Esses clientes só aparecem na tela Tomadores pra quem tem o módulo Financeiro.

Pra passar a emitir nota pra um deles, clique em "Emitir nota pra este cliente". São dois passos, e nada do que você já lançou sai do lugar:

1. **Quem é**: o CNPJ dele ("Empresa do Brasil") ou, se for "Empresa de fora do Brasil", o nome, o país e o NIF.
2. **Como a nota sai**: o serviço, a descrição e pra onde enviar. A Ana deixa preenchido o que souber (pela última nota desse cliente, por exemplo) e você confere. Clique em "Salvar alterações" — só aí a Ana passa a gerar nota pra ele.

O selo "Falta configurar a nota" aparece quando a Ana já sabe quem é o cliente, mas ainda falta o passo 2. Clique em "Configurar".

Na ficha, a opção "Não emito nota pra este cliente por aqui (só controlo o que ele me paga)" liga e desliga esse modo.

### Empresa de fora do Brasil

Quem paga é uma empresa estrangeira, sem CNPJ (plataformas de fora, por exemplo)? No passo "Quem é", escolha "Empresa de fora do Brasil" e informe o nome da empresa, o país e o "NIF / número fiscal no país".

O NIF é o número que identifica a empresa no imposto do país dela — como o CNPJ é aqui. Ele vem no contrato ou no extrato de pagamento, às vezes escrito como "Tax ID", "VAT number" ou "Registration number". Copie igual está lá.

A empresa não tem esse número? Marque "Esta empresa não tem número fiscal" e escolha o motivo ("O país dela não exige esse número" ou "Ela é dispensada de ter o número"). A nota sai com o nome e o país da empresa. Só marque se ela realmente não tem o número — na dúvida, pergunte ao seu contador.

Nome em outro alfabeto (chinês, japonês, coreano, russo...): pode escrever do jeito que está no contrato. Ele sai certo no XML e no PDF da nota.

A nota pra empresa de fora sai com a identificação fiscal estrangeira e o país. Na primeira vez, confirme com seu contador.

---

## 3. Gerar, assinar, enviar à prefeitura e ao tomador

### As etapas de uma nota

Toda nota passa por quatro etapas:

1. **Gerar**: a Ana monta a nota com os dados do tomador, o valor e a descrição.
2. **Assinar**: a nota é assinada com o certificado digital da empresa.
3. **Enviar à prefeitura**: a nota vai pra Receita e é autorizada (ou recusada). Só depois de autorizada ela é uma nota fiscal de verdade.
4. **Entregar ao tomador**: a nota chega ao cliente, do jeito que ele recebe (e-mail, WhatsApp, portal...).

### Gerar uma nota

Na tela "NFS-e", clique em "Nova emissão". Escolha o tomador, confira a data de competência e informe o valor. A alíquota do Simples já vem preenchida com a referência de "Empresa › Dados da empresa (Alíquota)" — confira antes de gerar.

Você também pode clicar em "Gerar" na linha do tomador, na tela Tomadores.

### Fazer tudo de uma vez

Na janela "Nova emissão" existe o bloco "Ao gerar, a Ana também", com três opções:

- "Assina com o certificado"
- "Envia à prefeitura"
- "Entrega ao tomador, do jeito marcado no cadastro dele (e-mail, baixar o PDF, WhatsApp, portal...)"

Com as três marcadas, o botão vira "Gerar e fazer tudo" e a Ana faz a sequência inteira. Sua escolha fica guardada pra próxima nota. Se um passo falhar, a Ana para ali e mostra o motivo; o botão "Ver a nota" leva pra página da nota, onde dá pra continuar.

Sem nada marcado, o botão é "Gerar rascunho" e você faz os outros passos depois.

### A conferência antes de gerar

Assim que você digita o valor, a Ana confere os dados do tomador, da empresa e da nota:

- **Vermelho ("Precisa corrigir")**: a nota sairia errada. A Ana não gera enquanto não for corrigido, e mostra como resolver e o atalho pra tela certa.
- **Amarelo ("Confira")**: é só pra você olhar. Marque "Conferi e está certo, pode gerar" pra continuar.

A mesma conferência aparece na página da nota enquanto ela não foi autorizada. Com ponto em vermelho, a prefeitura tende a recusar a nota: corrija antes de enviar.

### Já existe uma nota desse tomador no mês

Ao escolher o tomador e a data, a Ana avisa se já existe nota dele naquele mês:

- Se a nota que existe **ainda não foi enviada**: você pode continuar por ela ("Abrir a nota que já existe") ou marcar "Apagar a que não foi enviada e gerar esta no lugar".
- Se a nota que existe **já foi emitida**: pra gerar outra, escolha uma data de competência de outro mês.

### A lista de notas (tela "NFS-e")

A tela mostra todas as notas, com filtros de ano, mês e tomador e uma busca. Cada linha tem três selos:

- **Assinatura**: "A assinar" (clique pra assinar) ou "Assinada ✓".
- **Prefeitura**: "A enviar" (clique pra enviar), "Aguardando", "Autorizada ✓" ou "Recusada".
- **Tomador**: "A enviar", "Enviada ✓", "Falhou", "Enviar no portal" ou "Não precisa".

Clique num selo pra fazer aquele passo. Clique no nome do tomador pra abrir a página da nota.

O cartão "Ainda não autorizadas" mostra quantas notas ainda não foram autorizadas pela prefeitura. Clique nele pra ver só elas.

### Fazer um passo em várias notas

Marque as caixinhas das notas na lista. Aparecem os botões "Fazer tudo o que falta" (em cada nota: assina, envia à prefeitura e manda por e-mail — só o que ainda falta), "Assinar", "Enviar à prefeitura", "Enviar ao tomador por e-mail" e "Baixar arquivos (.zip)".

A Ana mostra quantas notas estão prontas pra aquela ação e pede uma confirmação. O trabalho roda em segundo plano, uma nota por vez, e você acompanha no canto da tela. Só dá pra rodar uma ação em lote por vez.

### A página da nota

Ao abrir uma nota você vê os dados dela, a "Conferência", as "Ações" e o "Envio desta nota". No fim da página, o quadro "Próximo passo" diz o que falta nessa nota e tem o botão pra fazer — e, quando a nota termina, leva pra próxima nota que está esperando por você ("Ir pra próxima nota").

Em "Ações" ficam: "Assinar", "Submeter à prefeitura", "Baixar PDF", "Baixar XML", "Mensagem pronta", "Apagar nota" e "Cancelar nota", conforme a etapa da nota.

Enviar à prefeitura pede uma confirmação ("Confirmar envio"), porque o envio em si não dá pra desfazer — só cancelar a nota depois, se ela for autorizada.

### Baixar o PDF e o XML

Na lista de notas, a coluna "Arquivos" tem os botões de baixar o PDF e o XML. O PDF sai depois que a prefeitura autoriza a nota.

Pra baixar várias de uma vez, marque as notas e clique em "Baixar arquivos (.zip)". Dá pra baixar até 250 notas por .zip; pra baixar o mês inteiro, filtre por mês e selecione todas.

### Apagar uma nota

Enquanto a nota **não foi autorizada** pela prefeitura, dá pra apagar: na página da nota, clique em "Apagar nota". Ela some da lista.

### Cancelar uma nota

Depois de **autorizada**, a nota só pode ser cancelada: na página da nota, clique em "Cancelar nota", escolha o motivo ("Erro na emissão", "Serviço não prestado" ou "Outros") e escreva a justificativa (entre 15 e 255 caracteres). O cancelamento é enviado à Receita e, se aceito, não pode ser desfeito. Use só quando a nota realmente não deveria ter sido emitida.

### Tomador que manda ordem de pagamento em PDF

Pra alguns tomadores que mandam uma ordem de pagamento em PDF (a Ana reconhece pelo cadastro do tomador), a janela "Nova emissão" mostra o botão "Enviar o PDF da ordem": a Ana lê o arquivo e preenche o número da ordem, o valor e a competência. Confira a data de competência antes de gerar. Se o botão não aparecer pro seu tomador, é só digitar o valor.

### Calendário

A tela "Calendário" mostra os dias de gerar cada nota, o lembrete de revisar a alíquota e os eventos que você criar. Quem tem o Financeiro também vê as previsões e confirmações de recebimento.

- Clique num dia (ou em "Novo evento") pra criar um lembrete.
- Clique num aviso pra ajustar: em "Só esta vez" você pode "Mover" a data ou "Ocultar este alerta" sem mexer nos outros meses; em "Mudar a regra" você muda o dia de todos os meses e clica em "Salvar regra".

---

## 4. Notas recusadas e CEP

### A prefeitura recusou a nota. E agora?

Quando a prefeitura recusa, a nota fica com o selo "Recusada" e a Ana mostra **por que foi recusada**. Nada se perde: a nota continua lá, esperando a correção.

Há dois casos:

- **A Ana sabe consertar sozinha.** Aparece o botão "Corrigir e reenviar". Ela corrige, assina de novo e manda à prefeitura. O número da nota não muda.
- **Precisa de você.** Corrija o que a prefeitura apontou (no cadastro do tomador ou gerando a nota de novo) e use "Tentar submeter de novo" na página da nota (ou "Tentar de novo" no selo).

Embaixo da mensagem da prefeitura pode aparecer **"Em palavras simples"**: uma explicação curta do que aconteceu e o que corrigir, escrita por inteligência artificial. A mensagem original da prefeitura continua visível logo acima — se as duas parecerem diferentes, vale a da prefeitura. A explicação não muda a nota nem reenvia nada.

### Recusa por causa do CEP

É o erro que mais faz a prefeitura recusar nota: o CEP do tomador não bate com a cidade ou com o endereço.

Clique em "Corrigir e reenviar". A Ana usa o endereço que está no cadastro do tomador — ou, se ele não mudou, procura o CEP certo pelo endereço —, assina de novo e envia à prefeitura. O número da nota não muda.

Se você souber o endereço certo, corrija antes no cadastro do tomador (link "Corrigir o endereço antes"): a nota vai com o endereço novo. Veja "Corrigir o nome, o endereço ou o CEP do tomador", na parte de Tomadores.

### Recusa por causa da hora da nota

Às vezes a hora da nota fica à frente do relógio da Receita e ela recusa. Clique em "Corrigir e reenviar": a Ana acerta a hora, assina de novo e envia. O número e os dados da nota não mudam.

### Onde vejo as notas recusadas

- Na tela "NFS-e", o cartão "Ainda não autorizadas" avisa quantas foram recusadas. Clique nele pra ver só as notas pendentes; clique no nome pra abrir a nota e corrigir.
- Na "Visão geral", os cards "Precisa da sua atenção" e "Próximos passos" também mostram o que está pendente.
- Em "Notas em lote", o passo a passo lista as notas recusadas com o motivo e o link "abrir e corrigir".

### Como evitar recusa

Antes de enviar, olhe a "Conferência" da nota e do tomador. Ponto em vermelho quer dizer que a prefeitura tende a recusar. A Ana sempre diz como resolver.

---

## 5. Notas em lote e relatório da Shopee

### Pra que serve a tela "Notas em lote"

É pra quem emite muitas notas de uma vez a partir de um relatório — como as comissões da Shopee, em que sai uma nota pra cada vendedor que te pagou comissão no mês. Essas notas ficam nessa tela, separadas da lista de NFS-e e da Visão geral.

O botão "Enviar relatório da Shopee" aparece quando a Shopee está cadastrada como tomador.

### Enviar o relatório da Shopee

1. No painel de afiliados da Shopee, baixe o **relatório mensal de comissões** (um arquivo .csv cujo nome começa com "MonthlyReport").
2. Em "Notas em lote", clique em "Enviar relatório da Shopee", escolha (ou arraste) o arquivo e clique em "Ler relatório".
3. A Ana mostra um resumo por mês: quantos vendedores e quanto soma. Confira o total com o painel da Shopee.
4. Ajuste, se quiser:
   - "Não gerar notas abaixo de": deixa de fora as comissões pequenas (0 = gera todas).
   - "Alíquota do Simples (%)".
   - A data de competência que vai em cada nota.
   - "Incluir vendedor(es) de fora do Brasil" (aparece quando o relatório tem vendedores estrangeiros). Se for a primeira vez, confirme com seu contador.
5. Em "Depois de gerar, a Ana também", marque o que ela deve fazer na sequência: assinar todas, enviar à prefeitura e mandar cada nota pro e-mail do vendedor (o que veio no relatório).
6. Clique em "Gerar ... notas e fazer tudo".

Os vendedores não ficam salvos como tomadores. Notas que já tinham sido geradas antes ficam como estão — a Ana não gera de novo.

A nota da própria Shopee (com o valor que a Shopee informa pra ela) sai pela "Nova emissão", escolhendo "Nota da Shopee".

### Preciso ficar com a página aberta?

Não. A sequência roda em segundo plano: depois do seu OK você pode fechar a página. Quando acaba, a Ana deixa um relatório em "Notas em lote" (em "Últimos processamentos", botão "Ver relatório") e manda o relatório por e-mail.

### O passo a passo do mês

No topo de "Notas em lote" fica o "Passo a passo" do mês, com quatro etapas: "Assinar", "Prefeitura autorizar", "Enviar aos vendedores" e "Guardar os arquivos". Ele mostra em que etapa o mês está e **um botão só**: "Continuar de onde parou". Um clique e a Ana faz em sequência tudo o que falta.

Quando termina, aparece "Tudo certo com este mês: sua situação está regular".

### O lote parou ou teve falhas

- **"Interrompido"**: o servidor reiniciou no meio. Clique em "Retomar" pra continuar de onde parou.
- **"Concluído com falhas"**: use "Refazer falhas" (ou, no relatório, "Tentar de novo as ... que falharam"). No relatório, "Notas que precisam de atenção" lista cada nota com o que aconteceu, e "Baixar a lista (.csv)" baixa essa lista.
- **Recusa por CEP**: no processo completo a Ana procura o CEP certo pelo endereço e manda de novo, sozinha.

### "Esperando o limite de e-mails"

O serviço de e-mail tem um limite de envios. Se o lote bater nesse limite, ele fica "Esperando o limite de e-mails" — **não é falha**. A Ana continua sozinha assim que o limite voltar; você não precisa fazer nada. As notas já estão autorizadas.

### Vendedores sem e-mail

Se o vendedor não informou e-mail no relatório, a nota dele não tem como ser enviada. Isso não é pendência sua, e a situação do mês fica regular do mesmo jeito. Se o vendedor te passar o e-mail, abra a nota e envie por lá.

### Guardar os arquivos do mês

Esta etapa é **opcional**. Quem não vai baixar nem compartilhar agora clica em "Marcar como concluído" (logo abaixo dos botões) e a etapa fica feita; "Reabrir" desfaz. Baixar, mandar por e-mail ou guardar no Drive também marca sozinho.

Depois que as notas são autorizadas, o bloco "Arquivos do mês" deixa escolher o que vai no pacote ("PDF e XML", "Só PDF" ou "Só XML") e oferece:

- "Baixar (.zip)": baixa o pacote no seu computador.
- "Mandar por e-mail": manda um e-mail só, com o .zip em anexo, pra quem você indicar (o contador, você).
- "Guardar no Google Drive": guarda os arquivos na pasta "Agente Ana" do seu Google Drive. Na primeira vez, clique em "Conectar o Google Drive" e aceite o acesso que o Google pedir. Pra desligar depois, use "desconectar". (Esse botão só aparece quando a integração com o Google Drive está disponível.)

---

## 6. Envio da nota: e-mail, download, WhatsApp, portal e Google Drive

### Como cada tomador recebe a nota

Na ficha do tomador, no bloco "Envio da nota", você marca "Como este tomador recebe a nota". Pode marcar mais de uma:

- **"E-mail"**: a Ana manda a nota com o PDF e o XML em anexo. Informe o "E-mail do tomador" (mais de um? separe com vírgula).
- **"WhatsApp"**: a Ana abre a conversa com a mensagem e o link da nota — você só aperta enviar.
- **"Portal do tomador"**: você sobe o PDF/XML no sistema dele e marca como enviada. Dá pra guardar o "Link do portal do tomador".
- **"Baixar o PDF ao finalizar"**: quando a prefeitura autorizar, o PDF já baixa no seu computador.

Nada marcado quer dizer que esse tomador **não precisa receber a nota**: ela não aparece como pendente de envio.

No "processo completo" a Ana segue o que estiver marcado ali. Em cada nota ainda dá pra mudar na hora.

Só dá pra enviar ao tomador depois que a prefeitura autorizar a nota.

### Enviar uma nota

Clique no selo da coluna "Tomador" (na lista) ou vá em "Envio desta nota" (na página da nota). O painel tem quatro abas:

- **"E-mail"**: confira "Para", "Cópia", "Assunto" e "Mensagem" (já vêm preenchidos com os dados da nota — edite à vontade) e clique em "Enviar e-mail".
- **"WhatsApp"**: confira o número e a mensagem e clique em "Abrir WhatsApp". A mensagem vai com o link pra baixar a nota. Ao abrir, a nota fica marcada como enviada. Sem número, você escolhe o contato quando o WhatsApp abrir.
- **"Portal"**: use "Baixar PDF" e "Baixar XML", envie no portal do tomador ("Abrir portal", se o link estiver cadastrado) e clique em "Marcar como enviada". Se entregou de outro jeito, use "Enviei de outro jeito".
- **"Contador/geral"**: manda a nota pros seus e-mails gerais (contador, o seu). **Não conta como enviada ao tomador.**

A opção "Lembrar para este tomador" guarda o que você usou: da próxima vez já vem assim.

### Mudar o texto do e-mail

- **Pra todos os tomadores**: "Empresa", aba "E-mails", bloco "E-mail para o tomador". Mude o assunto, a mensagem e os anexos e clique em "Salvar modelo". "Voltar ao texto padrão" desfaz.
- **Pra um tomador só**: na ficha dele, em "Envio da nota", abra "Mudar o texto do e-mail deste tomador".
- **Só nesta nota**: edite direto no painel de envio, antes de clicar em "Enviar e-mail".

### Mandar a nota pro contador ou pra outras pessoas

- **Cópia em todo e-mail de nota**: "Empresa" › "E-mails" › "Sempre mandar cópia para".
- **E-mails gerais**: em "Empresa" › "E-mails" › "E-mails gerais" você deixa cadastrados os e-mails do contador (ou o seu) e um texto próprio pra eles. Pra mandar uma nota pra esses e-mails, abra a nota e use a aba "Contador/geral" do envio — esse envio é feito nota por nota, por você.
- **Outras pessoas de um tomador específico**: na ficha do tomador, em "Outras pessoas que recebem esta nota", clique em "Adicionar pessoa". Cada um recebe um e-mail separado, e dá pra escrever um texto diferente pra cada um.

### Enviar várias notas por e-mail de uma vez

- Marque as notas na lista e clique em "Enviar ao tomador por e-mail". Cada nota vai pro e-mail cadastrado no tomador dela (só de quem recebe por e-mail).
- Ou filtre um tomador e um mês e clique em "Enviar todas por e-mail".

A Ana não manda de novo uma nota que já foi entregue. Pra mandar de novo, marque "Incluir as já enviadas (reenviar)" na confirmação.

### O envio falhou

O selo da coluna "Tomador" fica "Falhou". Clique nele pra tentar de novo — dá pra trocar pra WhatsApp na hora. Com um tomador e um mês filtrados, o botão "Reenviar falhas" manda de novo as que falharam (e as que ainda não tinham sido enviadas).

Na página da nota, o "Histórico de envios" mostra cada envio, pra quem foi e se deu certo.

### Link da nota

Na página da nota, "Copiar link da nota" copia um endereço que baixa a nota sem precisar de login. É esse link que vai na mensagem do WhatsApp e no corpo do e-mail. Ele vale por 180 dias.

### "Mensagem pronta"

Na página da nota, o botão "Mensagem pronta" mostra um texto pronto sobre a nota, com o botão "Copiar", pra você colar onde quiser.

### Baixar muitas notas ou guardar no Google Drive

- Na tela NFS-e: marque as notas e use "Baixar arquivos (.zip)".
- Em Notas em lote: use o bloco "Arquivos do mês" ("Baixar (.zip)", "Mandar por e-mail" ou "Guardar no Google Drive"). Veja a parte 5.
- Em qualquer nota autorizada: abra a nota e use "Guardar no Google Drive" (aparece quando a integração com o Google Drive está disponível). O PDF e o XML vão pra pasta Agente Ana › nome do tomador › mês.
- Automático por tomador: na ficha do tomador, em "Como este tomador recebe a nota", marque "Guardar no meu Google Drive". Daí em diante, toda nota dele é guardada no seu Drive assim que a prefeitura autoriza. A Ana só enxerga a pasta que ela mesma cria no seu Drive.

---

## 7. Financeiro, Mês a mês e Conciliação

### A tela "Financeiro" (Painel)

Mostra o que entrou, o que saiu e o que sobrou, mês a mês. Você escolhe o ano e, se quiser, um mês. Os cards da tela:

- **"Resultado do ano"** (ou do mês): recebido, despesas, lucro, margem, retiradas e saldo a distribuir. Quem também tem o módulo de Notas vê o faturado e o que falta receber.
- **"Entrou × saiu por mês"**, **"Para onde vai o dinheiro"** e **"Recebido por cliente"**: gráficos.
- **"Contas do mês"** e **"Rotina de fechamento"**.
- **"A receber"**: notas emitidas sem pagamento registrado (só com o módulo de Notas).
- **"Recebimentos sem nota"** (só com o módulo de Notas, quando houver).
- **"Recebimentos e despesas"**: as duas listas.
- **"Recebimentos x despesas, mês a mês"**.

### Registrar um recebimento

Clique em "Recebimento". Escolha de quem veio (dá pra criar um cliente novo ali mesmo, só com o nome), a "Nota que esse dinheiro paga" (quando houver), o valor e a data do recebimento.

Se o dinheiro caiu antes da nota, escolha "Nenhuma nota (dinheiro que caiu antes da nota)". Quem tem o módulo de Notas pode gerar a nota desse recebimento depois.

### Lançar uma despesa ou uma retirada

Clique em "Despesa". Escolha o tipo: despesa ou "Retirada / distribuição de lucros". Informe a categoria, o valor, o mês e, se quiser, a conta de onde saiu o dinheiro e o vencimento.

- Com vencimento e sem estar paga, a despesa fica "a pagar" nas contas do mês até você ticar.
- **Retirada não entra nas despesas**: ela sai do lucro que sobrou (o "saldo a distribuir").

Na lista "Despesas e retiradas", o lápis edita e a lixeira apaga.

### Contas do mês e contas recorrentes

Em "Contas do mês" você tica o que já foi pago. Pra não ter que lançar todo mês as mesmas contas (pró-labore, Simples, cartão, ferramentas), clique em "Contas recorrentes" e cadastre cada uma com nome, valor e dia do vencimento. Cada conta recorrente aparece todo mês em "Contas do mês", pra você ticar quando pagar.

- Valor vazio = a conta varia todo mês. Na hora de ticar, a Ana pergunta "Quanto foi pago?".
- "Pagamento já agendado até": a conta já aparece ticada até o mês que você informar.

### Rotina de fechamento

É a lista do que você confere todo fim de mês (conferir extratos, investimentos, baixar uma nota de um fornecedor...). Clique em "Montar rotina" (ou "Itens da rotina") pra criar os itens. Todo mês eles aparecem pra você ticar. Com tudo ticado, aparece "mês fechado ✓". Dá pra arrastar os itens pra mudar a ordem.

### Importar o extrato do banco

Clique em "Importar extrato" e envie o extrato em **PDF**, **OFX** ou **CSV**. Dica: no app do banco, a opção "exportar OFX" é a que funciona melhor.

A Ana lê as transações e separa as entradas das saídas. Você confere cada uma antes de gravar: de qual cliente é cada entrada (e a nota que ela paga, quando houver) e a categoria de cada saída. Dá pra criar cliente e categoria ali mesmo.

- A classificação já vem sugerida. Suas escolhas ficam lembradas: no próximo extrato, o mesmo pagador já vem classificado ("como da última vez").
- O que você não classificar na hora fica guardado pra resolver depois, na Conciliação.
- O que já tinha sido lançado numa importação anterior vem marcado como "já lançado antes".

Se o PDF for uma imagem ou foto do extrato, a Ana não consegue ler: baixe o extrato de novo no app do banco, de preferência em OFX.

### A tela "Conciliação"

São duas conferências, mais o fechamento:

1. **"As notas foram pagas?"** (a mais importante, só com o módulo de Notas): a Ana confere cada nota emitida com o dinheiro que entrou.
2. **"O extrato do banco está todo classificado?"**: cada linha do banco vira um recebimento ou uma despesa.

O **"Fechamento do mês"** junta as duas: o mês fecha quando as notas dele estão pagas e o extrato dele está todo classificado. Cada mês aparece como "Fechado", "Aguardando pagamento", "Falta conferir" ou "Nada lançado".

O número ao lado de "Conciliação", no menu, é a soma do que falta conferir nas duas partes.

### "As notas foram pagas?" — dar baixa

No topo, o resumo do período: "Faturado", "Recebido", "Em aberto" e "Atrasado". Embaixo, cada tomador com as notas dele. Os filtros ("Precisam de você", "Em aberto", "Atrasadas", "Com diferença", "Pagas") ajudam a achar.

Pra dar baixa numa nota, abra a linha dela e:

- "Registrar o recebimento": informe o valor recebido e a data em que caiu e clique em "Dar baixa". Se cair um valor diferente do da nota, a Ana mostra a diferença.
- "Ligar a um lançamento do extrato": escolha a entrada do extrato que pagou essa nota e clique em "Ligar e dar baixa".

Quando a Ana acha no extrato uma entrada que parece o pagamento de uma nota, ela pergunta se é isso mesmo — você confirma ou clica em "Não é esse".

Pra voltar atrás, use "Desfazer a baixa": a nota volta a ficar em aberto.

Também dá pra dar baixa pelo card "A receber" da tela Financeiro, clicando no selo de pagamento ("Dar baixa").

### Pagamento com valor diferente da nota

A nota aparece no filtro "Com diferença". Se a diferença é esperada (imposto retido pelo cliente, por exemplo), clique em "A diferença está certa (ex.: imposto retido)" e a Ana para de avisar.

### Quando uma nota fica "Atrasada"

A Ana usa o prazo de pagamento de cada cliente: o campo "Dias até o pagamento cair", no bloco "Calendário" da ficha do tomador (contados a partir da data de emissão da nota). Se o cliente não tem prazo cadastrado, a Ana só avisa de atraso depois de 60 dias.

### Dinheiro que entrou sem nota

Recebimentos que não estão ligados a nenhuma nota — comum em quem paga antes da nota. Aparecem em "Recebimentos sem nota". Pra cada um você pode: "Gerar nota" do valor que caiu, ligar a uma nota em aberto que já existe, ou ignorar o aviso se não precisa de nota.

### "O extrato do banco está todo classificado?"

À esquerda fica o que veio do banco e ainda não foi classificado, em duas abas: "Receitas" e "Despesas". À direita, o que está em aberto no sistema (notas a receber ou contas a pagar).

- Escolha um lançamento à esquerda e, à direita, a nota ou a conta que ele paga. Clique em "Dar baixa na nota escolhida" ou "Marcar a conta escolhida como paga".
- Não é de nenhuma nota nem conta prevista? Escolha o cliente (ou a categoria) e o mês e clique em "Lançar".
- "Na verdade é despesa" / "Na verdade é receita": troca o lançamento de lado.
- "Ignorar (não é receita nem despesa)": pra transferência entre contas suas, por exemplo. Os ignorados ficam numa lista e dá pra trazer de volta ("voltar pra lista").
- Quando há entradas com nota em aberto do mesmo valor, a Ana oferece o botão pra conciliar todas de uma vez.

### Quanto um cliente me pagou, mês a mês? Quanto gastei com uma coisa?

No card "Resultado do ano", a tabela "Mês a mês" mostra cada linha de dinheiro (recebido, despesas, retiradas) por mês. Clique na seta de uma linha pra abrir o detalhe: quem pagou (por cliente) ou com o que você gastou (por categoria). Use a busca "Buscar cliente ou gasto…" pra achar direto. Clicar no nome de um mês filtra a tela inteira por aquele mês.

### Clientes (pra quem tem só o Financeiro)

A tela "Clientes" mostra de quem o dinheiro entra e quanto cada um já pagou no ano. Dá pra adicionar um cliente (só o nome), renomear e desativar. Quem tem os dois módulos usa a tela Tomadores: são os mesmos clientes.

---

## 8. Anotações e Visão geral

### O que aparece na "Visão geral"

É o resumo do mês da empresa, com um card pra cada assunto dos módulos que você tem ligados. As setas ao lado do nome do mês trocam o mês.

Com o módulo de Notas: "Notas do mês" (tomadores ativos, emitidas, aguardando emissão, faturado no mês), "Emissões deste mês", "Precisa da sua atenção", "Próximos passos", "Faturamento por mês" e "Quem mais te paga".

Com o módulo Financeiro: "Dinheiro do mês" (recebido, despesas, lucro), "Entrou × saiu por mês", "Extrato sem classificar" (quando houver), "Contas do mês" e "Rotina de fechamento".

E os "Atalhos rápidos" pras ações mais usadas.

### "Próximos passos"

Mostra primeiro o que dá pra resolver agora (notas a gerar, assinar, enviar...) e depois o que vem na agenda dos próximos 30 dias. Clique numa linha pra ir direto resolver.

Se um aviso é um atraso consciente (por exemplo, uma nota que só sai depois do pagamento), passe o mouse na linha e clique no ícone do olho riscado, "Ignorar este aviso". Ele some dali e também de "Precisa da sua atenção".

### Arrumar a tela do seu jeito

Na Visão geral e no Financeiro, clique em "Editar disposição". Cada card ganha uma barra pra:

- arrastar e mudar de lugar;
- trocar a largura ("Meia largura" ou "Alargar");
- recolher (deixar só o título);
- esconder (o olho riscado tira o card da tela).

Os cards escondidos ficam em "Blocos escondidos", no fim da página: toque num deles pra voltar. "Voltar ao padrão" desfaz tudo. Quando terminar, clique em "Concluir". A arrumação fica salva na sua conta.

### Anotações

Na Visão geral e no Financeiro, clique em "Nova anotação" pra deixar registrado o que quiser. Escolha o formato:

- **"Texto"**: escreva livremente, como num bloco de notas.
- **"Lista"**: itens pra ir marcando conforme você faz.
- **"Tabela"**: controle com colunas, datas e valores somados no fim.

Cada anotação vira um card. Tudo salva sozinho. Dá pra mudar o nome, trocar o formato depois e apagar. Quem tem os dois módulos escolhe em "Aparece em" se a anotação fica só numa tela ou nas duas.

---

## 9. Assinatura, planos e módulos

### Período de teste

A conta nova começa num período de teste gratuito de 14 dias, sem cartão. Em "Minha conta", aba "Assinatura", aparece quantos dias restam (e, nos últimos 5 dias, um aviso no topo da tela).

### Quando o teste acaba

Nada é apagado. A empresa fica **só pra consulta**: você continua entrando, vendo e baixando notas, tomadores e lançamentos, mas não consegue gerar ou enviar notas nem fazer lançamentos novos. No topo aparece a faixa "O teste grátis desta empresa terminou" com o botão "Assinar agora". Assinando um plano, tudo volta na hora. O mesmo vale se a assinatura for cancelada.

Se o pagamento de um mês falhar, a conta não trava na hora: o cartão é cobrado de novo nos dias seguintes. Atualize a forma de pagamento em "Assinatura" pra não perder o acesso.

### Planos

Os planos vão pelo número de notas autorizadas no mês. O limite é por CNPJ.

| Plano | Valor por mês | Notas por mês | Financeiro |
|---|---|---|---|
| Básico | R$ 49,90 | até 30 | pode somar por R$ 39,90 |
| Empreendedor | R$ 99,90 | até 150 | pode somar por R$ 39,90 |
| Empresa | R$ 129,90 | até 300 | incluído |
| Avançado | R$ 149,00 | até 500 | incluído |
| Ilimitado | R$ 299,00 | sem limite | incluído |
| Financeiro | R$ 39,90 | não emite notas | é o próprio plano |

"Personalizado": pra várias empresas ou volume muito alto, clique em "Fale com a nossa equipe" na aba "Assinatura".

Pra assinar: "Minha conta" › "Assinatura" › "Assinar este" no plano escolhido. Pra somar o Financeiro ao Básico ou ao Empreendedor, marque "Somar o Financeiro" antes de escolher o plano.

### Limite de notas

- **O que conta:** só nota autorizada pela prefeitura no mês. Cancelada, recusada, de teste (homologação) e importada do Emissor Nacional não contam. O contador zera no dia 1º.
- **Onde ver:** "Minha conta" › "Assinatura" mostra "Notas deste mês", com a barra de uso.
- **Aos 80%:** a Ana avisa no topo da tela e sugere o plano de cima.
- **No limite:** a emissão para até você subir de plano — ou marcar "Continuar emitindo depois do limite por R$ 0,80 cada nota" (só pra quem já assina). As notas a mais entram na fatura seguinte; dá pra desmarcar quando quiser. As notas já prontas ficam esperando, nada se perde.
- **No teste grátis:** o limite é de 150 notas, com o Financeiro liberado. No teste não há nota excedente: pra passar do limite, assine um plano.
- **Lote:** antes de começar um lote que não cabe no limite, a Ana avisa quantas notas cabem.

### Mudar de plano, forma de pagamento e cancelamento

- **Mudar de plano**: em "Minha conta" › "Assinatura", clique em "Mudar pra este" no plano novo e confirme. A diferença de valor entra proporcional na próxima fatura. Nada é apagado.
- **Trocar o cartão, ver faturas ou cancelar**: clique em "Forma de pagamento, faturas e cancelamento".

Se você sair de um módulo, os dados dele ficam guardados e voltam quando contratar de novo.

A situação da assinatura aparece como "Período de teste", "Assinatura ativa", "Pagamento pendente", "Assinatura cancelada" ou "Conta cortesia". Em "Pagamento pendente", atualize a forma de pagamento pra evitar interrupção.

### Ligar e desligar módulos

Em "Empresa", aba "Mais opções", ficam os módulos da empresa ("Notas" e "Financeiro"). Desligar um módulo só esconde as telas dele: nada é apagado, e tudo volta quando ele for ligado de novo. Pelo menos um módulo precisa ficar ligado.

Com plano pago, os módulos vêm do plano que você assina: pra ligar ou desligar um módulo, mude o plano em "Minha conta" › "Assinatura".

### Indique e ganhe

Em "Minha conta", aba "Indique e ganhe", fica o seu link de indicação ("Copiar link" ou "Enviar no WhatsApp"). Cada pessoa que assinar pelo seu link vale 10% de desconto na sua mensalidade, enquanto ela continuar assinante. Com 10 indicados ativos, você não paga nada. A tela mostra o seu desconto e quem veio pelo seu link.

---

## 10. Conta, segurança e suporte

### Seu nome e seu e-mail

Em "Minha conta", aba "Perfil", você muda o nome pelo qual a Ana te chama. O e-mail de acesso não muda por ali — se precisar trocar, fale com o suporte.

### Senha

Em "Minha conta", aba "Acesso e segurança", clique em "Trocar senha". Você informa a senha atual e a nova (pelo menos 8 caracteres). Trocar a senha desconecta os outros aparelhos em que você estiver logado.

Se a sua conta não usa senha, você entra com o Google ou com um código enviado por e-mail.

**Esqueceu a senha?** Na tela de login, use "Entrar com código por e-mail": a Ana manda um código de 6 dígitos pro seu e-mail, válido por 10 minutos, e você entra sem a senha.

### Dispositivos conectados

Em "Acesso e segurança", o bloco "Dispositivos conectados" mostra onde a sua conta está aberta agora. Não reconhece algum? Clique em "Desconectar" e troque a senha. "Sair de todos os outros" desconecta todos de uma vez, menos o aparelho que você está usando.

### Aparência e dicas

Em "Minha conta", aba "Preferências", você escolhe o tema "Claro" ou "Escuro" (vale pro navegador que você está usando) e liga ou desliga as dicas da Ana.

### Segurança dos seus dados

Cada conta só enxerga os próprios dados. Senhas e certificados ficam guardados de forma criptografada. Os detalhes estão na Política de privacidade.

### Limpar dados de teste

Em "Empresa", aba "Mais opções", o bloco "Limpar dados" apaga dados da empresa por categoria (tomadores, notas, calendário, recebimentos, despesas) — útil pra tirar dados de teste. Não tem como desfazer; por isso a Ana pede pra digitar LIMPAR.

- Notas emitidas de verdade não podem ser apagadas: só saem as que nunca foram enviadas à Receita.
- Tomadores com notas já emitidas ficam arquivados (as notas continuam guardadas).

### Excluir a empresa ou a conta

- **"Excluir esta empresa"** ("Empresa" › "Mais opções"): apaga a empresa e todo o histórico dela na Ana. Se for a única empresa do seu login, a conta é excluída junto. A Ana pede o CNPJ pra confirmar.
- **"Excluir minha conta"** ("Minha conta" › "Perfil"): apaga o seu login e as empresas em que você é o único usuário. A Ana pede pra digitar EXCLUIR. Se tiver assinatura ativa, cancele antes em "Assinatura" pra não ser cobrado de novo.

Nos dois casos não tem como desfazer, e as notas já emitidas continuam válidas na Receita.

### Dar acesso ao contador

Em "Empresa" › "Contador" você convida o seu contador pelo e-mail dele e marca o que ele pode fazer:

- **Ver as notas e o financeiro** — sempre liberado.
- **Gerar e cancelar notas** — criar, assinar, enviar à prefeitura e cancelar, uma a uma ou em lote.
- **Enviar notas aos clientes** — e-mail, WhatsApp, Google Drive e marcar como enviada.
- **Cadastrar e editar tomadores**.
- **Lançar e conciliar no Financeiro** — recebimentos, despesas, extrato, conciliação.
- **Alterar dados da empresa** — cadastro, alíquota, certificado A1 e preferências.
- **Documentos da empresa** — ver, enviar e substituir os documentos fixos (contrato social, documentos dos sócios...). É a única coisa que o contador **não** vê sem permissão, porque tem documento pessoal de sócio. Começa desligada, inclusive para quem já era seu contador.

Clique em "Enviar convite". O contador entra com o login dele (você não passa a sua senha). Dá pra mudar as permissões a qualquer momento (vale na hora) ou tirar o acesso pela lixeira. A lista "O que o contador fez" mostra as últimas ações dele. Ficam sempre só com o dono: a assinatura, convidar ou tirar pessoas, ligar e desligar módulos e apagar a empresa ou os dados.

### Para contadores: "Painel do contador"

O contador cria a própria conta em "Criar conta", na opção "Sou contador(a)": é grátis, não pede CNPJ e não tem período de teste nem assinatura — quem assina é o cliente. O e-mail tem que ser o mesmo que o cliente convidou. Essa conta mostra só "Painel do contador", "Minha conta" e "Ajuda"; pra emitir as próprias notas, o contador adiciona a empresa dele pelo seletor de empresas ("Adicionar empresa"). O convite aparece em "Painel do contador" (no menu): "Aceitar" e depois "Abrir empresa". Dentro da empresa do cliente aparece uma faixa azul no topo dizendo o que ele pode fazer ali. As empresas dos clientes ficam também no seletor de empresas, no topo do menu, no grupo "Painel do contador". Se o contador tentar algo que o cliente não liberou, a Ana avisa qual permissão falta. "Deixar de atender" tira a empresa da lista.

Cada empresa da lista mostra "O que tem pra fazer": notas pra gerar, assinar, enviar, recusadas pela prefeitura e o que falta conferir na conciliação. Clicar numa pendência abre a empresa já na tela certa. "Só com pendência" esconde quem está em dia.

**Bonificação do contador:** ele recebe 10% de cada mensalidade paga pelos clientes que atende, enquanto atender a empresa. O card "Sua bonificação" mostra quantos clientes estão pagando e quanto há a receber; "Ver extrato" abre o detalhe mês a mês. O repasse é feito pela equipe da Agente Ana.

### Para contadores: o Painel do contador

No menu, "Painel do contador" mostra as empresas dos clientes sem precisar entrar em nenhuma. No topo, uma caixa de busca troca de empresa e uma faixa mostra os números da carteira (empresas, notas e faturado no mês, coisas urgentes). São três abas:

- **"Hoje"**: uma fila só com o que fazer, do mais urgente pro menos — certificado digital faltando, vencido ou vencendo (aviso a 30 dias, urgente a 15), notas recusadas, faturamento chegando a 80% do limite do MEI (R$ 81 mil no ano) ou do Simples (R$ 4,8 milhões no ano), recebimento sem nota, notas pra gerar, assinar ou enviar e conciliação pendente. "Resolver" abre a empresa já na tela certa.
- **"Fechamento do mês"**: as empresas em quatro colunas — "Falta conferir", "Aguardando pagamento", "Fechado" e "Sem conciliação" — para o mês escolhido (o passado, o atual ou o anterior). Cada cartão mostra as notas do mês e o botão "XML + PDF", que baixa o .zip das notas autorizadas daquele mês, pronto pro sistema contábil. O dono vê no histórico que o contador baixou.
- **"Empresas"**: a carteira, com regime, notas do mês, faturado no ano comparado com o limite do regime e a situação de cada uma.

Clicar numa empresa (ou escolher na busca) abre a **ficha dela**: regime, alíquota de referência, notas mês a mês (gráfico e tabela dos últimos 12 meses), limite do regime, validade do certificado, fechamento dos três últimos meses, o que tem pra fazer, o download das notas do mês e o contato do responsável. "Entrar na empresa" continua existindo pra trabalhar nela.

O faturamento mostrado é a soma das notas autorizadas que passaram pela Ana (geradas aqui ou importadas do Emissor Nacional). Receita que não virou NFS-e por aqui não entra — é um indicador, não o RBT12 oficial. O regime é o que está no cadastro da empresa: quem não é do Simples aparece como "Fora do Simples".

### Pergunte à Ana

Na tela "Ajuda", quando estiver disponível, aparece o quadro **"Pergunte à Ana"**: escreva a dúvida do seu jeito e clique em "Perguntar". A resposta sai das explicações deste guia e aparece ali mesmo. Cada pessoa pode fazer um número limitado de perguntas por dia (o quadro mostra quantas faltam); se acabarem, amanhã tem mais. Dúvidas de imposto, de alíquota ou de qual código de serviço usar são com o seu contador. A resposta é escrita por inteligência artificial e pode errar: na dúvida, fale com o suporte.

### Falar com o suporte

No menu, clique em "Precisa de ajuda? Fale com o suporte" (ou use o botão da tela "Ajuda"). Abre um formulário: escreva o assunto e a mensagem e clique em "Enviar". A resposta chega no seu e-mail, normalmente no mesmo dia útil. Quando disponível, também aparece o botão "Chamar no WhatsApp".

O e-mail do suporte é suporte@agenteana.com.br.

---

## Resumo rápido: onde fica cada coisa

| Quero... | Onde |
| --- | --- |
| Enviar ou trocar o certificado digital | "Empresa" › "Certificado" |
| Mudar os dados da empresa que saem na nota | "Empresa" › "Dados da empresa" |
| Mudar o texto do e-mail das notas | "Empresa" › "E-mails" |
| Informar a alíquota do Simples | "Empresa" › "Dados da empresa" |
| Ligar notas de teste ou importar do Emissor Nacional | "Empresa" › "Notas" |
| Ligar ou desligar um módulo | "Empresa" › "Mais opções" |
| Apagar dados de teste ou excluir a empresa | "Empresa" › "Mais opções" |
| Cadastrar um cliente | "Tomadores" › "Adicionar tomador" |
| Corrigir o CEP de um cliente | "Tomadores" › ficha do tomador › "Dados do tomador" |
| Gerar uma nota | "NFS-e" › "Nova emissão" |
| Corrigir uma nota recusada | Na nota, "Corrigir e reenviar" |
| Emitir muitas notas pela Shopee | "Notas em lote" › "Enviar relatório da Shopee" |
| Dar baixa numa nota paga | "Conciliação" › "As notas foram pagas?" |
| Importar o extrato do banco | "Financeiro" › "Importar extrato" |
| Trocar a senha ou ver aparelhos conectados | "Minha conta" › "Acesso e segurança" |
| Assinar, mudar de plano ou cancelar | "Minha conta" › "Assinatura" |
| Tema escuro e dicas | "Minha conta" › "Preferências" |
| Falar com uma pessoa | "Ajuda" › "Falar com o suporte" |

## Documentos da empresa

No menu, "Documentos da empresa" guarda os documentos fixos que o contador sempre pede, fora da pasta do mês: contrato social e alterações, cartão CNPJ, documentos dos sócios, certidões, alvará e licenças, e outros.

- **Guardar**: escolha o tipo, dê um nome (opcional), coloque a validade se tiver e escolha o arquivo (até 15 MB cada; 100 MB no total por empresa).
- **Validade**: 30 dias antes de vencer, e depois de vencido, o documento aparece em "Precisa da sua atenção".
- **Substituir**: troca o arquivo e guarda a data (não fica histórico de versões).
- **Quem vê**: só você e o contador que tiver a permissão "Documentos da empresa" (Empresa › Contador). Nem a equipe da Ana abre os documentos.
- **Quem apaga**: só o dono da empresa. O dono também vê quem abriu ou baixou cada documento ("Quem abriu").

## Pasta do mês (com o seu contador)

No menu, "Pasta do mês" junta tudo o que o seu contador precisa em cada mês:

- **A lista**: o que mandar todo mês (por exemplo, extrato do banco, notas de serviços tomados, comprovantes de pagamento). Você ou o contador montam; ela vale pros próximos meses. Pra começar rápido, use a lista sugerida.
- **Os arquivos**: em cada item, clique em "Enviar arquivo" (PDF, imagem, planilha, XML, OFX, documento ou ZIP, até 15 MB cada). Se num mês não teve, marque "Não teve neste mês".
- **O extrato**: se você importa o extrato na Conciliação, o item "Extrato do banco" já conta como enviado.
- **A conversa**: à direita, escreva o que quiser deixar combinado. O contador responde pelo painel dele, e o número no menu avisa quando chegou algo novo.

O contador vê a mesma pasta na ficha da sua empresa, no painel dele, e marca cada item como conferido.

## Integrações (Empresa › Integrações)

- **Drive**: conecte o Google Drive uma vez. Depois, em qualquer lugar, é só escolher "Enviar para o Drive" — no cadastro do tomador (envio automático), na nota ou no lote. OneDrive e Dropbox estão a caminho.
- **Google Agenda**: copie o link da sua agenda e clique em "Adicionar no Google Agenda" (ou cole em Outras agendas › + › Do URL). Os dias de gerar nota, as previsões de recebimento e os seus lembretes aparecem lá. O Google atualiza sozinho, com algumas horas de atraso. Se o link vazar, gere um novo — o antigo para de funcionar.
- **WhatsApp**: lembretes das tarefas, em breve.

