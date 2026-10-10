# Esquemas XML da NFS-e Nacional

| Arquivos | Versão | Uso na Ana |
| --- | --- | --- |
| `*_v1.00.xsd` | 1.00 | É a que a Ana **monta e valida** hoje (`app/fiscal/dps.py`). |
| `DPS_v1.01.xsd`, `NFSe_v1.01.xsd`, `tiposComplexos_v1.01.xsd`, `tiposSimples_v1.01.xsd` | 1.01 (pacote `nfse-esquemas_xsd-rtc-v1-00-20251210.zip`, publicado com a NT 004) | Guardados em 10/10/2026 para a reforma tributária. `tests/test_mei.py` valida a DPS do MEI contra eles. |

**Os arquivos 1.01 estão sem os comentários de documentação** (`xs:annotation`). A estrutura é idêntica à oficial — cada parte foi conferida por soma de verificação na hora de copiar. Fonte: gov.br/nfse › Biblioteca › Documentação técnica › RTC.

## Cuidados
- A série da DPS no 1.01 usa `(?!...)` (lookahead), que a libxml2 não entende. Os testes trocam por uma expressão equivalente antes de carregar (`[0-9]*[1-9][0-9]*` = "não pode ser só zeros").
- O 1.01 publicado é **anterior à NT 009**: não tem `regApIBSCBSSN`, `cAtvSN` nem `opSimpNac=4`. Quando a Sefin publicar o esquema da NT 009, guarde aqui como uma versão nova (sem apagar estes) e veja o raio-x técnico, seção 15.
- No 1.01 o `cNBS` é obrigatório e a ordem de `pAliq`/`tpRetISSQN` é diferente da 1.00.
