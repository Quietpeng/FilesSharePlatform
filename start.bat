@echo off
echo 文件共享平台启动脚本
echo 请确保已安装所需依赖，如果尚未安装，请运行: pip install -r requirements.txt

cd /d "%~dp0"

:parse_args
if "%~1"=="" goto continue
if /i "%~1"=="--clean" (
  set CLEAN_ARG=--clean
  echo [选项] 启动时将清理所有文件
  shift
  goto parse_args
)
if /i "%~1"=="--clean-on-exit" (
  set CLEAN_EXIT_ARG=--clean-on-exit
  echo [选项] 退出时将清理所有文件
  shift
  goto parse_args
)
if /i "%~1"=="-h" (
  echo 用法: start.bat [选项]
  echo.
  echo 选项:
  echo   --clean           启动时清理所有文件和数据
  echo   --clean-on-exit   退出时清理所有文件和数据
  echo   -h, --help        显示此帮助信息
  exit /b 0
)
if /i "%~1"=="--help" (
  goto help
)

:continue
echo 检查配置文件...
if not exist config.json (
  echo 配置文件不存在，将使用默认配置
)

echo 正在启动文件共享平台...
python app.py %CLEAN_ARG% %CLEAN_EXIT_ARG%

pause
