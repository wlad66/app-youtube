import time, os, feedparser, requests, psycopg2
from google import genai 
# Importazione specifica della classe per evitare l'errore "no attribute"
from youtube_transcript_api import YouTubeTranscriptApi as YT_API

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
        
        # Usiamo il riferimento diretto caricato sopra
        if os.path.exists(cookie_path):
            print(f"🍪 Uso i cookies per {video_id}...")
            transcript_list = YT_API.list_transcripts(video_id, cookies=cookie_path)
        else:
            print(f"⚠️ cookies.txt non trovato, provo senza...")
            transcript_list = YT_API.list_transcripts(video_id)
        
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
        print(f"⚠️ Errore per {video_id}: {e}")
        return f"Riassunto non disponibile (Errore: {str(e)[:50]})"

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
    print("🚀 VERSIONE 11: Bot in fase di test finale...") 
    while True:
        try:
            check_youtube()
        except Exception as e:
            print(f"🚨 Errore: {e}")
        time.sleep(600)
