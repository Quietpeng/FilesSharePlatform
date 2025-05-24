@echo off
echo 正在启动文件共享平台...
echo 请确保已安装所需依赖，如果尚未安装，请运行: pip install -r requirements.txt

cd /d "%~dp0"
python app.py

pause
