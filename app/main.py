from fastapi import FastAPI, Request, HTTPException, Response, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import openai # Added openai import
from typing import List
import os
import tempfile
import io
from pydub import AudioSegment
import time
from pdfminer.high_level import extract_text

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
        # The response object has a read() method to get the audio bytes
        audio_bytes = response.read()
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

@app.post("/generate-audiobook")
async def generate_audiobook(request: AudiobookRequest, background_tasks: BackgroundTasks):
    segments = split_text_into_segments(request.text)
    audio_blobs = []
    rate_limit_per_minute = 50
    delay_between_calls = 60 / rate_limit_per_minute  # Delay in seconds

    for segment in segments:
        audio_blob = call_openai_api(segment, request.api_key, request.voice)
        audio_blobs.append(audio_blob)
        time.sleep(delay_between_calls)  # Respect rate limits

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        output_path = temp_file.name
        merge_audio_files(audio_blobs, output_path)

    background_tasks.add_task(os.remove, output_path)
    return FileResponse(output_path, media_type="audio/wav", filename="merged_audio.wav", headers={"Content-Disposition": "attachment; filename=merged_audio.wav"}, background=background_tasks)

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
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...), api_key: str = Form(...), voice: str = Form(...)):
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
        time.sleep(delay_between_calls)  # Respect rate limits

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        output_path = temp_file.name
        merge_audio_files(audio_blobs, output_path)

    background_tasks.add_task(os.remove, output_path)
    return FileResponse(output_path, media_type="audio/wav", filename="merged_audio.wav", headers={"Content-Disposition": "attachment; filename=merged_audio.wav"}, background=background_tasks)
