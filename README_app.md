# Audiobook Generator (Python Edition)

This project is a Python-based conversion of the original Audiobook Generator, which uses the OpenAI API to convert text into audiobooks. It is built with FastAPI for hosting the web application.

## Overview

The Audiobook Generator allows users to input text or upload files (text or ePub), select a voice, provide an OpenAI API key, and generate an audiobook as a WAV file. This version replicates the functionality of the original JavaScript project using Python and FastAPI.

## Setup

1. **Install Dependencies**: Ensure you have Python 3.8+ installed. Then, install the required packages by running:
   ```
   pip install -r requirements.txt
   ```

2. **Run the Application**: Start the FastAPI server with the following command from the project directory:
   ```
   uvicorn app.main:app --reload
   ```

   This will run the application on `http://127.0.0.1:8000`. The `--reload` flag enables auto-reload during development.

## Usage

- Open your browser and navigate to `http://127.0.0.1:8000`.
- Enter your OpenAI API key.
- Input text or upload a `.txt` or `.epub` file.
- Select a voice for the audiobook.
- Click "Generate Audiobook" to create and download the audio file.

## Project Structure

- `app/main.py`: Entry point for the FastAPI application.
- `app/templates/`: HTML templates for the web interface.
- `app/static/`: Static files (CSS and JavaScript) for the frontend.
- `requirements.txt`: List of Python dependencies.

## License

This project inherits the licensing terms from the original project. For more details, refer to the original repository at [https://github.com/TheMorpheus407/OpenAI-Audiobook-Generator](https://github.com/TheMorpheus407/OpenAI-Audiobook-Generator).
