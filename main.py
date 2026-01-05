import time, os, feedparser, requests, psycopg2
from google import genai 
import youtube_transcript_api

# --- CONFIGURAZIONE ---
DB_URL = os.getenv("DATABASE_URL")
GEMINI_KEY = os.getenv("GEMINI_KEY")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

client = genai.Client(api_key=GEMINI_KEY)

def init_db():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS videos (video_id TEXT PRIMARY KEY, title TEXT, summary TEXT)")
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Errore Database: {e}")

def get_summary(video_id, title):
    try:
        # TENTATIVO DI ACCESSO DIRETTO ALLA CLASSE
        from youtube_transcript_api import YouTubeTranscriptApi as api
        srt = api.get_transcript(video_id, languages=['it', 'en'])
        
        text = " ".join([t['text'] for t in srt])[:10000]
        prompt = f"Riassumi il video '{title}' in 5 punti chiave: {text}"
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        print(f"⚠️ Errore trascrizione per {video_id}: {e}")
        return "Riassunto non disponibile: errore tecnico nel recupero del testo."

def check_youtube():
    print("--- Controllo nuovi video in corso... ---")
    init_db()
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
    except Exception as e:
        print(f"❌ Errore DB: {e}")
        return

    for channel_id in CHANNELS:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:3]:
            video_id = entry.yt_videoid
            cur.execute("SELECT video_id FROM videos WHERE video_id = %s", (video_id,))
            if not cur.fetchone():
                print(f"✨ Nuovo video trovato: {entry.title}")
                summary = get_summary(video_id, entry.title)
                msg = f"📺 VIDEO: {entry.title}\n\n📝 RIASSUNTO:\n{summary}\n\n🔗 {entry.link}"
                requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data={"chat_id": TG_CHAT_ID, "text": msg})
                cur.execute("INSERT INTO videos (video_id, title, summary) VALUES (%s, %s, %s)", (video_id, entry.title, summary))
                conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("🚀 VERSIONE 5: Bot avviato correttamente!") 
    while True:
        try:
            check_youtube()
        except Exception as e:
            print(f"🚨 Errore ciclo: {e}")
        time.sleep(600)