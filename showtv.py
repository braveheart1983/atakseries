import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

BASE_URL = "https://www.showtv.com.tr"

# Ciner sunucularının bot olarak algılamaması için tarayıcı başlıkları
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.showtv.com.tr/",
    "Origin": "https://www.showtv.com.tr"
}

GITHUB_RAW_URL = "https://raw.githubusercontent.com/braveheart1983/atakseries/main/diziler/showtv.json"

def load_existing_data():
    try:
        response = requests.get(GITHUB_RAW_URL, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def save_data(data):
    os.makedirs("diziler", exist_ok=True)
    filename = "diziler/showtv.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"   💾 {filename} başarıyla kaydedildi.")
    return True

def slugify(text):
    text = text.lower()
    text = text.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def get_series_list_fast():
    try:
        r = requests.get(f"{BASE_URL}/diziler", headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.content, "html.parser")
        series_list = []
        dizi_kutulari = soup.find_all("div", attrs={"data-name": "box-type6"})
        for kutu in dizi_kutulari:
            link_tag = kutu.find("a", class_="group")
            if not link_tag:
                continue
            dizi_adi = link_tag.get("title")
            dizi_link = BASE_URL + link_tag.get("href")
            img_tag = kutu.find("img")
            poster_url = img_tag.get("src") or img_tag.get("data-src", "")
            if "?" in poster_url:
                poster_url = poster_url.split("?")[0]
            series_list.append({'name': dizi_adi, 'url': dizi_link, 'poster': poster_url})
        return series_list
    except:
        return []

def get_last_episode_number(series_url, series_name):
    try:
        series_slug = re.sub(r'[^a-z0-9]', '-', series_name.lower().replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c'))
        series_slug = re.sub(r'-+', '-', series_slug).strip('-')
        
        clean_url = series_url.replace("/dizi/tanitim/", "/dizi/tum_bolumler/")
        r = requests.get(clean_url, headers=HEADERS, timeout=6)
        if r.status_code != 200:
            r = requests.get(series_url, headers=HEADERS, timeout=5)
            
        episode_numbers = []
        soup = BeautifulSoup(r.content, "html.parser")
        
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            if series_slug in href:
                # Sitedeki '3-bolum/izle', 'bolum/3' ve 'bolum-3' yapılarının hepsini kaçırmadan yakalar
                match = re.search(r'(\d+)-bolum', href) or re.search(r'bolum/(\d+)', href) or re.search(r'bolum-(\d+)', href)
                if match:
                    episode_numbers.append(int(match.group(1)))
                    
        if episode_numbers:
            return max(episode_numbers)
        return None
    except:
        return None

def verify_and_get_video_url(series_name, episode_num):
    """Doğrudan VLC ve oynatıcılarda çalışan ham, imzasız MP4 / M3U8 linkini çeker"""
    try:
        clean_slug = re.sub(r'[^a-z0-9]', '-', series_name.lower().replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c'))
        clean_slug = re.sub(r'-+', '-', clean_slug).strip('-')
        
        # Kesinleşen güncel URL yapıları
        target_urls = [
            f"{BASE_URL}/dizi/tum_bolumler/{clean_slug}/{episode_num}-bolum/izle",
            f"{BASE_URL}/dizi/tum_bolumler/{clean_slug}/bolum/{episode_num}",
            f"{BASE_URL}/{clean_slug}/{episode_num}-bolum/izle"
        ]

        for url in target_urls:
            try:
                r_ep = requests.get(url, headers=HEADERS, timeout=8)
                if r_ep.status_code not in [200, 304]:
                    continue
                    
                page_html = r_ep.text
                video_id = None
                
                # Sayfa içindeki gizli video ID parametresini buluyoruz
                data_id_match = re.search(r'data-id=["\'](\d+)["\']', page_html)
                if data_id_match:
                    video_id = data_id_match.group(1)
                
                if not video_id:
                    player_div_match = re.search(r'id=["\']video_player_(\d+)["\']', page_html)
                    if player_div_match:
                        video_id = player_div_match.group(1)

                # ID bulunduysa Ciner'in veri havuzuna vurup ham adresi alıyoruz
                if video_id:
                    ciner_api_url = f"https://mo.ciner.com.tr/api/video/get/{video_id}"
                    
                    api_headers = HEADERS.copy()
                    api_headers["Referer"] = url
                    
                    r_api = requests.get(ciner_api_url, headers=api_headers, timeout=6)
                    if r_api.status_code == 200:
                        api_data = r_api.json()
                        media_node = api_data.get("data", {}).get("media", {})
                        
                        # 1. ÖNCELİK: Senin belirttiğin doğrudan VLC'de çalışan imzasız ham MP4 linki
                        mp4_entries = media_node.get("mp4", [])
                        if mp4_entries:
                            for entry in mp4_entries:
                                v_url = entry.get("src", "").strip()
                                # Kaliteyi en yüksek (1080p) veya senin verdiğin formata getirmek için temizlik
                                if v_url and ".mp4" in v_url:
                                    if 'fragman' not in v_url.lower() and 'tanitim' not in v_url.lower():
                                        # Gerekirse URL düzeltmelerini yap (çift slash temizliği)
                                        v_url = v_url.replace("\\/", "/")
                                        return v_url

                        # 2. ÖNCELİK: Eğer MP4 yoksa imzasız düz m3u8 adresi
                        m3u8_entries = media_node.get("m3u8", [])
                        if m3u8_entries and "src" in m3u8_entries[0]:
                            v_url = m3u8_entries[0]["src"].strip().replace("\\/", "/")
                            if 'fragman' not in v_url.lower() and 'tanitim' not in v_url.lower():
                                # Token kısmını (?e=...) uçurup sadece ham m3u8'i bırakıyoruz ki patlamasın
                                if "?" in v_url:
                                    v_url = v_url.split("?")[0]
                                return v_url
            except:
                continue
        return None
    except:
        return None

def create_episode_object(number, title, url):
    return {
        "number": number,
        "name": title,
        "sources": [{"url": url, "label": "İzleme Kaynağı"}]
    }

def update_showtv():
    print("🚀 ShowTV Ham URL Yakalayıcı Başlatıldı")
    print("=" * 60)
    
    existing_data = load_existing_data()
    existing_series_ids = {series.get("id") for series in existing_data}
    existing_series_map = {}
    
    for series in existing_data:
        series_id = series.get("id")
        if series_id:
            episodes = series.get("episodes", [])
            last_ep = max(episodes, key=lambda x: x.get("number", 0)) if episodes else None
            existing_series_map[series_id] = {
                "data": series,
                "last_episode": last_ep.get("number", 0) if last_ep else 0
            }
    
    all_series = get_series_list_fast()
    series_to_check = []
    new_series = []
    
    for series in all_series:
        series_id = f"showtv_{slugify(series['name'])}"
        if series_id not in existing_series_ids:
            new_series.append(series)
            
    series_to_check.extend(new_series)
    existing_series_list = [s for s in all_series if f"showtv_{slugify(s['name'])}" in existing_series_ids]
    
    # Güncel olan ilk 5 diziyi listeye ekle
    for series in existing_series_list[:5]:
        if f"showtv_{slugify(series['name'])}" not in {f"showtv_{slugify(s['name'])}" for s in new_series}:
            series_to_check.append(series)
            
    seen_names = set()
    series_to_check = [s for s in series_to_check if not (s['name'] in seen_names or seen_names.add(s['name']))]
    
    updated_count = 0
    new_series_count = 0
    
    for idx, series in enumerate(series_to_check, 1):
        series_id = f"showtv_{slugify(series['name'])}"
        print(f"\n[{idx}/{len(series_to_check)}] 📺 {series['name']}")
        
        last_episode = get_last_episode_number(series['url'], series['name'])
        if not last_episode:
            print(f"    ⚠️  Bölüm numarası saptanamadı.")
            continue
            
        print(f"    📺 Sitedeki Son Bölüm: {last_episode}")
        
        if series_id in existing_series_map:
            existing_last = existing_series_map[series_id]["last_episode"]
            if last_episode > existing_last:
                video_url = verify_and_get_video_url(series['name'], last_episode)
                if video_url:
                    new_episode = create_episode_object(last_episode, f"{last_episode}. Bölüm", video_url)
                    existing_series_map[series_id]["data"]["episodes"].append(new_episode)
                    existing_series_map[series_id]["data"]["episodes"] = sorted(existing_series_map[series_id]["data"]["episodes"], key=lambda x: x.get("number", 0))
                    updated_count += 1
                    print(f"          ✅ {last_episode}. Bölüm JSON'a eklendi!\n          🔗 Ham URL: {video_url}")
                else:
                    print(f"          ❌ Video linki API'den süzülemedi.")
            else:
                print(f"    ℹ️  Yeni bölüm yok (JSON zaten güncel: {existing_last})")
        else:
            video_url = verify_and_get_video_url(series['name'], last_episode)
            if video_url:
                new_series_obj = {
                    "id": series_id,
                    "name": series['name'],
                    "overview": f"{series['name']} dizisinin tüm bölümleri - Show TV",
                    "poster": series['poster'], "logo": series['poster'], "backdrop": series['poster'],
                    "year": "", "tmdb_score": 0, "genres": ["Dram", "Aile", "Komedi"], "categories": ["Show TV"], "cast": [],
                    "episodes": [create_episode_object(last_episode, f"{last_episode}. Bölüm", video_url)]
                }
                existing_data.append(new_series_obj)
                new_series_count += 1
                print(f"          ✅ Yeni dizi sıfırdan eklendi! ({last_episode}. Bölüm)\n          🔗 Ham URL: {video_url}")
            else:
                print(f"          ❌ Video linki API'den süzülemedi.")
        time.sleep(0.2)
        
    if updated_count > 0 or new_series_count > 0:
        save_data(existing_data)
        print(f"\n============================================================\n✅ İŞLEM TAMAMLANDI VE JSON YAZILDI!\n============================================================")

if __name__ == "__main__":
    update_showtv()
