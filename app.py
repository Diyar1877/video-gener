import io
import os
import subprocess
import tempfile
from dotenv import load_dotenv
from flask import Flask, request, send_file, send_from_directory, jsonify
from flask_cors import CORS

load_dotenv()

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(__file__)
VIDEO_DIR = os.path.join(BASE_DIR, os.getenv('VIDEO_DIR', 'videos'))
MUSIC_DIR = os.path.join(BASE_DIR, os.getenv('MUSIC_DIR', 'music'))


@app.route('/safety-videos-mp4/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)


@app.route('/music/<path:filename>')
def serve_music(filename):
    return send_from_directory(MUSIC_DIR, filename)


@app.route('/api/merge', methods=['POST'])
def merge_videos():
    data = request.get_json()
    files = data.get('files', [])

    if not files:
        return jsonify({'error': 'Keine Videos ausgewählt'}), 400

    for f in files:
        path = os.path.join(VIDEO_DIR, os.path.basename(f))
        if not os.path.isfile(path):
            return jsonify({'error': f'Datei nicht gefunden: {f}'}), 404

    with tempfile.TemporaryDirectory() as tmpdir:
        # Normalize all videos to same format first
        normalized = []
        for i, f in enumerate(files):
            src = os.path.join(VIDEO_DIR, os.path.basename(f))
            norm_path = os.path.join(tmpdir, f'part{i}.ts')
            r = subprocess.run(
                [
                    'ffmpeg', '-y', '-i', src,
                    '-vf', 'scale=1280:720,fps=30,format=yuv420p',
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-ar', '44100', '-ac', '2', '-b:a', '128k',
                    norm_path,
                ],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                return jsonify({'error': f'Fehler bei {f}', 'details': r.stderr}), 500
            normalized.append(norm_path)

        # Create concat list from normalized files
        list_path = os.path.join(tmpdir, 'list.txt')
        with open(list_path, 'w') as fh:
            for p in normalized:
                fh.write(f"file '{p}'\n")

        output_path = os.path.join(tmpdir, 'output.mp4')

        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return jsonify({'error': 'FFmpeg Fehler', 'details': result.stderr}), 500

        with open(output_path, 'rb') as f:
            buf = io.BytesIO(f.read())

    return send_file(
        buf,
        mimetype='video/mp4',
        as_attachment=True,
        download_name='safety2-praesentation.mp4',
    )


if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host=host, port=port, debug=debug)
