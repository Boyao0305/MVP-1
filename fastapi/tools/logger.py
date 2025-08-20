from loguru import logger
import sys
import os

# 确保 log 文件夹存在
os.makedirs("log", exist_ok=True)
os.environ["TZ"] = "Asia/Shanghai"
try:
    import time
    time.tzset()  # Linux/Mac 有效，Windows 无效
except Exception:
    pass

# 移除 loguru 的默认 handler
logger.remove()

# 控制台输出
logger.add(
    sys.stdout, 
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS Z}</green> | <cyan>{level}</cyan> | <level>{message}</level>",
    enqueue=True,
    backtrace=True,
    diagnose=True,
)

# 日志文件输出到 log/ 目录，时间为北京时间，每天轮换
logger.add(
    "log/app_{time:YYYY-MM-DD}.log",  # 文件名为当天日期
    rotation="1 day",                 # 每天轮换
    retention="10 days",              # 最多保留10天
    encoding="utf-8",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS Z} | {level} | {message}",
    enqueue=True,
    backtrace=True,
    diagnose=True,
)

# 这样，logger 会同时输出到控制台和 log 文件夹下的文件，并且每天生成一个新日志文件