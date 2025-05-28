from datetime import datetime
import json


# def format_time(time_str):
#     """转换时间格式 HH:MM:SS → HH:MM:SS,000"""
#     return f"{time_str},000"

# def validate_time(time_str):
#     """验证时间格式"""
#     try:
#         datetime.strptime(time_str, "%H:%M:%S")
#         return True
#     except ValueError:
#         return False
    
def json_to_srt(json_data):
    """
    将JSON字幕数据转换为SRT格式文件
    
    参数:
        json_data (list): 包含字幕数据的JSON数组
        output_file (str): 输出文件路径
    """

    def format_srt_time(time_str):
        """格式化时间为SRT标准格式"""
        if ',' in time_str:  # 已有毫秒部分
            # 确保毫秒部分为3位数字
            parts = time_str.split(',')
            if len(parts) == 2:
                return f"{parts[0]},{parts[1].ljust(3, '0')[:3]}"
            return time_str
        else:  # 没有毫秒部分
            return f"{time_str},000"
            
    srt_content = []
    
    for index, entry in enumerate(json_data, start=1):
        # # 验证时间格式
        # if not all(validate_time(t) for t in [entry['start'], entry['end']]):
        #     # raise ValueError(f"Invalid time format in entry {index}")
        #     continue
        
        # 格式化时间
        start = format_srt_time(entry['start'])
        end = format_srt_time(entry['end'])
        
        # 构建SRT块
        block = [
            str(index),
            f"{start} --> {end}",
            entry['text'],
            ""
        ]
        srt_content.append("\n".join(block))

    return srt_content    