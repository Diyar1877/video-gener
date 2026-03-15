import io
import os
import subprocess
import tempfile
from flask import Flask, request, send_file, send_from_directory, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

VIDEO_DIR = os.path.join(os.path.dirname(__file__), 'videos')
MUSIC_DIR = os.path.join(os.path.dirname(__file__), 'music')
MUSIC_INTRO = os.path.join(MUSIC_DIR, 'intro.mp3')
MUSIC_LOOP = os.path.join(MUSIC_DIR, 'loop.mp3')
MUSIC_OUTRO = os.path.join(MUSIC_DIR, 'outro.mp3')


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

        # Get durations
        durations = []
        for p in normalized:
            probe = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', p],
                capture_output=True, text=True,
            )
            durations.append(float(probe.stdout.strip()))

        intro_dur = durations[0] if durations else 0
        outro_dur = durations[-1] if durations else 0
        total_dur = sum(durations)
        middle_dur = total_dur - intro_dur - outro_dur

        # Build music track: intro(30s) + loop(85s repeating) + outro(25s)
        output_path = os.path.join(tmpdir, 'output.mp4')

        result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_path,
                '-i', MUSIC_INTRO,
                '-stream_loop', '-1',
                '-i', MUSIC_LOOP,
                '-i', MUSIC_OUTRO,
                '-filter_complex',
                f'[1:a]volume=0.08[intro];'
                f'[2:a]volume=0.08,atrim=0:{middle_dur}[mid];'
                f'[3:a]volume=0.08[outro];'
                f'[intro][mid][outro]concat=n=3:v=0:a=1[music];'
                f'[0:a]volume=1.0[voice];'
                f'[voice][music]amix=inputs=2:duration=first:normalize=0[aout]',
                '-map', '0:v',
                '-map', '[aout]',
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
    app.run(host='0.0.0.0', port=5000, debug=True)
