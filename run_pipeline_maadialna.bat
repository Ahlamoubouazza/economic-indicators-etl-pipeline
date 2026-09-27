@echo off

cd /d "D:\Desktop\mon stage pfa\projet-indicateurs-eco"

call ".venv\Scripts\activate.bat"

python -m src.pipeline.pipeline_maadialna

pause