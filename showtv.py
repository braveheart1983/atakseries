import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os

BASE_URL = "https://www.showtv.com.tr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

GITHUB_RAW_URL = "https://raw.githubusercontent.com/braveheart1983/atakseries/main/diziler/showtv.json"

def load_existing_data():
    try:
        print(f"📥 JSON dosyası GitHub'dan indiriliyor...")
        response = requests.get(GITHUB_RAW_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ {len(data)} dizi yüklendi")
            return data
        else:
            print(f"   ⚠️  Dosya bulunamadı")
            return []
    except:
        return []

def save_data(data):
    os.makedirs("diziler", exist_ok=True)
    filename = "diziler/showtv.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"   💾 {filename} kaydedildi")
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
            series_list.append({
                'name': dizi_adi,
                'url': dizi_link,
                'poster': poster_url
            })
        return series_list
    except Exception as e:
        print(f"Hata: {e}")
        return []

def get_last_episode_number(series_url):
    """Show TV güncel sayfasından gerçek en son bölüm numarasını çeker"""
    try:
        clean_url = series_url.replace("/dizi/tanitim/", "/dizi/tum_bolumler/")
        r = requests.get(clean_url, headers=HEADERS, timeout=6)
        if r.status_code != 200:
            r = requests.get(series_url, headers=HEADERS, timeout=5)
            
        episode_numbers = []
        
        # HTML Linklerini tara
        soup = BeautifulSoup(r.content, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            match = re.search(r'bolum-(\d+)-izle', href)
            if match:
                episode_numbers.append(int(match.group(1)))
                
        # ld+json taraması
        json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block.strip())
                if data.get("@type") == "ItemList":
                    for item in data.get("itemListElement", []):
                        item_url = item.get("url", "")
                        match = re.search(r'bolum-(\d+)-izle', item_url)
                        if match:
                            episode_numbers.append(int(match.group(1)))
            except:
                continue
                
        if episode_numbers:
            return max(episode_numbers)
            
        options = soup.find_all("option", attrs={"data-href": True})
        for opt in options:
            text = opt.text.strip()
            match = re.search(r'(\d+)\.?\s*Bölüm', text)
            if match:
                episode_numbers.append(int(match.group(1)))
        
        if episode_numbers:
            return max(episode_numbers)
            
        return None
    except:
        return None

def verify_and_get_video_url(series_name, episode_num):
    """Bölüm sayfasını HTML içinden dinamik olarak bulur ve video kaynağını kazıyıp m3u8'e dönüştürür"""
    try:
        # Show TV standart tireli slug yapısı
        clean_slug = re.sub(r'[^a-z0-9]', '-', series_name.lower().replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c'))
        clean_slug = re.sub(r'-+', '-', clean_slug).strip('-')
        
        list_url = f"{BASE_URL}/dizi/tum_bolumler/{clean_slug}"
        
        r = requests.get(list_url, headers=HEADERS, timeout=8)
        target_url = None
        
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, "html.parser")
            # 1. Aşama: Sayfadaki tüm <a> taglerinde "bolum-X-izle" kalıbını ara
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if f"bolum-{episode_num}-izle" in href.lower():
                    target_url = f"{BASE_URL}{href}" if href.startswith("/") else href
                    break
            
            # 2. Aşama: Bulamazsa ld+json listesini tara
            if not target_url:
                json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL)
                for block in json_blocks:
                    try:
                        data = json.loads(block.strip())
                        if data.get("@type") == "ItemList":
                            for item in data.get("itemListElement", []):
                                item_url = item.get("url", "")
                                if f"bolum-{episode_num}-izle" in item_url.lower():
                                    target_url = f"{BASE_URL}{item_url}" if item_url.startswith("/") else item_url
                                    break
                    except:
                        continue

        # Yedek plan (Eski tahmin yöntemi)
        if not target_url:
            slug = slugify(series_name)
            target_url = f"{BASE_URL}/{slug}/{episode_num}-bolum/izle"
        
        # Gerçek bölüm sayfasına git
        r_ep = requests.get(target_url, headers=HEADERS, timeout=8)
        if r_ep.status_code in [200, 304]:
            page_html = r_ep.text
            
            def clean_and_convert_url(raw_url):
                """Gelen ham MP4 veya çözünürlük ekli linki temiz m3u8 formatına çevirir"""
                raw_url = raw_url.replace("\\/", "/").strip()
                if raw_url.startswith('//'): 
                    raw_url = 'https:' + raw_url
                
                # Çözünürlük ve kalite eklerini temizle (Örn: _1920x1080.mp4 -> .m3u8)
                raw_url = re.sub(r'_\d+x\d+', '', raw_url)
                
                # Uzantıyı m3u8 formatına dönüştür
                if raw_url.endswith(".mp4"):
                    raw_url = raw_url[:-4] + ".m3u8"
                    
                return raw_url

            # VİDEO YAKALAMA FİLTRELERİ (AGRESİF)
            
            # Filtre A: HTML içindeki ham contentUrl alanları
            content_url_match = re.search(r'"contentUrl"\s*:\s*"([^"]+)"', page_html)
            if content_url_match:
                video_url = clean_and_convert_url(content_url_match.group(1))
                if 'fragman' not in video_url.lower() and 'tanitim' not in video_url.lower():
                    return video_url
                    
            # Filtre B: ld+json içerisindeki VideoObject yapıları
            json_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page_html, re.DOTALL)
            for block in json_blocks:
                try:
                    data = json.loads(block.strip())
                    objects = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for obj in objects:
                        if obj.get("@type") == "VideoObject" or "contentUrl" in obj:
                            v_url = obj.get("contentUrl") or obj.get("embedUrl")
                            if v_url:
                                video_url = clean_and_convert_url(v_url)
                                if 'fragman' not in video_url.lower() and 'tanitim' not in video_url.lower():
                                    return video_url
                except:
                    continue

            # Filtre C: data-hope-video özniteliği
            pattern = r'data-hope-video="([^"]+)"'
            match = re.search(pattern, page_html)
            if match:
                try:
                    data_str = match.group(1).replace('&quot;', '"').replace('&#39;', "'")
                    v_data = json.loads(data_str)
                    if "media" in v_data:
                        media = v_data["media"]
                        if "m3u8" in media and len(media["m3u8"]) > 0:
                            return media["m3u8"][0]["src"]
                        elif "mp4" in media and len(media["mp4"]) > 0:
                            return clean_and_convert_url(media["mp4"][0]["src"])
                except:
                    pass
            
            # Filtre D: Genel CDN Link Kalıpları
            video_patterns = [
                r'(https?://vmcdn\.ciner\.com\.tr/[^\s"\']+\.m3u8[^\s"\']*)',
                r'(https?://vmcdn\.ciner\.com\.tr/[^\s"\']+\.mp4[^\s"\']*)',
                r'(https?://ht\.ciner\.com\.tr/[^\s"\']+\.m3u8[^\s"\']*)',
                r'vmcdn\.ciner\.com\.tr/[^\s"\']+\.(?:m3u8|mp4)'
            ]
            for pattern in video_patterns:
                matches = re.findall(pattern, page_html, re.IGNORECASE)
                for url in matches:
                    video_url = clean_and_convert_url(url)
                    if 'fragman' not in video_url.lower() and 'tanitim' not in video_url.lower():
                        return video_url
        
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
    print("🚀 ShowTV HIZLI GÜNCELLEYİCİ")
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
        
        last_episode = get_last_episode_number(series['url'])
        
        if not last_episode:
            print(f"    ⚠️  Bölüm bulunamadı")
            continue
        
        print(f"    📺 Son bölüm: {last_episode}")
        
        if series_id in existing_series_map:
            existing_last = existing_series_map[series_id]["last_episode"]
            
            if last_episode > existing_last:
                target_episode = last_episode
                
                if last_episode > existing_last + 1:
                    possible_next = existing_last + 1
                    print(f"    🔍 {possible_next}. bölüm kontrol ediliyor...")
                    
                    video_url = verify_and_get_video_url(series['name'], possible_next)
                    if video_url:
                        target_episode = possible_next
                        print(f"    ✅ {possible_next}. bölüm yayınlanmış!")
                    else:
                        print(f"    ⚠️ {possible_next}. bölüm yayınlanmamış, {last_episode}. bölüm kontrol ediliyor...")
                        video_url = verify_and_get_video_url(series['name'], last_episode)
                        if video_url:
                            target_episode = last_episode
                        else:
                            print(f"    ℹ️  Yeni bölüm yok")
                            continue
                
                if target_episode == last_episode and target_episode > existing_last:
                    video_url = verify_and_get_video_url(series['name'], target_episode)
                elif target_episode == existing_last + 1:
                    pass
                else:
                    video_url = verify_and_get_video_url(series['name'], target_episode)
                
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
            print(f"    🆕 Yeni dizi ekleniyor...")
            
            target_episode = last_episode
            video_url = verify_and_get_video_url(series['name'], target_episode)
            
            if not video_url:
                for ep in range(target_episode - 1, target_episode - 6, -1):
                    if ep > 0:
                        video_url = verify_and_get_video_url(series['name'], ep)
                        if video_url:
                            target_episode = ep
                            break
            
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
        print("=" * 60)
    else:
        print(f"\n✅ Hiç değişiklik yok! (Süre: {time.time() - start_time:.2f} saniye)")

if __name__ == "__main__":
    update_showtv()
