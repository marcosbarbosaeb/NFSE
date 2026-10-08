# Cenários da simulação (modo demonstração)

Cada arquivo `.json` aqui é um cenário de `/simulacao?cenario=<nome do arquivo>`
(sem `cenario`, vale `afiliados`). Pra trocar de nicho, copie um arquivo, mude
os dados e abra `/simulacao?cenario=<novo nome>` — nada de mexer em cadastro.

- `empresa`: a empresa que emite (nome, cidade pelo código IBGE, endereço, alíquota).
- `tomadores`: pra quem ela emite. **CNPJ sempre com os dois últimos dígitos "00"
  e verificador errado** (o teste confere): assim nunca é uma empresa de verdade.
  `dia` = dia de gerar a nota; `dias_receber` = prazo de pagamento.
  `valores` = o valor de cada mês (`"-1"` = mês passado, `"0"` = este mês);
  sem `valores`, usa `base` crescendo `variacao_por_mes` a cada mês.
  `recebidos` = meses já pagos. `inativo: true` = tomador desligado.
  `sem_nota_no_mes: true` = não gera a nota deste mês (pra mostrar o "Gerar").
- `despesas`: gastos por mês (`mes` como acima).
- `eventos`: lembretes no calendário, `daqui_a_dias` a partir de hoje.

As notas dos meses passados já nascem autorizadas e entregues (de mentira — a
conta é de simulação e a nota é de homologação). Ver app/services/demo.py.
