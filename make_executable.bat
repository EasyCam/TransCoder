@echo off
echo.
echo TransCoder Ubuntu 24.04 部署脚本已创建完成！
echo.
echo 注意：这些脚本是为Ubuntu 24.04系统设计的，需要在Linux环境中使用。
echo.
echo 已创建的脚本：
echo   setup.sh          - 一键部署脚本（首次使用）
echo   quick_start.sh     - 快速启动脚本
echo   stop.sh            - 强制停止脚本（将在setup.sh中生成）
echo   install_service.sh - 系统服务安装脚本
echo   make_executable.sh - Linux权限设置脚本
echo.
echo 部署文档：
echo   DEPLOYMENT_GUIDE.md - 详细的部署和使用指南
echo.
echo 在Ubuntu系统中的使用步骤：
echo 1. 给脚本添加执行权限：chmod +x *.sh
echo 2. 首次部署：./setup.sh
echo 3. 日常启动：./start.sh 或 ./quick_start.sh
echo 4. 停止服务：./stop.sh
echo 5. 安装系统服务：./install_service.sh
echo.
echo 请将这些文件传输到Ubuntu 24.04系统中使用。
echo.
pause 