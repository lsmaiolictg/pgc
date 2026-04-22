import json
import os
from openai import OpenAI
import logging
import re

#Configurações e Constantes
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

client = OpenAI(
    api_key="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",
    base_url="https://api.groq.com/openai/v1"
)

#Funções auxiliares
def safe_json_parse(content):
    if not content:
        return {"events": []}

    content = content.strip()

    try:
        return json.loads(content)
    except:
        pass

    content = re.sub(r"```json|```", "", content).strip()

    try:
        return json.loads(content)
    except:
        pass

    matches = re.findall(r"\{.*?\}", content, re.DOTALL)

    for m in matches:
        try:
            return json.loads(m)
        except:
            continue

    return {"events": []}

#Deteção de eventos a partir do texto completo do segmento de 90s
def detect_events_full_text(full_text):
    prompt = f"""
            Você é um especialista em narração esportiva.

            Sua tarefa é identificar SOMENTE eventos AO VIVO (momento exato do lance acontecendo).

            ⚠️ REGRAS MUITO IMPORTANTES:

            ✅ Um evento válido acontece DURANTE a jogada
            Exemplo:
            - "GOOOOOL!!!"
            - "Bateu pro gol!"
            - "É pênalti!"

            ❌ NÃO é evento:
            - Comentários depois ("no gol que ele fez")
            - Análises ("foi mérito dele")
            - Replays
            - Jogadas que NÃO resultaram em gol
            - Frases no passado

            🚨 REGRA DE OURO:
            Se a frase estiver no PASSADO → NÃO é evento

            🚨 REGRA DE OURO 2:
            Se não houver emoção / ação → NÃO é evento

            🚨 REGRA DE OURO 3:
            Se não dá pra imaginar o lance acontecendo naquele momento → NÃO é evento

            ---

            TEXTO:
            {full_text}

            ---

            RESPONDA EM JSON:

            {{
            "events": [
                {{
                "event_type": "gol | penalti",
                "text_ref": "trecho exato onde o evento acontece AO VIVO",
                "confidence": 0.0-1.0
                }}
            ]
            }}
            """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Se não houver evento AO VIVO, retorne lista vazia."},
            {"role": "user", "content": prompt}
        ]
    )

    return safe_json_parse(response.choices[0].message.content)

def find_best_segment(event_text, segments):

    event_text = event_text.lower()

    best_match = None
    best_score = 0

    for seg in segments:

        seg_text = seg["text"].lower()

        # score simples por interseção de palavras
        common = set(event_text.split()) & set(seg_text.split())
        score = len(common)

        if score > best_score:
            best_score = score
            best_match = seg

    return best_match

def expand_window(center_seg, segments, window=10):

    start = center_seg["start"]
    end = center_seg["end"]

    for seg in segments:

        if abs(seg["start"] - center_seg["start"]) <= window:
            start = min(start, seg["start"])

        if abs(seg["end"] - center_seg["end"]) <= window:
            end = max(end, seg["end"])

    return start, end

def select_best_events(events, window=40):

    if not events:
        return []

    events = sorted(events, key=lambda x: x["start_time"])

    groups = []
    current = [events[0]]

    for e in events[1:]:

        if e["start_time"] - current[-1]["start_time"] <= window:
            current.append(e)
        else:
            groups.append(current)
            current = [e]

    groups.append(current)

    final = []

    for g in groups:
        best = max(g, key=lambda x: x["confidence"])
        final.append(best)

    return final

def merge_global_events(all_events, tolerance=5):
    if not all_events:
        return []

    for e in all_events:
        print(e)

    all_events = sorted(all_events, key=lambda x: x["start_time"])

    merged = []
    current = all_events[0].copy()

    for e in all_events[1:]:
        same_type = e["event_type"] == current["event_type"]
        overlap = (
            e["start_time"] <= current["end_time"] + tolerance
            and e["end_time"] >= current["start_time"] - tolerance
        )

        if same_type and overlap:
            current["start_time"] = min(current["start_time"], e["start_time"])
            current["end_time"] = max(current["end_time"], e["end_time"])
            current["confidence"] = max(current["confidence"], e["confidence"])
            print(f"  → MERGEADO: {current['start_time']}-{current['end_time']}")
        else:
            merged.append(current)
            current = e.copy()
            print(f"  → SEPARADO")

    merged.append(current)
    return merged

def process_full_game(input_folder, output_file):

    all_events = []

    for file in os.listdir(input_folder):

        if not file.endswith(".json"):
            continue

        path = os.path.join(input_folder, file)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for e in data.get("events", []):
            all_events.append(e)

    final_events = merge_global_events(all_events)

    output_data = {
        "events": final_events
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

#Função para processar cada arquivo de transcrição e detectar eventos
def process_transcription_file(input_file, output_folder):

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    full_text = data["full_text"]
    segments = data["transcription"]

    #Detecta eventos no texto completo
    detection = detect_events_full_text(full_text)
    events = detection.get("events", [])

    if not events:
        return
    detected_events = []

    #Para cada evento detectado, encontra o melhor segmento correspondente e expande a janela para capturar o lance completo
    for ev in events:
        match = find_best_segment(ev["text_ref"], segments)

        if not match:
            continue

        start, end = expand_window(match, segments)

        detected_events.append({
            "event_type": ev["event_type"],
            "start_time": start,
            "end_time": end,
            "confidence": ev.get("confidence", 0)
        })

    #Remove eventos duplicados devido ao overlap dos segmentos e consolida resultados próximos
    final_events = select_best_events(detected_events)

    output_data = {
        "video_id": data["video_id"],
        "segment_file": data["segment_file"],
        "events": final_events
    }

    os.makedirs(output_folder, exist_ok=True)

    output_file = os.path.join(
        output_folder,
        os.path.basename(input_file)
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

def process_all_transcriptions(input_folder, output_folder):

    for file in os.listdir(input_folder):
        if file.endswith(".json"):

            logging.info(f"Processando {file}")

            process_transcription_file(
                os.path.join(input_folder, file),
                output_folder
            )

#Função principal
def main():
    input_folder = "dataset/transcriptions"
    output_folder = "dataset/events"

    process_all_transcriptions(input_folder, output_folder)

    process_full_game(
        output_folder,
        "dataset/final_events.json"
    )

    logging.info("Finalizado!")

if __name__ == "__main__":
    main()