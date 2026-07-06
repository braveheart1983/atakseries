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

# GitHub RAW URL - JSON dosyasının bulunduğu yer
GITHUB_RAW_URL = "https://raw.githubusercontent.com/braveheart1983/atakseries/main/diziler/showtv.json"

def load_existing_data():
    """GitHub'dan JSON dosyasını yükler"""
    try:
        print(f"📥 JSON dosyası GitHub'dan indiriliyor...")
        response = requests.get(GITHUB_RAW_URL, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ {len(data)} dizi yüklendi")
            return data
        else:
            print(f"   ⚠️  Dosya bulunamadı (HTTP {response.status_code}), yeni dosya oluşturulacak")
            return []
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️  İndirme hatası: {e}, yeni dosya oluşturulacak")
        return []
    except json.JSONDecodeError as e:
        print(f"   ⚠️  JSON parse hatası: {e}, yeni dosya oluşturulacak")
        return []

def save_data(data):
    """JSON dosyasını diziler klasörüne kaydeder"""
    # 📌 DÜZELTİLDİ: diziler klasörüne kaydet
    os.makedirs("diziler", exist_ok=True)
    filename = "diziler/showtv.json"
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"   💾 {filename} dosyası local'e kaydedildi")
    
    # GitHub Actions için çıktı oluştur
    try:
        with open(os.environ.get('GITHUB_OUTPUT', 'output.txt'), 'a') as f:
            f.write(f"updated=true\n")
            f.write(f"filename={filename}\n")
    except:
        pass
    
    return True

def slugify(text):
    text = text.lower()
    text = text.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def get_series_list_fast():
    """Sadece dizi listesini hızlıca al"""
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

def get_last_episode_number(series_url, series_name):
    """Sadece son bölüm numarasını al"""
    try:
        r = requests.get(series_url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(r.content, "html.parser")
        
        episode_numbers = []
        
        options = soup.find_all("option", attrs={"data-href": True})
        for opt in options:
            text = opt.text.strip()
            match = re.search(r'(\d+)\.?\s*Bölüm', text)
            if match:
                episode_numbers.append(int(match.group(1)))
        
        if episode_numbers:
            return max(episode_numbers)
        
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
                        return int(match.group(1))
                except:
                    pass
        
        return None
    except Exception as e:
        print(f"    Hata: {e}")
        return None

def get_video_url(series_name, episode_num):
    """Video URL'sini al"""
    try:
        slug = slugify(series_name)
        ep_url = f"{BASE_URL}/{slug}/{episode_num}-bolum/izle"
        
        r = requests.get(ep_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        
        video_div = soup.find("div", class_="hope-video")
        if video_div and video_div.get("data-hope-video"):
            try:
                v_data = json.loads(video_div.get("data-hope-video"))
                
                if "media" in v_data:
                    media = v_data["media"]
                    if "m3u8" in media and len(media["m3u8"]) > 0:
                        return media["m3u8"][0]["src"]
                    elif "mp4" in media and len(media["mp4"]) > 0:
                        return media["mp4"][0]["src"]
            except:
                pass
        
        return None
    except Exception as e:
        print(f"      Video URL hatası: {e}")
        return None

def create_episode_object(number, title, url):
    """Bölüm nesnesini yeni formatta oluşturur"""
    return {
        "number": number,
        "name": title,
        "sources": [
            {
                "url": url,
                "label": "İzleme Kaynağı"
            }
        ]
    }

def update_showtv():
    """ShowTV JSON'ını güncelle (GitHub'dan oku, güncelle, kaydet)"""
    print("🚀 ShowTV GÜNCELLEYİCİ (GitHub Uyumlu - Yeni Format)")
    print("=" * 60)
    start_time = time.time()
    
    # GitHub'dan mevcut veriyi yükle
    existing_data = load_existing_data()
    print(f"📂 Mevcut JSON'da {len(existing_data)} dizi var")
    
    # Mevcut dizilerin ID'lerini ve son bölüm numaralarını al
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
    
    updated_count = 0
    new_series_count = 0
    total_new_episodes = 0
    
    for idx, series in enumerate(all_series, 1):
        series_id = f"showtv_{slugify(series['name'])}"
        
        if series_id in existing_series_map:
            print(f"\n[{idx}/{len(all_series)}] 📺 {series['name']}")
        else:
            print(f"\n[{idx}/{len(all_series)}] 🆕 {series['name']} (YENİ DİZİ!)")
        
        last_episode = get_last_episode_number(series['url'], series['name'])
        
        if not last_episode:
            print(f"    ⚠️  Bölüm bulunamadı")
            continue
        
        print(f"    📺 Son Bölüm: {last_episode}")
        
        if series_id in existing_series_map:
            existing_last = existing_series_map[series_id]["last_episode"]
            
            if last_episode > existing_last:
                print(f"    ✅ YENİ BÖLÜM! (Eski: {existing_last} -> Yeni: {last_episode})")
                print(f"       🎬 {last_episode}. Bölüm video alınıyor...")
                
                video_url = get_video_url(series['name'], last_episode)
                
                if video_url:
                    video_url = video_url.replace("//ht/", "/ht/").replace("com//", "com/")
                    
                    # YENİ FORMATTA BÖLÜM EKLE
                    new_episode = create_episode_object(
                        number=last_episode,
                        title=f"{last_episode}. Bölüm",
                        url=video_url
                    )
                    existing_series_map[series_id]["data"]["episodes"].append(new_episode)
                    
                    # Bölümleri sırala
                    existing_series_map[series_id]["data"]["episodes"] = sorted(
                        existing_series_map[series_id]["data"]["episodes"], 
                        key=lambda x: x.get("number", 0)
                    )
                    
                    updated_count += 1
                    total_new_episodes += 1
                    print(f"          ✅ {last_episode}. Bölüm eklendi (Yeni Format)!")
                else:
                    print(f"          ❌ Video bulunamadı")
            else:
                print(f"    ℹ️  Yeni bölüm yok")
        else:
            print(f"    🆕 Yeni dizi ekleniyor...")
            print(f"       🎬 {last_episode}. Bölüm video alınıyor...")
            
            video_url = get_video_url(series['name'], last_episode)
            
            if video_url:
                video_url = video_url.replace("//ht/", "/ht/").replace("com//", "com/")
                
                # YENİ FORMATTA DİZİ OLUŞTUR
                new_series = {
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
                            number=last_episode,
                            title=f"{last_episode}. Bölüm",
                            url=video_url
                        )
                    ]
                }
                existing_data.append(new_series)
                new_series_count += 1
                total_new_episodes += 1
                print(f"          ✅ Yeni dizi eklendi! ({last_episode}. Bölüm - Yeni Format)")
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
