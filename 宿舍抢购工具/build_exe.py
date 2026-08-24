# -*- coding: utf-8 -*-
"""
pyarmor打包脚本
将v1.2.6版本打包成exe
"""
import os
import sys
import subprocess
import shutil

def build_exe():
    """打包exe"""
    print("pyarmor打包脚本")
    print("="*80)
    print(f"打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 源文件路径
    source_file = "_dev/grab_dorm.py"
    output_dir = "releases/v1.2.6"
    exe_name = "grab_dorm_v1.2.6.exe"
    
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
        # pyarmor命令 - 使用gen命令
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
            
            # 复制必要的依赖文件
            print(f"\n复制必要的依赖文件...")
            
            # 复制配置文件
            config_files = ["config.json", "config_account2.json"]
            for config_file in config_files:
                if os.path.exists(config_file):
                    shutil.copy(config_file, output_dir)
                    print(f"  复制配置文件: {config_file}")
            
            # 复制激活模块
            activation_file = "_dev/activation.py"
            if os.path.exists(activation_file):
                shutil.copy(activation_file, output_dir)
                print(f"  复制激活模块: {activation_file}")
            
            # 复制GUI模块（如果存在）
            gui_file = "_dev/gui.py"
            if os.path.exists(gui_file):
                shutil.copy(gui_file, output_dir)
                print(f"  复制GUI模块: {gui_file}")
            
            # 创建README文件
            readme_content = f"""# v1.2.6 抢宿舍工具

## 版本信息
- **版本号**: 1.2.6
- **打包时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}
- **打包工具**: pyarmor

## 使用方法
1. 双击 {exe_name} 运行
2. 或者使用命令行: {exe_name} --config config.json

## 配置文件
- config.json: 主配置文件
- config_account2.json: 账号2配置文件

## 激活KEY
- 使用: --key RSO-QIANGSS-2026

## 优化功能
1. 立即使用worker: 开放时间到达后立即启动
2. 连接池优化: 使用连接池，减少连接建立时间
3. 智能重试: 根据错误类型智能重试
4. 预取验证码: AI+ddddocr双识别投票

## 注意事项
1. 确保网络连接正常
2. 正式使用前先进行演练测试
3. 保持时间同步准确
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
    print("pyarmor打包脚本")
    print("="*80)
    print(f"打包时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行打包
    result = build_exe()
    
    # 总结
    print("\n" + "="*80)
    print("打包总结")
    print("="*80)
    
    if result:
        print("[OK] 打包成功")
        print("  - pyarmor打包完成")
        print("  - 依赖文件已复制")
        print("  - README文件已创建")
        print("  - exe文件已生成")
    else:
        print("[FAIL] 打包失败")
    
    print("\n使用说明:")
    print("1. 进入releases/v1.2.6目录")
    print("2. 双击grab_dorm_v1.2.6.exe运行")
    print("3. 或者使用命令行: grab_dorm_v1.2.6.exe --config config.json")

if __name__ == "__main__":
    import time
    main()