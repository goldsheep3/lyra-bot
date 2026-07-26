import re
from pathlib import Path

def generate_font_gitignore():
    # 1. 定义绝对/相对路径（基于项目根目录执行）
    enum_file_path = Path("plugins/maib/image_gen/resources.py")
    gitignore_file_path = Path("plugins/maib/assets/fonts/.gitignore")
    
    if not enum_file_path.exists():
        print(f"❌ 错误: 找不到枚举文件 {enum_file_path}")
        return

    # 2. 读取源码
    lines = enum_file_path.read_text(encoding="utf-8").splitlines()
    
    # 3. 初始化文件头
    output_lines = [
        "**/*.ttf",
        "**/*.otf",
        "",
        "# --- 以下排除(根据 FontCode 自动生成) ---",
        ""
    ]
    
    # 正则：匹配 [可选#] + [变量名] + = + [引号内的路径]
    pattern = re.compile(r'^\s*(#)?\s*\w+\s*=\s*["\']([^"\']+)["\']')

    for line in lines:
        # 保留大分类注释（如 # JetBrains Mono 静态字体），但过滤掉类本身的描述性注释
        if line.strip().startswith("#") and "=" not in line:
            clean_line = line.strip()
            if "字体名称枚举" not in clean_line and "---" not in clean_line:
                output_lines.append(clean_line)
            continue
            
        match = pattern.match(line)
        if match:
            is_commented = match.group(1) is not None
            # 统一提取出类似 "JetBrains_Mono/static/JetBrainsMono-Bold.ttf" 的部分
            font_path = match.group(2)
            
            # 注意：实际写入 .gitignore 时，路径需要根据它所在的位置来定。
            # 因为 .gitignore 在 plugins/maib/assets/fonts/ 下，
            # 如果你的 resources.py 里写的是相对该 fonts 目录的路径（或者相对根目录），需要在此处做微调。
            # 这里默认直接使用你原代码里的路径字串。
            if is_commented:
                output_lines.append(f"# !{font_path}")
            else:
                output_lines.append(f"!{font_path}")
                
        elif not line.strip() and output_lines[-1] != "":
            # 保持优雅的空行隔开
            output_lines.append("")

    # 4. 确保父目录存在并写入
    gitignore_file_path.parent.mkdir(parents=True, exist_ok=True)
    gitignore_file_path.write_text("\n".join(output_lines).strip() + "\n", encoding="utf-8")
    print(f"🎉 成功同步！已更新: {gitignore_file_path}")

if __name__ == "__main__":
    generate_font_gitignore()
