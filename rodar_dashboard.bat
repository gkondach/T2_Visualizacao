@echo off
REM ============================================================
REM  Dashboard LEM - Fundacao Pao dos Pobres
REM  Script de instalacao e execucao automatica (Windows)
REM
REM  O que este script faz:
REM   1. Verifica se o Python esta instalado (senao, orienta a instalar)
REM   2. Cria um ambiente virtual proprio dentro da pasta do projeto
REM   3. Instala automaticamente todas as bibliotecas necessarias
REM   4. Abre o dashboard no navegador
REM
REM  Basta dar 2 cliques neste arquivo. Pode ser executado quantas
REM  vezes quiser: da segunda vez em diante, ele pula a instalacao
REM  (muito mais rapido) e ja abre o dashboard direto.
REM ============================================================

setlocal enabledelayedexpansion
title Dashboard LEM - Fundacao Pao dos Pobres

REM Muda para a pasta onde este .bat esta salvo (funciona em qualquer PC/caminho)
cd /d "%~dp0"

echo ============================================================
echo   Dashboard LEM - Fundacao Pao dos Pobres
echo ============================================================
echo.

REM ---------- 1. Verificar se o Python esta instalado ----------
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao foi encontrado neste computador.
    echo.
    echo Instale o Python antes de continuar:
    echo   1. Acesse: https://www.python.org/downloads/
    echo   2. Baixe e instale a versao mais recente
    echo   3. IMPORTANTE: na tela de instalacao, marque a opcao
    echo      "Add Python to PATH" antes de clicar em Instalar
    echo   4. Depois de instalar, execute este arquivo novamente
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python encontrado: versao !PYVER!
echo.

REM ---------- 2. Criar ambiente virtual (so na primeira vez) ----------
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Criando ambiente virtual isolado ^(.venv^)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    echo [OK] Ambiente virtual criado.
) else (
    echo [OK] Ambiente virtual ja existe. Pulando esta etapa.
)
echo.

REM ---------- 3. Instalar/atualizar as bibliotecas necessarias ----------
echo [2/3] Verificando e instalando bibliotecas necessarias...
echo       ^(streamlit, pandas, numpy, plotly, openpyxl^)
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar as bibliotecas. Verifique sua conexao com a internet.
    pause
    exit /b 1
)
echo [OK] Todas as bibliotecas estao instaladas.
echo.

REM ---------- 4. Rodar o dashboard ----------
echo [3/3] Abrindo o dashboard no navegador...
echo       ^(para fechar o dashboard, feche esta janela ou pressione Ctrl+C^)
echo.
".venv\Scripts\python.exe" -m streamlit run app.py

pause
