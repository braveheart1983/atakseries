import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

BASE_URL = "https://www.showtv.com.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

GITHUB_RAW_URL = "https://raw.githubusercontent.com/braveheart1983/atakseries/main/diziler/showtv.json"

def load_existing_data():
    try:
        print(f"📥 JSON dosyası GitHub'dan indiriliyor...")
        response = requests.get(GITHUB_RAW_URL, timeout=15)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ {len(data)} dizi yüklendi")
            return data
        else:
            print(f"   ⚠️  Dosya bulunamadı (HTTP {response.status_code})")
            return []
    except:
        return []

def save_data(data):
    os.makedirs("diziler", exist_ok=True)
    filename = "diziler/showtv.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"   💾 {filename} dosyası local'e kaydedildi")
    return True

def slugify(text):
    text = text.lower()
    text = text.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def get_series_list_fast():
    try:
        r = requests.get(f"{BASE_URL}/diziler", headers=HEADERS, timeout=10)
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
            series_list.append({
                'name': dizi_adi,
                'url': dizi_link,
                'poster': poster_url
            })
        return series_list
    except Exception as e:
        print(f"Hata: {e}")
        return []

def verify_episode_exists(series_name, episode_num):
    """Bölümün gerçekten yayınlanıp yayınlanmadığını kontrol et"""
    try:
        slug = slugify(series_name)
        url_formats = [
            f"{BASE_URL}/{slug}/{episode_num}-bolum/izle",
            f"{BASE_URL}/dizi/tum_bolumler/{slug}-sezon-1-bolum-{episode_num}-izle",
            f"{BASE_URL}/dizi/tum_bolumler/{slug}-bolum-{episode_num}-izle"
        ]
        
        for ep_url in url_formats:
            try:
                headers = HEADERS.copy()
                headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                headers["Pragma"] = "no-cache"
                
                r = requests.get(ep_url, headers=headers, timeout=8)
                
                if r.status_code in [200, 304]:
                    soup = BeautifulSoup(r.content, "html.parser")
                    page_html = str(soup)
                    
                    # 1. hope-video div'i ve data-hope-video kontrolü
                    video_div = soup.find("div", class_="hope-video")
                    if video_div:
                        data_attr = video_div.get("data-hope-video")
                        if data_attr:
                            try:
                                v_data = json.loads(data_attr)
                                if "media" in v_data:
                                    media = v_data["media"]
                                    if ("m3u8" in media and len(media["m3u8"]) > 0) or \
                                       ("mp4" in media and len(media["mp4"]) > 0):
                                        return True
                            except:
                                pass
                    
                    # 2. JSON-LD VideoObject kontrolü
                    if '"@type":"VideoObject"' in page_html:
                        return True
                    
                    # 3. Video URL'leri kontrolü
                    video_patterns = [
                        r'vmcdn\.ciner\.com\.tr/[^\s"\']+\.(?:m3u8|mp4)',
                        r'https?://[^\s"\']+\.m3u8[^\s"\']*',
                        r'https?://[^\s"\']+\.mp4[^\s"\']*'
                    ]
                    for pattern in video_patterns:
                        if re.search(pattern, page_html, re.IGNORECASE):
                            return True
                    
                    # 4. Sayfa başlığında bölüm bilgisi varsa (yayınlanmış demektir)
                    title = soup.title.string if soup.title else ""
                    if f"{episode_num}. Bölüm" in title or f"Bölüm {episode_num}" in title:
                        return True
            except:
                continue
        
        return False
    except:
        return False

def get_last_episode_number(series_url, series_name):
    """Doğru son bölüm numarasını bul"""
    try:
        r = requests.get(series_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.content, "html.parser")
        
        episode_numbers = []
        
        # Dropdown'dan bölüm numaralarını al
        options = soup.find_all("option", attrs={"data-href": True})
        for opt in options:
            text = opt.text.strip()
            match = re.search(r'(\d+)\.?\s*Bölüm', text)
            if match:
                episode_numbers.append(int(match.group(1)))
        
        # "Son Bölüm" butonunu kontrol et
        son_bolum_span = soup.find("span", string="Son Bölüm")
        if son_bolum_span:
            parent_a = son_bolum_span.find_parent("a")
            if parent_a and parent_a.get("href"):
                son_bolum_url = BASE_URL + parent_a.get("href")
                try:
                    r2 = requests.get(son_bolum_url, headers=HEADERS, timeout=5)
                    soup2 = BeautifulSoup(r2.content, "html.parser")
                    title = soup2.title.string if soup2.title else ""
                    match = re.search(r'(\d+)\.?\s*Bölüm', title)
                    if match:
                        son_ep = int(match.group(1))
                        if son_ep in episode_numbers or not episode_numbers:
                            return son_ep
                except:
                    pass
        
        if episode_numbers:
            return max(episode_numbers)
        
        return None
    except Exception as e:
        print(f"    Hata: {e}")
        return None

def get_video_url(series_name, episode_num):
    """Video URL'sini al"""
    try:
        slug = slugify(series_name)
        url_formats = [
            f"{BASE_URL}/{slug}/{episode_num}-bolum/izle",
            f"{BASE_URL}/dizi/tum_bolumler/{slug}-sezon-1-bolum-{episode_num}-izle",
            f"{BASE_URL}/dizi/tum_bolumler/{slug}-bolum-{episode_num}-izle"
        ]
        
        for ep_url in url_formats:
            try:
                headers = HEADERS.copy()
                headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                headers["Pragma"] = "no-cache"
                
                r = requests.get(ep_url, headers=headers, timeout=10)
                if r.status_code in [200, 304]:
                    soup = BeautifulSoup(r.content, "html.parser")
                    page_html = str(soup)
                    
                    # 1. hope-video div'inden data-hope-video al
                    video_div = soup.find("div", class_="hope-video")
                    if video_div:
                        data_attr = video_div.get("data-hope-video")
                        if data_attr:
                            try:
                                v_data = json.loads(data_attr)
                                if "media" in v_data:
                                    media = v_data["media"]
                                    if "m3u8" in media and len(media["m3u8"]) > 0:
                                        return media["m3u8"][0]["src"]
                                    elif "mp4" in media and len(media["mp4"]) > 0:
                                        return media["mp4"][0]["src"]
                            except:
                                pass
                    
                    # 2. JSON-LD'den video URL'si al
                    json_ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page_html, re.DOTALL)
                    if json_ld_match:
                        try:
                            json_str = json_ld_match.group(1)
                            data = json.loads(json_str)
                            if isinstance(data, dict) and data.get("@type") == "VideoObject":
                                if "contentUrl" in data:
                                    return data["contentUrl"]
                                if "embedUrl" in data:
                                    return data["embedUrl"]
                        except:
                            pass
                    
                    # 3. Video URL'lerini ara
                    video_patterns = [
                        r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
                        r'(https?://[^\s"\']+\.mp4[^\s"\']*)',
                        r'contentUrl":"([^"]+\.(?:m3u8|mp4))',
                        r'src="([^"]+\.(?:m3u8|mp4))"'
                    ]
                    for pattern in video_patterns:
                        matches = re.findall(pattern, page_html, re.IGNORECASE)
                        for url in matches:
                            if 'fragman' not in url.lower() and 'tanitim' not in url.lower():
                                return url
            except:
                continue
        
        return None
    except Exception as e:
        print(f"      Video URL hatası: {e}")
        return None

def create_episode_object(number, title, url):
    return {
        "number": number,
        "name": title,
        "sources": [{"url": url, "label": "İzleme Kaynağı"}]
    }

def update_showtv():
    print("🚀 ShowTV GÜNCELLEYİCİ")
    print("=" * 60)
    start_time = time.time()
    
    existing_data = load_existing_data()
    print(f"📂 Mevcut JSON'da {len(existing_data)} dizi var")
    
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
    
    print("\n🔍 Web sitesi taranıyor...")
    all_series = get_series_list_fast()
    print(f"   {len(all_series)} dizi bulundu")
    print("-" * 40)
    
    # Son 5 dizi + Yeni diziler
    series_to_check = []
    
    new_series = []
    for series in all_series:
        series_id = f"showtv_{slugify(series['name'])}"
        if series_id not in existing_series_ids:
            new_series.append(series)
    
    if new_series:
        print(f"🆕 {len(new_series)} yeni dizi bulundu!")
        series_to_check.extend(new_series)
    
    existing_series_list = [s for s in all_series if f"showtv_{slugify(s['name'])}" in existing_series_ids]
    last_five = existing_series_list[:5]
    
    if last_five:
        print(f"📺 Son 5 güncel dizi kontrol edilecek")
        new_series_ids = {f"showtv_{slugify(s['name'])}" for s in new_series}
        for series in last_five:
            series_id = f"showtv_{slugify(series['name'])}"
            if series_id not in new_series_ids:
                series_to_check.append(series)
    
    seen_names = set()
    unique_series = []
    for s in series_to_check:
        if s['name'] not in seen_names:
            seen_names.add(s['name'])
            unique_series.append(s)
    series_to_check = unique_series
    
    print(f"📌 Toplam {len(series_to_check)} dizi kontrol edilecek")
    print("-" * 40)
    
    updated_count = 0
    new_series_count = 0
    total_new_episodes = 0
    
    for idx, series in enumerate(series_to_check, 1):
        series_id = f"showtv_{slugify(series['name'])}"
        
        if series_id in existing_series_map:
            print(f"\n[{idx}/{len(series_to_check)}] 📺 {series['name']}")
        else:
            print(f"\n[{idx}/{len(series_to_check)}] 🆕 {series['name']} (YENİ DİZİ!)")
        
        last_episode = get_last_episode_number(series['url'], series['name'])
        
        if not last_episode:
            print(f"    ⚠️  Bölüm bulunamadı")
            continue
        
        print(f"    📺 Son bölüm: {last_episode}")
        
        if series_id in existing_series_map:
            existing_last = existing_series_map[series_id]["last_episode"]
            
            if last_episode > existing_last:
                # Atlama kontrolü
                target_episode = last_episode
                if last_episode > existing_last + 1:
                    possible_next = existing_last + 1
                    print(f"    🔍 {possible_next}. bölüm kontrol ediliyor...")
                    
                    if verify_episode_exists(series['name'], possible_next):
                        target_episode = possible_next
                        print(f"    ✅ {possible_next}. bölüm yayınlanmış!")
                    else:
                        print(f"    ⚠️ {possible_next}. bölüm yayınlanmamış, {last_episode}. bölüm kontrol ediliyor...")
                        if verify_episode_exists(series['name'], last_episode):
                            target_episode = last_episode
                        else:
                            print(f"    ℹ️  Yeni bölüm yok")
                            continue
                
                if target_episode > existing_last:
                    print(f"    ✅ YENİ BÖLÜM! (Eski: {existing_last} -> Yeni: {target_episode})")
                    print(f"       🎬 {target_episode}. Bölüm video alınıyor...")
                    
                    video_url = get_video_url(series['name'], target_episode)
                    
                    if video_url:
                        video_url = video_url.replace("//ht/", "/ht/").replace("com//", "com/")
                        
                        new_episode = create_episode_object(
                            number=target_episode,
                            title=f"{target_episode}. Bölüm",
                            url=video_url
                        )
                        existing_series_map[series_id]["data"]["episodes"].append(new_episode)
                        
                        existing_series_map[series_id]["data"]["episodes"] = sorted(
                            existing_series_map[series_id]["data"]["episodes"], 
                            key=lambda x: x.get("number", 0)
                        )
                        
                        updated_count += 1
                        total_new_episodes += 1
                        print(f"          ✅ {target_episode}. Bölüm eklendi!")
                    else:
                        print(f"          ❌ Video bulunamadı")
                else:
                    print(f"    ℹ️  Yeni bölüm yok")
            else:
                print(f"    ℹ️  Yeni bölüm yok")
        else:
            # YENİ DİZİ
            print(f"    🆕 Yeni dizi ekleniyor...")
            
            target_episode = last_episode
            if not verify_episode_exists(series['name'], target_episode):
                for ep in range(target_episode - 1, target_episode - 6, -1):
                    if ep > 0 and verify_episode_exists(series['name'], ep):
                        target_episode = ep
                        break
            
            print(f"       🎬 {target_episode}. Bölüm video alınıyor...")
            video_url = get_video_url(series['name'], target_episode)
            
            if video_url:
                video_url = video_url.replace("//ht/", "/ht/").replace("com//", "com/")
                
                new_series_obj = {
                    "id": series_id,
                    "name": series['name'],
                    "overview": f"{series['name']} dizisinin tüm bölümleri - Show TV",
                    "poster": series['poster'],
                    "logo": series['poster'],
                    "backdrop": series['poster'],
                    "year": "",
                    "tmdb_score": 0,
                    "genres": ["Dram", "Aile", "Komedi"],
                    "categories": ["Show TV"],
                    "cast": [],
                    "episodes": [
                        create_episode_object(
                            number=target_episode,
                            title=f"{target_episode}. Bölüm",
                            url=video_url
                        )
                    ]
                }
                existing_data.append(new_series_obj)
                new_series_count += 1
                total_new_episodes += 1
                print(f"          ✅ Yeni dizi eklendi! ({target_episode}. Bölüm)")
            else:
                print(f"          ❌ Video bulunamadı")
        
        time.sleep(0.1)
    
    if updated_count > 0 or new_series_count > 0:
        save_data(existing_data)
        
        elapsed_time = time.time() - start_time
        print(f"\n" + "=" * 60)
        print("✅ GÜNCELLEME TAMAMLANDI!")
        print("=" * 60)
        print(f"📊 İSTATİSTİKLER:")
        print(f"   • Toplam Dizi: {len(existing_data)}")
        print(f"   • Yeni Dizi: {new_series_count}")
        print(f"   • Yeni Bölüm Eklenen Dizi: {updated_count}")
        print(f"   • Toplam Yeni Bölüm: {total_new_episodes}")
        print(f"   • Süre: {elapsed_time:.2f} saniye")
        print(f"   • JSON Dosyası: 'diziler/showtv.json'")
        print("=" * 60)
    else:
        print(f"\n✅ Hiç değişiklik yok! (Süre: {time.time() - start_time:.2f} saniye)")

if __name__ == "__main__":
    update_showtv()
