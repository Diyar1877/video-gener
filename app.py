import os
import subprocess
import tempfile
from flask import Flask, request, send_file, send_from_directory, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

VIDEO_DIR = os.path.join(os.path.dirname(__file__), 'videos')


@app.route('/safety-videos-mp4/<path:filename>')
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)


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
        list_path = os.path.join(tmpdir, 'list.txt')
        with open(list_path, 'w') as fh:
            for f in files:
                abs_path = os.path.abspath(os.path.join(VIDEO_DIR, os.path.basename(f)))
                fh.write(f"file '{abs_path}'\n")

        output_path = os.path.join(tmpdir, 'output.mp4')

        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_path,
                '-c', 'copy',
                output_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return jsonify({'error': 'FFmpeg Fehler', 'details': result.stderr}), 500

        return send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name='safety2-praesentation.mp4',
        )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
