import time, os, feedparser, requests, psycopg2
from google import genai 
from youtube_transcript_api import YouTubeTranscriptApi

# --- CONFIGURAZIONE ---
DB_URL = os.getenv("DATABASE_URL")
GEMINI_KEY = os.getenv("GEMINI_KEY")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

client = genai.Client(api_key=GEMINI_KEY)

def get_summary(video_id, title):
    try:
        cookie_path = "cookies.txt"
        
        # Tentativo di recupero con cookies e gestione migliorata
        if os.path.exists(cookie_path):
            print(f"🍪 Uso i cookies per {video_id}...")
            # Usiamo list_transcripts che è più robusto con i cookies
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id, cookies=cookie_path)
        else:
            print(f"⚠️ cookies.txt non trovato, provo senza...")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Cerchiamo la trascrizione (qualsiasi lingua, preferendo it/en/es)
        try:
            srt = transcript_list.find_transcript(['it', 'en', 'es'])
        except:
            srt = next(iter(transcript_list))
            
        transcript = srt.fetch()
        text = " ".join([t['text'] for t in transcript])[:10000]
        
        prompt = f"Riassumi il video '{title}' in ITALIANO in 5 punti chiave: {text}"
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        # Log più dettagliato dell'errore
        error_msg = str(e).split('\n')[0] 
        print(f"⚠️ Errore per {video_id}: {error_msg}")
        return f"Riassunto non disponibile (Errore YouTube: {error_msg})"

def check_youtube():
    print("--- Controllo nuovi video in corso... ---")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS videos (video_id TEXT PRIMARY KEY, title TEXT, summary TEXT)")
        conn.commit()
    except Exception as e:
        print(f"❌ Errore DB: {e}")
        return

    for channel_id in CHANNELS:
        feed = feedparser.parse(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")
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
                print(f"✅ Messaggio inviato per: {entry.title}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("🚀 VERSIONE 9: Bot avviato con protezione aggiornata!") 
    while True:
        try:
            check_youtube()
        except Exception as e:
            print(f"🚨 Errore: {e}")
        time.sleep(600)
