import os
import json
import subprocess

#Configurações e Constantes
VIDEO_URL = "https://www.youtube.com/watch?v=x7YCIZCq89U" #Vasco x Palmeiras

BASE_FOLDER = "dataset"
VIDEO_FOLDER = os.path.join(BASE_FOLDER, "video")
EVENT_FOLDER = os.path.join(BASE_FOLDER, "final_events.json")
CLIP_FOLDER = os.path.join(BASE_FOLDER, "clips")

VIDEO_FILE = os.path.join(VIDEO_FOLDER, "video.mp4")

MAX_CLIP_DURATION = 20  # duração máxima de cada clip

#Funções auxiliares
def run_command(cmd):
    subprocess.run(cmd, check=True)

def download_video(url, output_file):
    cmd = [
        "yt-dlp",
        "--no-check-certificates",
        "--force-ipv4",
        "--cookies-from-browser", "edge",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "-o", output_file,
        url
    ]
    run_command(cmd)

def cut_video(input_video, output_video, start, end):
    duration = end - start

    cmd = [
        "ffmpeg",
        "-y",
        "-ss", str(start),
        "-i", input_video,
        "-t", str(duration),
        "-c:v", "libx264",
        "-c:a", "aac",
        output_video
    ]

    run_command(cmd)


def load_all_events(event_file):
    with open(event_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("events", [])

def get_event_window(event):
    if event["event_type"] == "gol":
        return 7, 12
    else:
        return 5, 8

def generate_clips(events, video_file, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    clip_paths = []

    for i, event in enumerate(events):

        pre, post = get_event_window(event)

        start = max(0, event["start_time"] - pre)
        end = event["end_time"] + post

        # limitar duração
        if (end - start) > MAX_CLIP_DURATION:
            end = start + MAX_CLIP_DURATION

        output_clip = os.path.join(
            output_folder,
            f"clip_{i:03d}_{event['event_type']}.mp4"
        )

        print(f"Cortando clip {i} ({event['event_type']}) [{start:.2f} - {end:.2f}]")

        cut_video(video_file, output_clip, start, end)

        clip_paths.append(output_clip)

    return clip_paths

def concatenate_clips(clip_paths, output_file):
    list_file = "clips_list.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for clip in clip_paths:
            f.write(f"file '{os.path.abspath(clip)}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file,
        "-c:v", "libx264",
        "-c:a", "aac",
        output_file
    ]

    run_command(cmd)

    os.remove(list_file)

def main():

    # 1. Baixar vídeo (opcional)
    # download_video(VIDEO_URL, VIDEO_FILE)

    # 2. Carregar eventos
    print("Carregando eventos...")
    events = load_all_events(EVENT_FOLDER)

    # 3. Ordenar e limpar
    events = sorted(events, key=lambda x: x["start_time"])

    print(f"Eventos finais: {len(events)}")

    # 4. Gerar clips
    clip_paths = generate_clips(events, VIDEO_FILE, CLIP_FOLDER)

    # 5. Concatenar highlight
    output_highlight = os.path.join(BASE_FOLDER, "highlight.mp4")

    print("Gerando highlight final...")
    concatenate_clips(clip_paths, output_highlight)

    print("Pipeline finalizado com sucesso!")


if __name__ == "__main__":
    main()