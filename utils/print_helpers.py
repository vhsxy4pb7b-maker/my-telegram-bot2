"""打印辅助函数"""
import sys


def safe_print(*args, **kwargs):
    """
    安全的打印函数，自动处理编码问题
    
    如果遇到 UnicodeEncodeError，尝试使用 ASCII 编码
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 如果包含无法编码的字符，尝试转换
        try:
            # 使用 sys.stdout.buffer 直接写入字节
            message = ' '.join(str(arg) for arg in args)
            if kwargs.get('end', '\n'):
                message += kwargs.get('end', '\n')
            sys.stdout.buffer.write(message.encode('utf-8', errors='replace'))
            sys.stdout.buffer.flush()
        except Exception:
            # 如果还是失败，使用 ASCII 编码（会丢失特殊字符）
            ascii_args = [str(arg).encode('ascii', errors='ignore').decode('ascii') 
                         for arg in args]
            print(*ascii_args, **kwargs)

