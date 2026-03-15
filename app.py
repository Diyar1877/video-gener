import hashlib
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
CACHE_DIR = os.path.join(BASE_DIR, 'cache')
os.makedirs(CACHE_DIR, exist_ok=True)


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

    # Cache-Key aus Dateinamen erzeugen
    cache_key = hashlib.md5('|'.join(files).encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f'{cache_key}.mp4')

    # Wenn schon gecached, sofort ausliefern
    if os.path.isfile(cache_path):
        return send_file(
            cache_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name='safety2-praesentation.mp4',
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        list_path = os.path.join(tmpdir, 'list.txt')
        with open(list_path, 'w') as fh:
            for f in files:
                src = os.path.join(VIDEO_DIR, os.path.basename(f))
                fh.write(f"file '{src}'\n")

        output_path = os.path.join(tmpdir, 'output.mp4')

        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_path,
                '-c', 'copy',
                '-movflags', '+faststart',
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return jsonify({'error': 'FFmpeg Fehler', 'details': result.stderr}), 500

        # In Cache speichern
        os.rename(output_path, cache_path)

    return send_file(
        cache_path,
        mimetype='video/mp4',
        as_attachment=True,
        download_name='safety2-praesentation.mp4',
    )


if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host=host, port=port, debug=debug)
