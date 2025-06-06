from fastapi import FastAPI, Request, HTTPException, Response, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import openai # Added openai import
from typing import List, Optional
import os
import tempfile
import io
from pydub import AudioSegment
import asyncio
from pdfminer.high_level import extract_text
import zipfile
import shutil

app = FastAPI()

# 獲取當前文件的目錄
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 確保靜態文件和模板目錄存在
static_dir = os.path.join(os.path.dirname(BASE_DIR), "static") # Adjusted path
templates_dir = os.path.join(os.path.dirname(BASE_DIR), "templates") # Adjusted path

# 自動創建目錄（如果不存在）
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    print(f"自動創建靜態文件目錄: {static_dir}")

if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
    print(f"自動創建模板目錄: {templates_dir}")

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Set up templates
templates = Jinja2Templates(directory=templates_dir)

class AudiobookRequest(BaseModel):
    text: str
    api_key: str
    voice: str
    max_duration: Optional[int] = None  # Maximum seconds per output file

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {"status": "ok"}

def split_text_into_segments(text: str, max_length: int = 4000) -> List[str]:
    segments = []
    current_segment = ''
    for sentence in text.split('. '):
        if len(current_segment) + len(sentence) > max_length:
            segments.append(current_segment)
            current_segment = ''
        current_segment += sentence + '. '
    if current_segment.strip():
        segments.append(current_segment)
    return segments

def call_openai_api(segment: str, api_key: str, voice: str) -> bytes:
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=segment
        )
        # The response content property returns the audio bytes directly
        audio_bytes = response.content
        return audio_bytes
    except openai.APIError as e:
        # Handle OpenAI API errors more specifically
        raise HTTPException(status_code=e.status_code if hasattr(e, 'status_code') else 500, detail=str(e))
    except Exception as e:
        # Catch any other unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred with the OpenAI API: {str(e)}")


def merge_audio_files(audio_files: List[bytes], output_path: str) -> str:
    combined = AudioSegment.empty()
    for audio_data in audio_files:
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
        combined += audio_segment
    combined.export(output_path, format="wav")
    return output_path

def merge_audio_files_with_limit(audio_files: List[bytes], output_dir: str, max_duration: Optional[int] = None) -> List[str]:
    """Merge MP3 blobs into one or more WAV files respecting a duration limit."""
    outputs = []
    combined = AudioSegment.empty()
    current_duration = 0.0
    part = 1

    for audio_data in audio_files:
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_data), format="mp3")
        segment_duration = audio_segment.duration_seconds

        if max_duration and current_duration + segment_duration > max_duration and len(combined) > 0:
            out_path = os.path.join(output_dir, f"part_{part}.wav")
            combined.export(out_path, format="wav")
            outputs.append(out_path)
            combined = AudioSegment.empty()
            current_duration = 0.0
            part += 1

        combined += audio_segment
        current_duration += segment_duration

    if len(combined):
        out_path = os.path.join(output_dir, f"part_{part}.wav")
        combined.export(out_path, format="wav")
        outputs.append(out_path)

    return outputs

@app.post("/generate-audiobook")
async def generate_audiobook(request: AudiobookRequest, background_tasks: BackgroundTasks):
    segments = split_text_into_segments(request.text)
    audio_blobs = []
    rate_limit_per_minute = 50
    delay_between_calls = 60 / rate_limit_per_minute  # Delay in seconds

    for segment in segments:
        audio_blob = call_openai_api(segment, request.api_key, request.voice)
        audio_blobs.append(audio_blob)
        await asyncio.sleep(delay_between_calls)  # Respect rate limits

    temp_dir = tempfile.mkdtemp()
    file_paths = merge_audio_files_with_limit(audio_blobs, temp_dir, request.max_duration)

    if len(file_paths) == 1:
        file_path = file_paths[0]
        background_tasks.add_task(shutil.rmtree, temp_dir)
        return FileResponse(file_path, media_type="audio/wav", filename="merged_audio.wav", headers={"Content-Disposition": "attachment; filename=merged_audio.wav"}, background=background_tasks)
    else:
        zip_path = os.path.join(temp_dir, "audiobook_parts.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for p in file_paths:
                zf.write(p, arcname=os.path.basename(p))
        background_tasks.add_task(shutil.rmtree, temp_dir)
        return FileResponse(zip_path, media_type="application/zip", filename="audiobook_parts.zip", headers={"Content-Disposition": "attachment; filename=audiobook_parts.zip"}, background=background_tasks)

from fastapi import UploadFile, File, Form
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def extract_text_from_epub(file_content: bytes) -> str:
    book = epub.read_epub(io.BytesIO(file_content))
    text_content = []
    for item in book.get_items():
        if item.get_type() == epub.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            text_content.append(text)
    return "\n".join(text_content)

def extract_text_from_pdf(file_content: bytes) -> str:
    # Use io.BytesIO to treat the byte content as a file-like object
    return extract_text(io.BytesIO(file_content))

@app.post("/upload-file")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), api_key: str = Form(...), voice: str = Form(...), max_duration: int = Form(None)):
    content = await file.read()
    text = ""
    if file.filename.endswith('.txt'):
        text = content.decode('utf-8')
    elif file.filename.endswith('.epub'):
        text = extract_text_from_epub(content)
    elif file.filename.endswith('.pdf'): # New condition
        text = extract_text_from_pdf(content) # Call to new function
    else:
        # Updated error message
        raise HTTPException(status_code=400, detail="Unsupported file type. Only .txt, .epub, and .pdf files are supported.")

    segments = split_text_into_segments(text)
    audio_blobs = []
    rate_limit_per_minute = 50
    delay_between_calls = 60 / rate_limit_per_minute  # Delay in seconds

    for segment in segments:
        audio_blob = call_openai_api(segment, api_key, voice)
        audio_blobs.append(audio_blob)
        await asyncio.sleep(delay_between_calls)  # Respect rate limits

    temp_dir = tempfile.mkdtemp()
    file_paths = merge_audio_files_with_limit(audio_blobs, temp_dir, max_duration)

    if len(file_paths) == 1:
        file_path = file_paths[0]
        background_tasks.add_task(shutil.rmtree, temp_dir)
        return FileResponse(file_path, media_type="audio/wav", filename="merged_audio.wav", headers={"Content-Disposition": "attachment; filename=merged_audio.wav"}, background=background_tasks)
    else:
        zip_path = os.path.join(temp_dir, "audiobook_parts.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for p in file_paths:
                zf.write(p, arcname=os.path.basename(p))
        background_tasks.add_task(shutil.rmtree, temp_dir)
        return FileResponse(zip_path, media_type="application/zip", filename="audiobook_parts.zip", headers={"Content-Disposition": "attachment; filename=audiobook_parts.zip"}, background=background_tasks)
