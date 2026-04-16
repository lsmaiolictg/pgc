import subprocess
import os

FFMPEG_PATH = r"C:\ffmpeg\bin"

def run(cmd):
    subprocess.run(cmd, check=True)

def download_audio_segment(url, start, end, output):
    cmd = [
        "yt-dlp",
        "--ffmpeg-location", FFMPEG_PATH,

        "--no-check-certificates",

        "--cookies", "cookies.txt", 

        "--download-sections", f"*{start}-{end}",
        "-f", "bestaudio",
        "-x",
        "--audio-format", "wav",
        "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",

        "-o", output,
        url
    ]
    run(cmd)

def main():

    url = "https://www.youtube.com/watch?v=x7YCIZCq89U" #Vasco x Palmeiras

    start_time = "03:24:20"
    end_time   = "03:37:00"

    os.makedirs("test_audio", exist_ok=True)
    output_file = "test_audio/game_segment.%(ext)s"
    print("Baixando apenas o trecho do jogo...")

    download_audio_segment(
        url,
        start_time,
        end_time,
        output_file
    )

    print("Download finalizado.")

if __name__ == "__main__":
    main()