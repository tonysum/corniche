#!/usr/bin/env python3
"""
移除数据管理服务相关部分的脚本
注意：保留 db.py 和 data.py，因为它们被回测服务使用
"""

import os
import shutil
import sys
import re
from pathlib import Path

def remove_data_service():
    """移除数据管理服务相关部分"""
    
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    print(f"项目根目录: {project_root}")
    print()
    
    # 确认操作（非交互模式）
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--yes':
        confirm = 'y'
    else:
        confirm = input("确认要移除数据管理服务吗？(y/N): ").strip().lower()
        if confirm != 'y':
            print("操作已取消")
            return
    
    # 1. 删除数据管理服务目录
    print("\n删除数据管理服务目录...")
    data_service_dir = project_root / "backend" / "services" / "data_service"
    if data_service_dir.exists():
        shutil.rmtree(data_service_dir)
        print(f"  ✓ 已删除 {data_service_dir}")
    else:
        print(f"  ⚠  {data_service_dir} 不存在")
    
    # 2. 删除数据管理前端目录
    print("\n删除数据管理前端目录...")
    frontend_data_dir = project_root / "frontend-data"
    if frontend_data_dir.exists():
        shutil.rmtree(frontend_data_dir)
        print(f"  ✓ 已删除 {frontend_data_dir}")
    else:
        print(f"  ⚠  {frontend_data_dir} 不存在")
    
    # 3. 删除数据下载脚本（可选）
    print("\n检查数据下载脚本...")
    download_klines = project_root / "backend" / "download_klines.py"
    if download_klines.exists():
        if len(sys.argv) > 1 and sys.argv[1] == '--yes':
            confirm = 'n'  # 默认保留，因为可能还有用
        else:
            confirm = input("删除 download_klines.py？(y/N): ").strip().lower()
        if confirm == 'y':
            download_klines.unlink()
            print(f"  ✓ 已删除 {download_klines}")
        else:
            print(f"  ⏭  保留 {download_klines}")
    
    # 4. 删除数据库迁移脚本（可选）
    print("\n检查数据库迁移脚本...")
    migrate_py = project_root / "backend" / "migrate.py"
    if migrate_py.exists():
        if len(sys.argv) > 1 and sys.argv[1] == '--yes':
            confirm = 'n'  # 默认保留，因为可能还有用
        else:
            confirm = input("删除 migrate.py？(y/N): ").strip().lower()
        if confirm == 'y':
            migrate_py.unlink()
            print(f"  ✓ 已删除 {migrate_py}")
        else:
            print(f"  ⏭  保留 {migrate_py}")
    
    # 5. 更新共享配置
    print("\n更新共享配置...")
    config_file = project_root / "backend" / "services" / "shared" / "config.py"
    if config_file.exists():
        content = config_file.read_text(encoding='utf-8')
        
        # 移除 DATA_SERVICE_PORT
        content = re.sub(r'^DATA_SERVICE_PORT = .*\n', '', content, flags=re.MULTILINE)
        
        # 移除数据管理前端的 CORS 配置
        content = re.sub(r'    "http://localhost:3001",.*\n', '', content)
        content = re.sub(r'    "http://127.0.0.1:3001",.*\n', '', content)
        content = re.sub(r'    # 数据管理前端.*\n', '', content)
        content = re.sub(r'    "http://8.216.33.6:3001",.*\n', '', content)
        
        config_file.write_text(content, encoding='utf-8')
        print(f"  ✓ 已更新 {config_file}")
    
    # 6. 更新启动脚本
    print("\n更新启动脚本...")
    start_script = project_root / "backend" / "start-services.sh"
    if start_script.exists():
        content = start_script.read_text(encoding='utf-8')
        
        # 移除数据服务启动相关代码
        lines = content.split('\n')
        new_lines = []
        skip = False
        for i, line in enumerate(lines):
            # 跳过数据服务相关的代码块
            if 'data_service' in line.lower() or 'DATA_SERVICE' in line:
                skip = True
                continue
            if skip and (line.strip().startswith('#') or 'backtest' in line.lower() or 'order' in line.lower()):
                skip = False
            if not skip:
                new_lines.append(line)
        
        start_script.write_text('\n'.join(new_lines), encoding='utf-8')
        print(f"  ✓ 已更新 {start_script}")
    
    # 7. 更新 Docker Compose 配置
    print("\n更新 Docker Compose 配置...")
    docker_compose = project_root / "docker-compose.yml"
    if docker_compose.exists():
        content = docker_compose.read_text(encoding='utf-8')
        
        # 移除 data-service 服务块
        content = re.sub(
            r'  data-service:.*?networks:.*?- crypto-network\n',
            '',
            content,
            flags=re.DOTALL
        )
        
        # 移除 frontend-data 服务块
        content = re.sub(
            r'  frontend-data:.*?networks:.*?- crypto-network\n',
            '',
            content,
            flags=re.DOTALL
        )
        
        # 移除 frontend-data 的依赖
        content = re.sub(
            r'    depends_on:\s*\n\s+- data-service\n',
            '',
            content
        )
        
        docker_compose.write_text(content, encoding='utf-8')
        print(f"  ✓ 已更新 {docker_compose}")
    
    # 8. 更新 README
    print("\n更新文档...")
    readme_file = project_root / "backend" / "README.md"
    if readme_file.exists():
        content = readme_file.read_text(encoding='utf-8')
        
        # 移除数据管理服务相关说明
        content = re.sub(
            r'### 1\. 数据管理服务.*?### 2\.',
            '### 1.',
            content,
            flags=re.DOTALL
        )
        
        # 移除其他数据服务引用
        content = re.sub(r'数据管理服务.*?\n', '', content)
        content = re.sub(r'8001.*?\n', '', content)
        
        readme_file.write_text(content, encoding='utf-8')
        print(f"  ✓ 已更新 {readme_file}")
    
    print("\n" + "="*60)
    print("数据管理服务相关部分已移除！")
    print("="*60)
    print("\n注意：")
    print("1. 已保留 db.py 和 data.py（回测服务需要使用）")
    print("2. 已保留 binance_api.py（可能被其他模块使用）")
    print("3. 请手动检查以下文件：")
    print("   - docker-compose.yml")
    print("   - backend/start-services.sh")
    print("   - 其他文档文件")
    print()

if __name__ == "__main__":
    remove_data_service()
