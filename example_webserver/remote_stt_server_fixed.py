#!/usr/bin/env python3
"""
Remote STT Server for SSH environments - Fixed Version
Captures audio from local browser and processes STT on remote server
Fixes: WebSocket reconnection issues and audio processing stability
"""

import asyncio
import threading
import json
import websockets
import numpy as np
from scipy.signal import resample
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys
import time

# Add the parent directory to the path to import RealtimeSTT
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from RealtimeSTT import AudioToTextRecorder
except ImportError:
    print("RealtimeSTT not found. Please install it first:")
    print("pip install RealtimeSTT")
    sys.exit(1)

# Configuration - Updated for port mapping (Internal 8000 -> External 11195)
WEB_SERVER_PORT = 8000  # Use port 8000 for external port mapping (11195)
WEBSOCKET_PORT = 8002  # Changed from 8001 to avoid nginx conflict
HOST = "0.0.0.0"  # Listen on all interfaces for SSH access

# STT Configuration
end_of_sentence_detection_pause = 0.45
unknown_sentence_detection_pause = 0.7
mid_sentence_detection_pause = 2.0

recorder = None
recorder_ready = threading.Event()
connected_clients = set()
prev_text = ""
audio_chunks_received = 0
last_audio_time = 0

def preprocess_text(text):
    """Clean and format the transcribed text"""
    # Remove leading whitespaces
    text = text.lstrip()
    
    # Remove starting ellipses if present
    if text.startswith("..."):
        text = text[3:]
    
    # Remove any leading whitespaces again after ellipses removal
    text = text.lstrip()
    
    # Uppercase the first letter
    if text:
        text = text[0].upper() + text[1:]
    
    return text

async def broadcast_to_clients(message):
    """Send message to all connected WebSocket clients"""
    if connected_clients:
        disconnected_clients = set()
        for client in connected_clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                print(f"[BROADCAST] Error sending to client: {e}")
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        connected_clients.difference_update(disconnected_clients)

def text_detected(text):
    """Callback for real-time transcription updates"""
    global prev_text
    
    text = preprocess_text(text)
    
    # Adjust silence detection based on text ending
    sentence_end_marks = ['.', '!', '?', '。']
    if text.endswith("..."):
        recorder.post_speech_silence_duration = mid_sentence_detection_pause
    elif text and text[-1] in sentence_end_marks and prev_text and prev_text[-1] in sentence_end_marks:
        recorder.post_speech_silence_duration = end_of_sentence_detection_pause
    else:
        recorder.post_speech_silence_duration = unknown_sentence_detection_pause
    
    prev_text = text
    
    # Send real-time update to clients
    message = json.dumps({
        'type': 'realtime',
        'text': text
    })
    
    # Schedule the broadcast in a thread-safe way
    if connected_clients:
        threading.Thread(target=lambda: asyncio.run(broadcast_to_clients(message)), daemon=True).start()
    
    print(f"\r[STT] {text}", flush=True, end='')

def decode_and_resample(audio_data, original_sample_rate, target_sample_rate):
    """Decode and resample audio data"""
    # Decode 16-bit PCM data to numpy array
    audio_np = np.frombuffer(audio_data, dtype=np.int16)
    
    # Calculate the number of samples after resampling
    num_original_samples = len(audio_np)
    num_target_samples = int(num_original_samples * target_sample_rate / original_sample_rate)
    
    # Resample the audio
    resampled_audio = resample(audio_np, num_target_samples)
    
    return resampled_audio.astype(np.int16).tobytes()

async def websocket_handler(websocket):
    """Handle WebSocket connections for audio streaming - Enhanced with better error handling"""
    global audio_chunks_received, last_audio_time
    
    client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    print(f"[WS] Client {client_id} connected")
    connected_clients.add(websocket)
    
    # Reset audio processing state for new connection
    local_chunks_received = 0
    
    try:
        async for message in websocket:
            if not recorder_ready.is_set():
                print(f"[WS] Recorder not ready for client {client_id}")
                continue
            
            local_chunks_received += 1
            audio_chunks_received += 1
            current_time = time.time()
            
            # Parse the message (metadata + audio data)
            try:
                metadata_length = int.from_bytes(message[:4], byteorder='little')
                metadata_json = message[4:4+metadata_length].decode('utf-8')
                metadata = json.loads(metadata_json)
                sample_rate = metadata['sampleRate']
                chunk = message[4+metadata_length:]
                
                # Log every 100 chunks for debugging
                if local_chunks_received % 100 == 0:
                    print(f"\n[WS] Client {client_id}: {local_chunks_received} chunks, {len(chunk)} bytes, {sample_rate}Hz")
                
                # Resample and feed to recorder
                resampled_chunk = decode_and_resample(chunk, sample_rate, 16000)
                recorder.feed_audio(resampled_chunk)
                
                last_audio_time = current_time
                
            except Exception as e:
                print(f"[WS] Error processing audio chunk from {client_id}: {e}")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"[WS] Client {client_id} disconnected: {e}")
    except Exception as e:
        print(f"[WS] WebSocket error for client {client_id}: {e}")
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] Client {client_id} removed (processed {local_chunks_received} chunks)")

def recorder_thread():
    """Initialize and run the STT recorder"""
    global recorder, prev_text
    
    print("[STT] Initializing RealtimeSTT...")
    
    # Enhanced recorder configuration for better stability
    recorder_config = {
        'spinner': False,
        'use_microphone': False,  # We'll feed audio manually
        'model': 'small.en',
        'realtime_model_type': 'tiny.en',
        'language': 'en',
        'silero_sensitivity': 0.05,
        'webrtc_sensitivity': 3,
        'post_speech_silence_duration': unknown_sentence_detection_pause,
        'min_length_of_recording': 1.1,
        'min_gap_between_recordings': 0,
        'enable_realtime_transcription': True,
        'realtime_processing_pause': 0.02,
        'on_realtime_transcription_update': text_detected,
        'silero_deactivity_detection': True,
        'early_transcription_on_silence': 0.2,
        'beam_size': 5,
        'beam_size_realtime': 3,
        'no_log_file': True,
        'initial_prompt': 'Add periods only for complete sentences. Use ellipsis (...) for unfinished thoughts or unclear endings.'
    }
    
    try:
        recorder = AudioToTextRecorder(**recorder_config)
        print("[STT] RealtimeSTT initialized successfully")
        recorder_ready.set()
        
        def process_full_sentence(full_sentence):
            """Process complete sentences"""
            print(f"\n[STT] Full sentence: {full_sentence}")
            full_sentence = preprocess_text(full_sentence)
            prev_text = ""
            
            # Send full sentence to clients
            message = json.dumps({
                'type': 'fullSentence',
                'text': full_sentence
            })
            
            # Schedule the broadcast in a thread-safe way
            if connected_clients:
                threading.Thread(target=lambda: asyncio.run(broadcast_to_clients(message)), daemon=True).start()
        
        # Start the transcription loop with error recovery
        print("[STT] Starting transcription loop...")
        while True:
            try:
                recorder.text(process_full_sentence)
            except Exception as e:
                print(f"[STT] Error in transcription loop: {e}")
                time.sleep(1)  # Brief pause before retrying
                
    except Exception as e:
        print(f"[STT] Error initializing recorder: {e}")
        print("[STT] Trying with fallback configuration...")
        
        # Fallback configuration
        fallback_config = {
            'spinner': False,
            'use_microphone': False,
            'model': 'base.en',
            'language': 'en',
            'enable_realtime_transcription': False,
            'on_realtime_transcription_update': text_detected,
            'no_log_file': True
        }
        
        try:
            recorder = AudioToTextRecorder(**fallback_config)
            print("[STT] Fallback recorder initialized")
            recorder_ready.set()
            
            while True:
                try:
                    result = recorder.text()
                    if result:
                        print(f"[STT] Fallback result: {result}")
                        # Send to clients
                        message = json.dumps({
                            'type': 'fullSentence',
                            'text': result
                        })
                        if connected_clients:
                            threading.Thread(target=lambda: asyncio.run(broadcast_to_clients(message)), daemon=True).start()
                except Exception as e:
                    print(f"[STT] Error in fallback loop: {e}")
                    time.sleep(1)
        except Exception as e:
            print(f"[STT] Fallback recorder also failed: {e}")

class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler to serve the web interface"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs)
    
    def end_headers(self):
        # Add CORS headers for cross-origin requests
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def start_web_server():
    """Start the HTTP server for the web interface"""
    server = HTTPServer((HOST, WEB_SERVER_PORT), CustomHTTPRequestHandler)
    print(f"[WEB] Server started on http://{HOST}:{WEB_SERVER_PORT}")
    server.serve_forever()

def audio_monitor():
    """Monitor audio reception and connection status"""
    global audio_chunks_received, last_audio_time
    
    while True:
        time.sleep(10)
        current_time = time.time()
        client_count = len(connected_clients)
        
        if last_audio_time > 0:
            time_since_last = current_time - last_audio_time
            print(f"\n[MONITOR] Clients: {client_count}, Audio chunks: {audio_chunks_received}, Last audio: {time_since_last:.1f}s ago")
        else:
            print(f"\n[MONITOR] Clients: {client_count}, Audio chunks: {audio_chunks_received}, No audio received yet")

def main():
    """Main function to start all services"""
    print("=" * 60)
    print("Remote STT Server for SSH Environments - Fixed Version")
    print("=" * 60)
    print(f"Web Interface: http://{HOST}:{WEB_SERVER_PORT}/remote_stt_client_fixed.html")
    print(f"External Access: http://YOUR_EXTERNAL_IP:11195/remote_stt_client_fixed.html")
    print(f"WebSocket Server: ws://{HOST}:{WEBSOCKET_PORT}")
    print("=" * 60)
    
    # Start the recorder thread
    recorder_thread_obj = threading.Thread(target=recorder_thread, daemon=True)
    recorder_thread_obj.start()
    
    # Start audio monitor
    monitor_thread = threading.Thread(target=audio_monitor, daemon=True)
    monitor_thread.start()
    
    # Wait for recorder to be ready
    print("[MAIN] Waiting for STT recorder to be ready...")
    recorder_ready.wait()
    print("[MAIN] STT Recorder is ready")
    
    # Start the web server in a separate thread
    web_server_thread = threading.Thread(target=start_web_server, daemon=True)
    web_server_thread.start()
    
    # Start the WebSocket server
    print("[MAIN] Starting WebSocket server...")
    
    async def run_server():
        # Use the correct websockets.serve syntax for newer versions
        async with websockets.serve(websocket_handler, HOST, WEBSOCKET_PORT):
            print("[MAIN] All servers started successfully!")
            print("[MAIN] Fixed version with improved reconnection handling")
            print("[MAIN] Press Ctrl+C to stop the server.")
            # Keep the server running
            await asyncio.Future()  # Run forever
    
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\n[MAIN] Shutting down servers...")

if __name__ == '__main__':
    main()
