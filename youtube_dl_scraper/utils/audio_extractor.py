import subprocess

def extract_mp3(input_file, output_file):
    """
    从MP4文件中提取MP3音频
    
    参数:
        input_file: 输入的MP4文件路径
        output_file: 输出的MP3文件路径
    """
    command = [
        'ffmpeg',
        '-i', input_file,      # 输入文件
        '-vn',                 # 禁用视频流
        '-acodec', 'libmp3lame',  # 使用MP3编码器
        '-q:a', '2',           # 设置VBR质量（0-9，0为最高质量）
        '-y',                  # 覆盖输出文件（可选）
        output_file
    ]
    
    try:
        # 执行命令
        result = subprocess.run(
            command,
            check=True,        # 检查命令是否成功执行
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"成功提取音频到: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"提取失败: {e.stderr.decode('utf-8')}")
        return False
    except FileNotFoundError:
        print("错误: 未找到ffmpeg，请确保已安装并添加到系统路径")
        return False