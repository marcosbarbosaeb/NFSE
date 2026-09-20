@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
rem ==== PARAMETROS DA NOTA (preenchidos pelo Claude a cada nota) ====
set FORNECEDOR=elausa
set COMPETENCIA=2026-08
set VALOR=10620.70
set ALIQ=12.5
rem ===================================================================
if "%VALOR%"=="" (
    echo VALOR nao definido neste .bat. Nada foi enviado.
    goto fim
)
if not exist secretos\senha.txt (
    echo Arquivo secretos\senha.txt nao encontrado. Nada foi enviado.
    goto fim
)
set /p SENHA=<secretos\senha.txt
echo ============================================================
echo   EMISSAO EM PRODUCAO - ElaUsa - competencia %COMPETENCIA% - valor %VALOR% - SN %ALIQ%%%
echo ============================================================
echo [1/4] Proximo nDPS livre (serie 1, producao)...
if exist output\proximo_ndps.txt del output\proximo_ndps.txt
python consultar_dps.py secretos\raiana.pfx "%SENHA%" --tpAmb 1 --next-file output\proximo_ndps.txt
if not exist output\proximo_ndps.txt (
    echo Nao foi possivel determinar o proximo nDPS. Nada foi enviado.
    goto fim
)
set /p NDPS=<output\proximo_ndps.txt
echo [2/4] Gerando DPS (nDPS=%NDPS%)...
python build_dps.py --fornecedor %FORNECEDOR% --competencia %COMPETENCIA% --valor %VALOR% --n-dps %NDPS% --tpAmb 1 --aliq-sn %ALIQ%
if errorlevel 1 goto fim
python resumo_dps.py output\DPS_%FORNECEDOR%_%COMPETENCIA%.xml > output\resumo_producao_elausa.txt
type output\resumo_producao_elausa.txt
echo [3/4] Assinando...
python sign_dps.py output\DPS_%FORNECEDOR%_%COMPETENCIA%.xml secretos\raiana.pfx "%SENHA%"
if errorlevel 1 goto fim
echo [4/4] Enviando para PRODUCAO...
python submit_dps.py output\DPS_%FORNECEDOR%_%COMPETENCIA%_assinada.xml secretos\raiana.pfx "%SENHA%" --tpAmb 1 > output\resultado_producao_elausa.txt 2>&1
echo ---------------- RESPOSTA ----------------
type output\resultado_producao_elausa.txt
echo ------------------------------------------
:fim
set SENHA=
echo.
pause
