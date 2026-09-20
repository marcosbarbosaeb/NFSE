@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
rem ==== PARAMETROS DO CANCELAMENTO (preenchidos pelo Claude) ====
set CHAVE=31062002245172374000122000000000094726097112223684
set CMOTIVO=1
set XMOTIVO=Emissao duplicada: nota reemitida manualmente pelo Emissor Nacional para atender ao prazo de envio ao tomador.
set TPAMB=1
rem ================================================================
if not exist secretos\senha.txt (
    echo Arquivo secretos\senha.txt nao encontrado. Nada foi enviado.
    goto fim
)
set /p SENHA=<secretos\senha.txt
echo ============================================================
echo   CANCELAMENTO DE NFS-e - chave %CHAVE%
echo ============================================================
python cancelar_nfse.py secretos\raiana.pfx "%SENHA%" --chave %CHAVE% --cmotivo %CMOTIVO% --xmotivo "%XMOTIVO%" --tpAmb %TPAMB% > output\resultado_cancelamento.txt 2>&1
echo ---------------- RESPOSTA ----------------
type output\resultado_cancelamento.txt
echo -------------------------------------------
:fim
set SENHA=
echo.
pause
