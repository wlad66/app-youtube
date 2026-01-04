import time, os, feedparser, requests, psycopg2
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi

# --- CONFIGURAZIONE (Usa variabili d'ambiente su Dokploy) ---
DB_URL = os.getenv("DATABASE_URL")
GEMINI_KEY = os.getenv("GEMINI_KEY")
TG_TOKEN = os.getenv("TELEGRAM_TOKEN")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# Lista dei canali (ID canale, non il nome)
CHANNELS = ["UC_x5XG1OV2P6uYZ5gzS9tNQ", "ID_ALTRO_CANALE"] 

genai.configure(api_key=GEMINI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

def init_db():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS videos (video_id TEXT PRIMARY KEY, title TEXT, summary TEXT)")
    conn.commit()
    cur.close()
    conn.close()

def get_summary(video_id, title):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['it', 'en'])
        text = " ".join([t['text'] for t in transcript])[:10000] # Limite testo
        prompt = f"Riassumi il video '{title}' in 5 punti chiave ed elenca eventuali link o nomi citati: {text}"
        response = ai_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Riassunto non disponibile: {str(e)}"

def check_youtube():
    init_db()
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    for channel_id in CHANNELS:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:3]: # Controlla gli ultimi 3 video
            video_id = entry.yt_videoid
            cur.execute("SELECT video_id FROM videos WHERE video_id = %s", (video_id,))
            if not cur.fetchone():
                print(f"Nuovo video trovato: {entry.title}")
                summary = get_summary(video_id, entry.title)
                
                # Invia a Telegram
                msg = f"📺 *{entry.title}*\n\n📝 *RIASSUNTO:*\n{summary}\n\n🔗 {entry.link}"
                requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                              data={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
                
                # Salva in Database
                cur.execute("INSERT INTO videos (video_id, title, summary) VALUES (%s, %s, %s)", 
                            (video_id, entry.title, summary))
                conn.commit()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    while True:
        try:
            check_youtube()
        except Exception as e:
            print(f"Errore: {e}")
        time.sleep(3600) # Controlla ogni ora