#!/usr/bin/env python
import asyncio
import threading
import queue
import json
from youtube_dl_scraper import YouTube
import os
import uvicorn
import sqlite3
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Path
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, Tuple, Any
from datetime import datetime
from contextlib import asynccontextmanager # Import asynccontextmanager
from starlette.websockets import WebSocketState
from urllib.parse import urlparse

# --- Configuration ---
DOWNLOADS_DIR = "downloads"
DATABASE_URL = "tasks.db"

# Create downloads directory if it doesn't exist
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)

# --- Database Initialization ---
def init_db():
    """Initializes the SQLite database and creates the tasks table."""
    try:
        with sqlite3.connect(DATABASE_URL) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    error_message TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        print(f"Database initialized at {DATABASE_URL}")
    except Exception as e:
        print(f"Error initializing database: {e}")

# Initialize the database on script startup
# This ensures the DB and table exist before the FastAPI app starts processing requests
init_db()

# --- Queues and Connection Storage ---
# Task queue for the download worker: (task_id, url, client_id)
download_queue: queue.Queue[Tuple[str, str, Tuple[str, int]] | None] = queue.Queue() # Added None for sentinel
# Status queue from worker to main loop: {"task_id": ..., "status": ..., "message": ..., "client_id": ...}
status_queue: queue.Queue[Dict[str, Any]] = queue.Queue()

# Store active WebSocket connections mapped by a unique identifier (e.g., connection info)
active_websockets: Dict[Tuple[str, int], WebSocket] = {}

# --- Database Operations (Thread-Safe Helpers) ---
# It's safer for threads to have their own connections for writes.
# Reads can potentially share connections more safely, but separate is simpler here.

def execute_db_query(query: str, params: Tuple = ()):
    """Helper to execute DB queries that modify data."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print(f"Database query error: {e}\nQuery: {query}\nParams: {params}")
        # Re-raise or handle as needed
        raise e
    finally:
        if conn:
            conn.close()

def create_task_in_db(task_id: str, url: str):
    """Inserts a new task with 'pending' status into the database."""
    query = "INSERT INTO tasks (task_id, url, status) VALUES (?, ?, ?)"
    execute_db_query(query, (task_id, url, "pending"))
    print(f"DB: Created task {task_id} for URL {url}")

def update_task_status_in_db(task_id: str, status: str):
    """Updates the status and details of a task in the database."""
    query = """
        UPDATE tasks
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE task_id = ?
    """
    execute_db_query(query, (status, task_id))
    print(f"DB: Updated task {task_id} to status '{status}'")

def update_task_status_result_in_db(task_id: str, status: str, result: str):
    """Updates the status and details of a task in the database."""
    query = """
        UPDATE tasks
        SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP
        WHERE task_id = ?
    """
    execute_db_query(query, (status, result, task_id))
    print(f"DB: Updated task {task_id} to status '{status}'")

def update_task_status_error_in_db(task_id: str, status: str, error_message: str):
    """Updates the status and details of a task in the database."""
    query = """
        UPDATE tasks
        SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
        WHERE task_id = ?
    """
    execute_db_query(query, (status, error_message, task_id))
    print(f"DB: Updated task {task_id} to status '{status}'")

def get_task_from_db(task_id: str) -> Dict[str, Any] | None:
    """Retrieves a task record by its ID from the database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_URL)
        conn.row_factory = sqlite3.Row # Return rows as dictionaries
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, url, status, result, error_message, created_at, updated_at FROM tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Database error retrieving task {task_id}: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_task_from_db_by_url(url: str) -> Dict[str, Any] | None:
    """Retrieves a task record by its ID from the database."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_URL)
        conn.row_factory = sqlite3.Row # Return rows as dictionaries
        cursor = conn.cursor()
        cursor.execute("SELECT task_id, url, status, result, error_message, created_at, updated_at FROM tasks WHERE url = ?", (url,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"Database error retrieving task {url}: {e}")
        return None
    finally:
        if conn:
            conn.close()


# --- Download Worker Thread ---

def download_worker(download_q: queue.Queue, status_q: queue.Queue):
    """Worker thread to process the download queue."""
    print("Download worker thread started.")
    while True:
        task_info = download_q.get()
        if task_info is None:  # Sentinel value to stop the thread
            print("Download worker received stop signal, exiting.")
            break # Exit the thread loop

        task_id, url, client_id = task_info

        print(f"Worker: Processing task {task_id} for URL: {url} (client: {client_id})")

        # Update status in DB
        update_task_status_in_db(task_id, "downloading")
        # Send status update to client
        status_q.put({"task_id": task_id, "status": "downloading", "message": f"Starting download for {url}", "client_id": client_id})

        result = {}
        error_msg = None

        task = get_task_from_db_by_url(url)

        print(f'task exists=={task}')

        if task and task.get('result') and task_id != task.get('task_id'):
            prev_result = json.loads(task['result'])
            result.update(prev_result)
            # status = 'success' if result.get('audio') and result.get('srt') else 'downloading'
            # update_task_status_result_in_db(task_id, status, result=json.dumps(result))

        print(f'task result=={result}')

        # notegpt 可在国内网络下运行
        youtube = YouTube(caption_scraper_name = "notegpt")

        try:
            if not result.get('audio'):
                video = youtube.scrape_video(url)
                final_audio_filepath = video.streams.get_higher_bitrate().download()
                print(final_audio_filepath)

                
                if final_audio_filepath and os.path.exists(final_audio_filepath) and os.path.getsize(final_audio_filepath) > 0:
                    print(f"Worker: Task {task_id} successful. File: {final_audio_filepath}")
                    result.update({'audio': final_audio_filepath})
                    # Update status in DB
                    update_task_status_result_in_db(task_id, "partial_success", result=json.dumps(result))
                    # Send status update to client
                    status_q.put({"task_id": task_id, "status": "success", "message": result, "client_id": client_id})
                else:
                    # If file wasn't found or download somehow completed without error but no file
                    error_msg = "Download completed, but final file could not be confirmed."
                    print(f"Worker: Task {task_id} failed or file not found: {error_msg}")
                    # Update status in DB
                    update_task_status_error_in_db(task_id, "failed", error_message=error_msg)
                    # Send status update to client
                    status_q.put({"task_id": task_id, "status": "failed", "message": error_msg, "client_id": client_id})

        except Exception as e:
            print(f"Worker: Download failed for audio task {task_id}: {e}")
            error_msg = str(e)
            # Update status in DB
            update_task_status_error_in_db(task_id, "failed", error_message=error_msg)
            # Send status update to client
            status_q.put({"task_id": task_id, "status": "failed", "message": error_msg, "client_id": client_id})

        final_srt_filepath = None
        final_text_filepath = None
        try:
            if not result.get('srt'):
                captions = None
                try:
                    captions = youtube.scrape_captions(url)
                except Exception as e:
                    print("capture captions failed", e)

                if captions:
                    # print(captions)
                    print(captions.subtitles)

                    caption = captions.get_captions_by_lang_code('a.en')
                    if not caption:
                        caption = captions.get_captions_by_lang_code('en')
                        if not caption:                    
                            caption = captions.get_captions_by_lang_code('en-US')

                    try:
                        final_srt_filepath = caption.raw2file().as_posix()
                        final_text_filepath = caption.txt().as_posix()
                    except Exception as e:
                        print("capture raw subtitles failed", e)
                    # try:
                    #     final_filepath = caption.txt().as_posix()
                    # except Exception as e:
                    #     print("capture txt subtitles failed", e)
                    #     try:
                    #         final_filepath = caption.raw2file().as_posix()
                    #     except Exception as e:
                    #         print("capture raw subtitles failed", e)
                    #         pass    

                if not final_srt_filepath or not final_text_filepath:
                    # downsub 下载文件的域名从国内网络无法访问
                    youtube = YouTube(caption_scraper_name = "downsub")

                    try:
                        captions = youtube.scrape_captions(url)
                    except Exception as e:
                        print("capture captions failed again", e)

                    if captions:
                        caption = captions.get_captions_by_lang_code('a.en')
                        if not caption:
                            caption = captions.get_captions_by_lang_code('en')
                            if not caption:                    
                                caption = captions.get_captions_by_lang_code('en-US')

                        try:
                            final_srt_filepath = caption.raw2file().as_posix()
                            final_text_filepath = caption.txt().as_posix()
                        except Exception as e:
                            print("capture txt subtitles failed again", e)

                print(final_srt_filepath)
                print(final_text_filepath)
                
                if final_srt_filepath and os.path.exists(final_srt_filepath) and os.path.getsize(final_srt_filepath) > 0 and final_text_filepath and os.path.exists(final_text_filepath) and os.path.getsize(final_text_filepath) > 0:
                    print(f"Worker: Task {task_id} successful. File: {final_srt_filepath}")
                    result.update({'srt': final_srt_filepath, 'text': final_text_filepath})
                    # Update status in DB
                    update_task_status_result_in_db(task_id, "partial_success", result=json.dumps(result))
                    # Send status update to client
                    status_q.put({"task_id": task_id, "status": "success", "message": result, "client_id": client_id})
                else:
                    # If file wasn't found or download somehow completed without error but no file
                    #  error_msg = final_filepath if "file path unknown" in str(final_filepath) else "Download completed, but final file could not be confirmed."
                    error_msg = "Download completed, but final file could not be confirmed."
                    print(f"Worker: Task {task_id} failed or file not found: {error_msg}")
                    # Update status in DB
                    update_task_status_error_in_db(task_id, "failed", error_message=error_msg)
                    # Send status update to client
                    status_q.put({"task_id": task_id, "status": "failed", "message": error_msg, "client_id": client_id})

        except Exception as e:
            print(f"Worker: Download failed for srt task {task_id}: {e}")
            error_msg = str(e)
            # Update status in DB
            update_task_status_error_in_db(task_id, "failed", error_message=error_msg)
            # Send status update to client
            status_q.put({"task_id": task_id, "status": "failed", "message": error_msg, "client_id": client_id})

        finally:
            try:
                status = 'success' if result.get('audio') and result.get('srt') and result.get('text') else 'failed'
                update_task_status_result_in_db(task_id, status, result=json.dumps(result))
            except Exception as e:
                print(f"Worker: Download successfully but update status failed for task {task_id}: {e}")
                error_msg = str(e)
                # Send status update to client
                status_q.put({"task_id": task_id, "status": "failed", "message": error_msg, "client_id": client_id})

            download_q.task_done() # Signal that the task is done for the queue

    print("Download worker thread finished.")


# Start the background download worker thread (will be started by lifespan manager)
# worker_thread = threading.Thread(target=download_worker, args=(download_queue, status_queue), daemon=True)
# worker_thread.start()


# --- Background Task for Sending Status Updates ---
async def status_sender_task(status_q: queue.Queue, active_websockets: Dict[Tuple[str, int], WebSocket]):
    """Background task to send status updates from the worker to clients."""
    print("Status sender background task started.")
    while True:
        try:
            # Get without blocking, wait a bit if empty
            status_update = status_q.get_nowait()
            task_id = status_update.get("task_id")
            client_id = status_update.get("client_id")
            status_message = {
                "task_id": task_id,
                "status": status_update.get("status"),
                "message": status_update.get("message")
            }

            # Find the correct websocket and send the update
            if client_id in active_websockets:
                websocket = active_websockets[client_id]
                # Check if connection is still active using internal state
                # if not websocket.client_state.disconnection_sent: # websockets v10+
                # if not websocket.closed: # older versions of websockets
                if websocket.client_state == WebSocketState.CONNECTED:
                     print(f"Status Sender: Sending status '{status_message['status']}' for task {task_id} to client {client_id}")
                     await websocket.send_json(status_message)
                else:
                    print(f"Status Sender: Client {client_id} for task {task_id} disconnected, skipping WS update. Status is in DB.")
            else:
                print(f"Status Sender: Client {client_id} for task {task_id} not found in active connections. Status is in DB.")

        except queue.Empty:
            # Queue is empty, wait a little before checking again
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error in status sender task: {e}")
            # Consider logging the failed send attempt
        # No finally block here, task runs indefinitely until stopped

# --- Lifespan Event Handler ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown events.
    """
    print("FastAPI app startup initiated.")
    # Startup logic: Start the status sender task
    status_sender_task_instance = asyncio.create_task(status_sender_task(status_queue, active_websockets))
    print("Status sender background task scheduled.")

    # Startup logic: Start the download worker thread
    global worker_thread
    worker_thread = threading.Thread(target=download_worker, args=(download_queue, status_queue), daemon=True)
    worker_thread.start()
    print("Download worker thread started.")


    yield # Application is ready to serve requests

    print("FastAPI app shutdown initiated.")
    # Shutdown logic: Signal the worker thread to stop and wait for it
    download_queue.put(None) # Send sentinel to worker
    worker_thread.join() # Wait for worker thread to finish
    print("Download worker thread joined.")

    # Shutdown logic: Cancel the status sender task
    status_sender_task_instance.cancel()
    try:
        await status_sender_task_instance # Wait for cancellation
        print("Status sender background task cancelled.")
    except asyncio.CancelledError:
        print("Status sender background task was already cancelled.")
    except Exception as e:
        print(f"Error during status sender task cancellation: {e}")


# --- FastAPI Application ---
# Pass the lifespan context manager to the FastAPI instance
app = FastAPI(lifespan=lifespan)


# --- WebSocket Endpoint ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = websocket.client # Unique identifier for the client connection

    active_websockets[client_id] = websocket
    print(f"Client connected: {client_id}. Active connections: {len(active_websockets)}")

    try:
        while True:
            data = await websocket.receive_json()
            print(f"Received message from {client_id}: {data}")

            url = data.get("url")

            if not url:
                await websocket.send_json({"status": "failed", "message": "No URL provided."})
                continue

            # Basic URL validation (can be enhanced)
            # Check if it looks like a YouTube URL. Use a slightly more robust check.
            # Consider using regex or a dedicated library for proper URL validation.
            # For this example, let's check for common YouTube patterns in the host or path.
            is_youtube_url = False
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                if parsed_url.scheme in ('http', 'https') and ('youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc):
                     is_youtube_url = True
            except:
                pass # Ignore parsing errors, assume not a valid URL

            if not is_youtube_url:
                 await websocket.send_json({"status": "failed", "message": "Invalid YouTube URL format."})
                 continue


            # Generate a unique task ID
            task_id = str(uuid.uuid4())

            # Insert initial task record into DB with 'pending' status
            try:
                 create_task_in_db(task_id, url)
            except Exception as db_error:
                 print(f"Error inserting task {task_id} into DB: {db_error}")
                 await websocket.send_json({"status": "failed", "message": f"Failed to create task in database: {db_error}"})
                 continue

            # Put the download task in the queue (including task_id and client_id)
            download_queue.put((task_id, url, client_id))
            # Send initial pending status back via WS (including task_id)
            await websocket.send_json({"task_id": task_id, "status": "pending", "message": f"Task {task_id} added to queue for URL {url}."})

    except WebSocketDisconnect as e:
        print(f"Client disconnected: {client_id}. Code: {e.code}, Reason: {e.reason}")
    except Exception as e:
        print(f"WebSocket error for client {client_id}: {e}")
        # Attempt to send a failed status before closing, if possible
        try:
             # If task_id was generated before the error, try to update DB and send status
             if 'task_id' in locals():
                 error_message_text = f"WebSocket error processing task {task_id}: {e}"
                 # Avoid infinite loops if DB update fails
                 try:
                      update_task_status_error_in_db(task_id, "failed", error_message=error_message_text)
                 except:
                      pass # Ignore DB update errors during exception handling

                 # Try sending status via WS
                 try:
                     await websocket.send_json({"task_id": task_id, "status": "failed", "message": error_message_text})
                 except:
                      pass # Ignore WS send errors

             else:
                  # If error happened before task_id generation
                  try:
                     await websocket.send_json({"status": "failed", "message": f"An internal WebSocket error occurred before task creation: {e}"})
                  except:
                      pass # Ignore WS send errors


        except Exception as outer_e:
             print(f"Failed during error handling for client {client_id}: {outer_e}")

    finally:
        # Clean up the client connection
        if client_id in active_websockets:
            del active_websockets[client_id]
        print(f"Client {client_id} removed. Active connections: {len(active_websockets)}")

# --- HTTP Endpoint to Get Task Status by ID ---
class AnalysisRequest(BaseModel):
    url: str
    # You might want to add examType or sourceType here as well if they are relevant for the backend analysis
    # examType: str = "TOEFL"
    # sourceType: str = "url"

@app.post("/analyze-youtube-http")
async def analyze_youtube_http(request_data: AnalysisRequest):
    url = request_data.url
    # You might also want to receive a client_id for logging or specific tracking
    # For HTTP, client_id is typically managed via sessions or JWTs, not directly from connection objects.
    # We'll just use a generic identifier or log it as 'HTTP_CLIENT'

    print(f"Received HTTP request for URL: {url}")

    # Basic URL validation (can be enhanced)
    is_youtube_url = False
    try:
        parsed_url = urlparse(url)
        # Simplified check for demonstration. Use a more robust regex in production.
        if parsed_url.scheme in ('http', 'https') and \
           ("youtube.com" in parsed_url.netloc or "youtu.be" in parsed_url.netloc):
             is_youtube_url = True
    except Exception as e:
        print(f"URL parsing error: {e}")
        pass # Ignore parsing errors

    if not is_youtube_url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL format.")

    # 是否已经存在，是否正在处理
    # Generate a unique task ID
    task_id = str(uuid.uuid4())

    # Insert initial task record into DB with 'pending' status
    try:
        create_task_in_db(task_id, url)
    except Exception as db_error:
        print(f"Error inserting task {task_id} into DB: {db_error}")
        raise HTTPException(status_code=500, detail=f"Failed to create task in database: {db_error}")

    # Put the download task in the queue (including task_id)
    # Since HTTP is stateless, we can't tie it to a specific live WebSocket client_id.
    # The worker will update the `task_statuses` dictionary, which the client will poll.
    download_queue.put_nowait((task_id, url, "HTTP_CLIENT")) # "HTTP_CLIENT" as a placeholder for client_id

    # Send initial pending status back via HTTP response (including task_id)
    return {
        "task_id": task_id,
        "status": "pending",
        "message": f"Task {task_id} added to queue for URL {url}.",
        "polling_endpoint": f"/tasks/{task_id}" # Suggest a polling endpoint
    }


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str = Path(..., title="The ID of the task to get status for")):
    """Retrieves the status and details of a task by its ID."""
    task = get_task_from_db(task_id)
    if task:
        return task
    else:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")
    
@app.get("/tasks/{task_id}/{media_type}")
async def get_task_status_and_media(task_id: str = Path(..., title="The ID of the task to get status for"), media_type: str = Path(..., title="The type of the task's result")):
    """Retrieves the status and details of a task by its ID."""
    if media_type not in ["text", "srt", "audio"]:
        raise HTTPException(status_code=400, detail="Invalid mediaType. Must be 'text' or 'srt' or 'audio'.")

    task = get_task_from_db(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

    if task.get('status') == "success":
        result_str = task.get('result')    
        if not result_str:
            raise HTTPException(status_code=500, detail="Task succeeded but no result data found.")        

        try:
            result_data = json.loads(result_str)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Failed to parse task result data.")

        file_path = None
        if media_type == "audio":
            file_path = result_data.get("audio")
        elif media_type == "srt":
            file_path = result_data.get("srt")
        elif media_type == "text":
            file_path = result_data.get("text")

        if not file_path:
            raise HTTPException(status_code=404, detail=f"Requested mediaType '{media_type}' not found in task result.")

        # Construct the full path to the file
        # IMPORTANT: Ensure 'downloads/' is correctly resolved relative to your project's root
        # or use an absolute path if your `downloads` folder isn't in the same directory as your script.
        full_file_path = os.path.join(os.getcwd(), file_path) # Assuming 'downloads' is in the current working directory

        if not os.path.exists(full_file_path):
            print(f"File not found: {full_file_path}")
            raise HTTPException(status_code=404, detail=f"File for mediaType '{media_type}' not found on server. It might have been deleted or never created properly.")

        # Return the file
        # FastAPI's FileResponse automatically handles content-type based on file extension
        print(f"Returning file: {full_file_path}")
        return FileResponse(full_file_path, media_type="application/octet-stream", filename=os.path.basename(full_file_path))

# Optional: Add a simple HTML page for testing
@app.get("/", response_class=HTMLResponse)
async def get_test_page():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Downloader WebSocket Test with DB</title>
        <style>
            body { font-family: sans-serif; }
            #taskStatusList div { border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; }
            #taskStatusList div strong { display: block; margin-bottom: 5px; }
            #taskDetails { background-color: #f4f4f4; padding: 10px; border: 1px solid #ddd; white-space: pre-wrap; word-wrap: break-word; }
        </style>
    </head>
    <body>
        <h1>YouTube Downloader WebSocket Test with DB</h1>
        <input type="text" id="urlInput" placeholder="Enter YouTube URL" size="50">
        <button onclick="sendUrl()">Download Audio</button>
        <br><br>
        <input type="text" id="taskIdInput" placeholder="Enter Task ID to check" size="30">
        <button onclick="getTaskStatus()">Get Task Status (HTTP)</button>
        <div id="status">Status: Not connected</div>
        <pre id="taskDetails"></pre>

        <h2>Live Task Status Updates</h2>
        <div id="taskStatusList">
            </div>


        <script>
            var ws = null;
            var urlInput = document.getElementById('urlInput');
            var taskIdInput = document.getElementById('taskIdInput');
            var statusDiv = document.getElementById('status');
            var taskDetailsPre = document.getElementById('taskDetails');
            var taskStatusListDiv = document.getElementById('taskStatusList');
            var activeTasks = {}; // Track tasks initiated by this client session

            function connectWebSocket() {
                // Use ws:// for http, wss:// for https
                ws = new WebSocket(`ws://${window.location.host}/ws`);

                ws.onopen = function(event) {
                    statusDiv.innerHTML = "Status: Connected";
                    console.log("WebSocket opened:", event);
                };

                ws.onmessage = function(event) {
                    var data = JSON.parse(event.data);
                    console.log("WebSocket message:", data);

                    if (data.task_id) {
                         updateTaskStatusDisplay(data.task_id, data.status, data.message);
                    } else {
                        // General status message (less common now with task IDs)
                         statusDiv.innerHTML = "Status: " + data.status + (data.message ? " - " + data.message : "");
                    }
                };

                ws.onerror = function(event) {
                    statusDiv.innerHTML = "Status: Error";
                    console.error("WebSocket error:", event);
                };

                ws.onclose = function(event) {
                    statusDiv.innerHTML = "Status: Disconnected. Code: " + event.code + ", Reason: " + event.reason;
                    console.log("WebSocket closed:", event);
                    ws = null;
                    // Optional: Attempt to reconnect after a delay
                    // setTimeout(connectWebSocket, 5000);
                };
            }

            function sendUrl() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    var url = urlInput.value;
                    if (url) {
                        ws.send(JSON.stringify({ "url": url }));
                        statusDiv.innerHTML = "Status: Sending URL...";
                        urlInput.value = ''; // Clear input after sending
                    } else {
                        alert("Please enter a URL.");
                    }
                } else {
                    statusDiv.innerHTML = "Status: WebSocket not connected. Connecting...";
                    connectWebSocket(); // Try connecting if not already
                    // Retry sending after connection is established (simplified)
                    setTimeout(sendUrl, 500); // Retry after short delay
                }
            }

            async function getTaskStatus(taskId = null) {
                const idToFetch = taskId || taskIdInput.value;
                if (!idToFetch) {
                    alert("Please enter a Task ID or process a URL first.");
                    return;
                }
                taskDetailsPre.textContent = 'Fetching task ' + idToFetch + '...';
                try {
                    const response = await fetch(`/tasks/${idToFetch}`);
                    if (!response.ok) {
                        throw new Error('HTTP error ' + response.status);
                    }
                    const taskData = await response.json();
                    taskDetailsPre.textContent = JSON.stringify(taskData, null, 2);
                     // Optionally update the live list display if this task is there
                     updateTaskStatusDisplay(taskData.task_id, taskData.status, taskData.result || taskData.error_message);

                } catch (error) {
                    taskDetailsPre.textContent = 'Error fetching task ' + idToFetch + ': ' + error.message;
                    console.error("Error fetching task:", error);
                }
            }

            function updateTaskStatusDisplay(taskId, status, message) {
                 let taskElement = document.getElementById('task-status-' + taskId);
                 if (!taskElement) {
                     taskElement = document.createElement('div');
                     taskElement.id = 'task-status-' + taskId;
                     taskStatusListDiv.prepend(taskElement); // Add new tasks at the top
                 }
                 // Update the content for this task
                 taskElement.innerHTML = `<strong>Task ID: ${taskId}</strong><br>Status: ${status}${message ? ' - ' + message : ''}`;

                 // Add a link to check via HTTP next to the live update (re-add each time status updates)
                 let httpLink = document.createElement('a');
                 httpLink.href = `/tasks/${taskId}`;
                 httpLink.target = "_blank";
                 httpLink.textContent = ' (Check via HTTP)';
                 taskElement.appendChild(httpLink);
            }


            // Connect when the page loads
            window.onload = connectWebSocket;

        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8091)