# routers/tts.py
import os
import time
import re
import subprocess
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api")

@router.get("/speak")
def speak(
    word: str = Query(..., description="要朗读的英文内容"),
    voice: str = Query("en-us", description="发音人，如 en, en-us, en-gb, zh 等"),
    background_tasks: BackgroundTasks = None
):
    try:
        # 创建临时音频目录
        temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "temp"))
        os.makedirs(temp_dir, exist_ok=True)

        # 安全命名音频文件
        safe_word = re.sub(r'[^a-zA-Z0-9_]', '_', word)
        timestamp = int(time.time() * 1000)
        filename = f"{safe_word}_{timestamp}.wav"
        audio_path = os.path.join(temp_dir, filename)

        # ✅ 调用 espeak 命令合成语音
        cmd = [
            "espeak",
            "-v", voice,          # 设置发音人，如 en-us / en / zh
            "-s", "150",          # 设置语速（可调）
            "-w", audio_path,     # 输出路径
            word
        ]
        subprocess.run(cmd, check=True)

        # ✅ 设置响应后删除音频文件
        if background_tasks:
            background_tasks.add_task(os.remove, audio_path)

        # ✅ 返回音频文件
        return FileResponse(
            path=audio_path,
            media_type="audio/wav",
            filename=f"{safe_word}.wav",
            background=background_tasks
        )

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"espeak 调用失败: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务异常: {e}")
