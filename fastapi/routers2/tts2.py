# routers/tts.py
import os
import time
import re
import asyncio
import subprocess
import shlex
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException, Depends
from fastapi.responses import FileResponse
from tools.logger import logger
from functions.auth import authenticate_user, register_user, get_current_user
from pydantic import BaseModel
router = APIRouter(prefix="/test")
class TokenData(BaseModel):
    user_id: int
    role: str
@router.get("/speak")
async def speak(
    word: str = Query(..., description="要朗读的英文内容"),
    voice: str = Query("en-us", description="发音人，如 en, en-us, en-gb, zh 等"),
    background_tasks: BackgroundTasks = None,
    current_user: TokenData = Depends(get_current_user),
):
    user_id = current_user.user_id
    try:
        logger.info(f"收到朗读请求 word={word}, voice={voice}")

        # 创建临时音频目录
        temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "temp"))
        os.makedirs(temp_dir, exist_ok=True)
        logger.debug(f"音频临时目录为: {temp_dir}")

        # 安全命名音频文件
        safe_word = re.sub(r"[^a-zA-Z0-9_]", "_", word)
        timestamp = int(time.time() * 1000)
        filename = f"{safe_word}_{timestamp}.wav"
        audio_path = os.path.join(temp_dir, filename)
        logger.debug(f"音频文件路径: {audio_path}")

        # 调用 espeak 命令合成语音（异步，不阻塞事件循环）
        cmd = [
            "espeak",
            "-v", voice,
            "-s", "150",
            "-w", audio_path,
            word,
        ]
        logger.info(f"执行命令: {' '.join(shlex.quote(part) for part in cmd)}")
        proc = await asyncio.create_subprocess_exec(*cmd)
        rc = await proc.wait()
        if rc != 0:
            raise subprocess.CalledProcessError(rc, cmd)
        logger.info(f"音频合成完成: {audio_path}")

        # 设置响应后删除音频文件
        if background_tasks is None:
            background_tasks = BackgroundTasks()
        background_tasks.add_task(os.remove, audio_path)
        logger.debug(f"添加后台任务，响应后删除音频文件: {audio_path}")

        # 返回音频文件
        return FileResponse(
            path=audio_path,
            media_type="audio/wav",
            filename=f"{safe_word}.wav",
            background=background_tasks,
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"espeak 调用失败: {e}")
        raise HTTPException(status_code=500, detail=f"espeak 调用失败: {e}")
    except Exception as e:
        logger.exception("服务异常")
        raise HTTPException(status_code=500, detail=f"服务异常: {e}")
