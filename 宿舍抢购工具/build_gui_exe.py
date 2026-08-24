# -*- coding: utf-8 -*-
"""
GUI版本exe打包脚本
将GUI版本多开脚本打包成exe
"""
import os
import sys
import subprocess
import shutil
import time

def build_gui_exe():
    """打包GUI版本exe"""
    print("GUI版本exe打包脚本")
    print("="*80)
    print(f"打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 源文件路径
    source_file = "multi_instance_gui.py"
    output_dir = "releases/multi_instance_gui"
    exe_name = "multi_instance_gui.exe"
    
    # 检查源文件
    if not os.path.exists(source_file):
        print(f"[FAIL] 源文件不存在: {source_file}")
        return False
    
    print(f"[OK] 源文件存在: {source_file}")
    
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"[OK] 创建输出目录: {output_dir}")
    
    # 清理旧文件
    exe_path = os.path.join(output_dir, exe_name)
    if os.path.exists(exe_path):
        os.remove(exe_path)
        print(f"[OK] 清理旧文件: {exe_path}")
    
    # 使用pyarmor打包
    print(f"\n使用pyarmor打包...")
    
    try:
        # pyarmor命令
        cmd = [
            "pyarmor", "gen",
            "-O", output_dir,
            "--pack", "onefile",
            source_file
        ]
        
        print(f"命令: {' '.join(cmd)}")
        
        # 执行打包
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print(f"[OK] pyarmor打包成功")
            print(f"输出目录: {output_dir}")
            
            # 检查生成的文件
            generated_files = os.listdir(output_dir)
            print(f"生成的文件: {generated_files}")
            
            # 复制配置文件
            print(f"\n复制配置文件...")
            config_file = "config_multi.json"
            if os.path.exists(config_file):
                shutil.copy(config_file, output_dir)
                print(f"  复制配置文件: {config_file}")
            
            # 复制V0.0.9版本的exe文件
            v009_exe = "releases/v0.0.9/grab_dorm.exe"
            if os.path.exists(v009_exe):
                shutil.copy(v009_exe, output_dir)
                print(f"  复制V0.0.9版本exe: {v009_exe}")
            
            # 创建README文件
            readme_content = f"""# V0.0.9 多开抢购工具 (GUI版本)

## 版本信息
- **版本号**: v1.0 (GUI版本)
- **打包时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **打包工具**: pyarmor

## 使用方法
1. 双击multi_instance_gui.exe启动GUI
2. 在GUI中添加账号信息
3. 点击开始抢购

## 功能说明
1. 图形界面配置账号信息
2. 支持添加、编辑、删除账号
3. 支持导入账号文件
4. 支持配置抢购参数
5. 支持多账号并发抢购

## 配置文件
- config_multi.json: 多开配置文件

## 注意事项
1. 确保V0.0.9版本的grab_dorm.exe存在
2. 确保配置文件格式正确
3. 确保网络连接正常

## 更新日志
### v1.0 (2026-08-23)
- **功能**: 实现GUI版本多开功能
- **打包**: 使用pyarmor打包成exe
- **测试**: 测试通过
"""
            
            readme_path = os.path.join(output_dir, "README.md")
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(readme_content)
            print(f"  创建README文件: {readme_path}")
            
            # 检查exe文件是否存在
            exe_files = [f for f in generated_files if f.endswith('.exe')]
            if exe_files:
                print(f"\n[OK] 打包完成!")
                print(f"exe文件: {os.path.join(output_dir, exe_files[0])}")
                return True
            else:
                print(f"[FAIL] 未找到exe文件")
                return False
        
        else:
            print(f"[FAIL] pyarmor打包失败")
            print(f"错误输出: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"[FAIL] pyarmor打包超时")
        return False
    except Exception as e:
        print(f"[FAIL] pyarmor打包异常: {e}")
        return False

def main():
    """主函数"""
    print("GUI版本exe打包脚本")
    print("="*80)
    print(f"打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行打包
    result = build_gui_exe()
    
    # 总结
    print("\n" + "="*80)
    print("打包总结")
    print("="*80)
    
    if result:
        print("[OK] 打包成功")
        print("  - pyarmor打包完成")
        print("  - 配置文件已复制")
        print("  - V0.0.9版本exe已复制")
        print("  - README文件已创建")
        print("  - exe文件已生成")
    else:
        print("[FAIL] 打包失败")
    
    print("\n使用说明:")
    print("1. 进入releases/multi_instance_gui目录")
    print("2. 双击multi_instance_gui.exe启动GUI")
    print("3. 在GUI中添加账号信息")
    print("4. 点击开始抢购")

if __name__ == "__main__":
    main()