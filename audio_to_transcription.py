import os
import subprocess
import whisper
import json
import re
from urllib.parse import urlparse, parse_qs

FFMPEG_PATH = r"C:\ffmpeg\bin"

#Funções auxiliares
def get_video_id(url):
    query = urlparse(url).query
    return parse_qs(query)["v"][0]

def run_command(cmd):
    subprocess.run(cmd, check=True)

def get_audio_duration(input_file):
    cmd = [
        "ffprobe",
        "-i", input_file,
        "-show_entries", "format=duration",
        "-v", "quiet",
        "-of", "csv=p=0"
    ]
    return float(subprocess.check_output(cmd).decode().strip())

def download_audio(url, output_file):
    cmd = [
        "yt-dlp",
        "--no-check-certificates",
        "--ffmpeg-location", FFMPEG_PATH,
        "--force-ipv4",
        "--retries", "10",
        "--fragment-retries", "10",
        "-f", "bestaudio",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "-o", output_file,
        url
    ]
    run_command(cmd)

def cut_audio(input_file, output_file, start=None, end=None):
    cmd = ["ffmpeg", "-y"]

    if start is not None:
        cmd += ["-ss", str(start)]

    cmd += ["-i", input_file]

    if end is not None:
        duration = end - start
        cmd += ["-t", str(duration)]

    cmd += [
        "-ac", "1",
        "-ar", "16000",
        output_file
    ]
    run_command(cmd)

def segment_audio_overlap(input_file, output_folder, segment_time=90, overlap=15, prefix="seg"):
    os.makedirs(output_folder, exist_ok=True)
    duration = get_audio_duration(input_file)

    start = 0
    index = 0

    while start < duration:
        end = min(start + segment_time, duration)

        output_file = os.path.join(
            output_folder,
            f"{prefix}_seg_{index:03d}.wav"
        )

        cut_audio(input_file, output_file, start, end)

        start += (segment_time - overlap)
        index += 1

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()

def is_event_candidate(text):
    keywords = [
        "gol", "gooool", "goool", "marcou", "balançou",
        "penalti", "pênalti",
        "cartão", "expulso", "amarelo", "vermelho",
    ]
    text = text.lower()
    return any(k in text for k in keywords)

#Transcrição de áudio usando Whisper
def transcribe_audio_file(audio_file, model):
    result = model.transcribe(audio_file, language="pt")
    return result

def save_transcription_json(data, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def transcribe_segments(segments_folder, output_folder, model, video_id, segment_length, overlap):
    os.makedirs(output_folder, exist_ok=True)

    for file in sorted(os.listdir(segments_folder)):

        if file.endswith(".wav"):

            audio_path = os.path.join(segments_folder, file)

            print(f"Transcrevendo {file}...")

            result = transcribe_audio_file(audio_path, model)

            seg_index = int(file.split("_")[-1].replace(".wav", ""))

            # cálculo correto com overlap
            step = segment_length - overlap
            segment_start = seg_index * step
            segment_end = segment_start + segment_length

            enriched_segments = []

            for seg in result["segments"]:
                enriched_segments.append({
                    "start": seg["start"] + segment_start,
                    "end": seg["end"] + segment_start,
                    "duration": seg["end"] - seg["start"],
                    "text": seg["text"],
                    "clean_text": normalize_text(seg["text"]),
                    "is_candidate": is_event_candidate(seg["text"])
                })

            full_text = " ".join([s["text"] for s in result["segments"]])

            transcription_data = {
                "video_id": video_id,
                "segment_file": file,
                "segment_start": segment_start,
                "segment_end": segment_end,
                "full_text": full_text,
                "transcription": enriched_segments
            }

            json_name = file.replace(".wav", ".json")

            save_transcription_json(
                transcription_data,
                os.path.join(output_folder, json_name)
            )

def transcribe_single(audio_file, output_folder, model):
    os.makedirs(output_folder, exist_ok=True)

    print("Transcrevendo áudio completo...")

    result = transcribe_audio_file(audio_file, model)

    enriched_segments = []

    for seg in result["segments"]:
        enriched_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "duration": seg["end"] - seg["start"],
            "text": seg["text"],
            "clean_text": normalize_text(seg["text"]),
            "is_candidate": is_event_candidate(seg["text"])
        })

    transcription_data = {
        "full_text": " ".join([s["text"] for s in result["segments"]]),
        "transcription": enriched_segments
    }

    json_file = os.path.join(
        output_folder,
        os.path.basename(audio_file).replace(".wav", ".json")
    )

    save_transcription_json(transcription_data, json_file)

#Função principal
def main():
    #url = "https://www.youtube.com/watch?v=x7YCIZCq89U" #Vasco x Palmeiras
    url = "https://www.youtube.com/watch?v=MrGb98VFBXo" #Vasco x Paysandu

    start_time = 0
    end_time = 600
    download_audio_flag = False
    segment_audio_flag = True
    segment_length = 90
    overlap = 15

    video_id = get_video_id(url)

    base_folder = "dataset"
    raw_folder = os.path.join(base_folder, "audio_raw")
    cut_folder = os.path.join(base_folder, "audio_cut")
    seg_folder = os.path.join(base_folder, "segments")
    trans_folder = os.path.join(base_folder, "transcriptions")

    os.makedirs(raw_folder, exist_ok=True)
    os.makedirs(cut_folder, exist_ok=True)
    os.makedirs(seg_folder, exist_ok=True)
    os.makedirs(trans_folder, exist_ok=True)

    print("Carregando modelo Whisper...")
    model = whisper.load_model("large")  # tiny, base, small, medium, large

    if download_audio_flag:
        raw_audio = os.path.join(raw_folder, f"{video_id}_full.wav")
        print("Baixando áudio...")
        download_audio(url, raw_audio)

        cut_audio_file = os.path.join(
            cut_folder,
            f"{video_id}_{start_time}_{end_time}.wav"
        )

        print("Cortando trecho do áudio...")
        cut_audio(raw_audio, cut_audio_file, start_time, end_time)

    else:
        #cut_audio_file = "dataset/audio_cut/game_segment_vasco_palmeiras.wav"
        cut_audio_file = "dataset/audio_cut/game_segment_vasco_paysandu.wav"
        print("Pulando download. Usando áudio existente.")

    if segment_audio_flag:
        print("Segmentando áudio com overlap...")

        segment_audio_overlap(
            cut_audio_file,
            seg_folder,
            segment_length,
            overlap,
            video_id
        )

        print("Transcrevendo segmentos...")

        transcribe_segments(
            seg_folder,
            trans_folder,
            model,
            video_id,
            segment_length,
            overlap
        )

    else:
        print("Transcrevendo áudio completo...")

        transcribe_single(
            cut_audio_file,
            trans_folder,
            model
        )

    print("Pipeline finalizado!")

if __name__ == "__main__":
    main()