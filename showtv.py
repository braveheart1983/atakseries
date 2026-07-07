import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

BASE_URL = "https://www.showtv.com.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8"
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
    print(f"   💾 {filename} güncellendi.")
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

def scrape_episode_details_from_schema(series_url, series_name):
    """Sayfa içerisindeki application/ld+json bloklarından net bölüm numarasını ve ham mp4 linkini söker"""
    try:
        series_slug = re.sub(r'[^a-z0-9]', '-', series_name.lower().replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c'))
        series_slug = re.sub(r'-+', '-', series_slug).strip('-')
        
        # Tüm olası bölümler sayfasını kontrol et
        clean_url = series_url.replace("/dizi/tanitim/", "/dizi/tum_bolumler/")
        r = requests.get(clean_url, headers=HEADERS, timeout=8)
        if r.status_code != 200:
            r = requests.get(series_url, headers=HEADERS, timeout=5)
            
        soup = BeautifulSoup(r.content, "html.parser")
        
        # İlk olarak ana 'tum_bolumler' sayfasındaki gerçek bölüm izleme linklerini toplayalım
        episode_urls = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if series_slug in href.lower() and "izle" in href.lower():
                if not any(x in href.lower() for x in ["fragman", "tanitim", "ozet", "sahne"]):
                    full_url = href if href.startswith("http") else BASE_URL + href
                    if full_url not in episode_urls:
                        episode_urls.append(full_url)
                        
        # Eğer link bulamadıysa mevcut url'yi dene
        if not episode_urls:
            episode_urls.append(clean_url)

        max_episode_num = -1
        best_mp4_url = None

        # Bulunan izleme sayfalarının içine girip l+json şemalarını ayıklıyoruz
        for ep_url in episode_urls[:3]:  # Zaman kazanmak için en güncel ilk 3 linke bakması yeterli
            try:
                r_page = requests.get(ep_url, headers=HEADERS, timeout=6)
                if r_page.status_code != 200:
                    continue
                    
                page_soup = BeautifulSoup(r_page.content, "html.parser")
                scripts = page_soup.find_all("script", type="application/ld+json")
                
                current_ep_num = None
                current_mp4 = None
                
                for script in scripts:
                    try:
                        json_data = json.loads(script.string)
                        
                        # 1. Şema: TVEpisode yapısından kesin bölüm numarasını alıyoruz
                        if json_data.get("@type") == "TVEpisode":
                            if "episodeNumber" in json_data:
                                current_ep_num = int(json_data["episodeNumber"])
                                
                        # 2. Şema: VideoObject yapısından doğrudan ham MP4 linkini (contentUrl) çekiyoruz
                        if json_data.get("@type") == "VideoObject":
                            if "contentUrl" in json_data:
                                current_mp4 = json_data["contentUrl"].strip()
                    except:
                        continue
                        
                if current_ep_num and current_mp4:
                    if current_ep_num > max_episode_num:
                        max_episode_num = current_ep_num
                        best_mp4_url = current_mp4
            except:
                continue

        if max_episode_num != -1 and best_mp4_url:
            return max_episode_num, best_mp4_url
        return None, None
    except:
        return None, None

def create_episode_object(number, title, url):
    return {
        "number": number,
        "name": title,
        "sources": [{"url": url, "label": "İzleme Kaynağı"}]
    }

def update_showtv():
    print("🚀 ShowTV ld+json Şema Sökücü Başlatıldı")
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
        
        # Yeni şema analiz fonksiyonumuzu çağırıyoruz
        last_episode, video_url = scrape_episode_details_from_schema(series['url'], series['name'])
        
        if not last_episode or not video_url:
            print(f"    ⚠️  Siteden geçerli tam bölüm ve MP4 kaynağı saptanamadı.")
            continue
            
        print(f"    📺 Sitedeki Gerçek Son Bölüm: {last_episode}")
        
        if series_id in existing_series_map:
            existing_last = existing_series_map[series_id]["last_episode"]
            
            if last_episode > existing_last:
                new_episode = create_episode_object(last_episode, f"{last_episode}. Bölüm", video_url)
                existing_series_map[series_id]["data"]["episodes"].append(new_episode)
                existing_series_map[series_id]["data"]["episodes"] = sorted(existing_series_map[series_id]["data"]["episodes"], key=lambda x: x.get("number", 0))
                updated_count += 1
                print(f"          ✅ {last_episode}. Bölüm JSON'a eklendi!\n          🔗 Doğrudan MP4 Linki: {video_url}")
            else:
                print(f"    ℹ️  Yeni bölüm yok (JSON güncel, Mevcut En Son: {existing_last})")
        else:
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
            print(f"          ✅ Yeni dizi sıfırdan JSON'a işlendi! ({last_episode}. Bölüm)\n          🔗 Doğrudan MP4 Linki: {video_url}")
            
        time.sleep(0.2)
        
    if updated_count > 0 or new_series_count > 0:
        save_data(existing_data)
        print(f"\n============================================================\n✅ KESİN ÇÖZÜM: YENİ BÖLÜM VE MP4 KAYNAĞI JSON'A YAZILDI!\n============================================================")

if __name__ == "__main__":
    update_showtv()
