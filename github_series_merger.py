import json
import requests
from glob import glob
import os
import time

# ================= KONFİGÜRASYON =================
GITHUB_USER = "braveheart1983"
REPO_NAME = "atakseries"
BRANCH = "main"
SOURCE_FOLDER = "diziler"

# Platform adı -> (Görünen Kategori Adı, Dosya Öneki, Logo URL)
CATEGORY_MAP = {
    "amazon-prime": ("Amazon Prime", "amazon-prime", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/amazon.png"),
    "animeker": ("Anime", "animeker", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/anime.jpg"),
    "asya-dizileri": ("Asya Dizileri", "asya-dizileri", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/asyadiziler.jpg"),
    "cocuk": ("Çocuk", "cocuk", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/kids.png"),
    "disney": ("Disney+", "disney", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/disney+.png"),
    "exen": ("Exen", "exen", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/exxen.jpg"),
    "hbo": ("HBO Max", "hbo", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/hbo.png"),
    "netflix": ("Netflix", "netflix", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/netflix.png"),
    "puhutv": ("PuhuTV", "puhutv", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/Puhutv.jpg"),
    "star-tv": ("Star TV", "star-tv", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/Startv.png"),
    "tabii": ("Tabii", "tabii", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/tabii.png"),
    "tod": ("TOD", "tod", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/tod.png"),
    "yerli-diziler": ("Yerli Diziler", "yerli-diziler", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/yerli.png"),
    "atv": ("ATV", "atv", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/atv.png"),
    "showtv": ("Show TV", "showtv", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/showtv.png"),
    "apple-tv": ("Apple TV", "apple-tv", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/appletv.png"),
    "blutv": ("BluTV", "blutv", "https://raw.githubusercontent.com/braveheart1983/atakseries/main/logolar/blutv.png")
}
# ================================================

def get_json_from_github(file_path):
    """GitHub'dan JSON dosyasını çeker"""
    url = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}/{file_path}"
    print(f"   📥 Çekiliyor: {url}")
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"   ❌ Hata {response.status_code}: {file_path}")
            return None
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return None

def get_file_list_from_github():
    """GitHub'daki diziler klasöründeki JSON dosyalarının listesini alır"""
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/contents/{SOURCE_FOLDER}"
    print(f"📂 Dosya listesi alınıyor: {url}")
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            files = response.json()
            json_files = [f["name"] for f in files if f["name"].endswith(".json")]
            print(f"   ✅ {len(json_files)} JSON dosyası bulundu: {json_files}")
            return json_files
        else:
            print(f"   ❌ API Hatası: {response.status_code}")
            return []
    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return []

def validate_series_item(item):
    """Bir dizi öğesinin geçerli olup olmadığını kontrol eder"""
    if not isinstance(item, dict):
        return False
    if not item.get('name'):
        return False
    if not item.get('id'):
        return False
    return True

def fix_poster_url(url):
    """Poster URL'sini düzeltir (varsa)"""
    if not url:
        return ""
    if isinstance(url, str):
        url = url.strip().strip('"').strip("'")
        return url
    return ""

def save_json_file(data, filename, pretty=True):
    """JSON dosyasını kaydeder"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
            else:
                json.dump(data, f, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"   ❌ Dosya kaydedilemedi: {e}")
        return False

def main():
    print("🚀 GitHub Seri Birleştirici Başladı")
    print("=" * 60)
    start_time = time.time()
    
    json_files = get_file_list_from_github()
    if not json_files:
        print("❌ Hiç JSON dosyası bulunamadı!")
        return
    
    all_series = []
    main_index = []
    processed_count = 0
    error_count = 0
    
    for file_name in json_files:
        platform_name = file_name.replace(".json", "")
        
        if platform_name in CATEGORY_MAP:
            category_name, file_prefix, logo_url = CATEGORY_MAP[platform_name]
        else:
            category_name = platform_name
            file_prefix = platform_name
            logo_url = ""
        
        print(f"\n📄 İşleniyor: {file_name}")
        print(f"   🏷️  Kategori: {category_name}")
        
        file_path = f"{SOURCE_FOLDER}/{file_name}"
        data = get_json_from_github(file_path)
        
        if data is None:
            print(f"   ⚠️ Veri çekilemedi, atlanıyor.")
            error_count += 1
            continue
        
        if not isinstance(data, list):
            print(f"   ⚠️ JSON bir liste değil, atlanıyor.")
            error_count += 1
            continue
        
        if len(data) == 0:
            print(f"   ⚠️ Boş dosya, atlanıyor.")
            error_count += 1
            continue
        
        valid_series = []
        index_data = []
        
        for series in data:
            if not validate_series_item(series):
                continue
            
            series_id = series.get("id")
            if not series_id:
                series_id = f"{file_prefix}_{len(valid_series)}"
                series["id"] = series_id
            
            if series.get("poster"):
                series["poster"] = fix_poster_url(series["poster"])
            
            valid_series.append(series)
            
            index_data.append({
                "id": series_id,
                "name": series.get("name"),
                "poster": series.get("poster", "")
            })
        
        if not valid_series:
            print(f"   ⚠️ Geçerli dizi bulunamadı, atlanıyor.")
            error_count += 1
            continue
        
        all_series.extend(valid_series)
        processed_count += 1
        
        print(f"   ✅ {len(valid_series)} geçerli dizi işlendi")
        
        if save_json_file(index_data, f"{file_prefix}-index.json"):
            print(f"   📁 {file_prefix}-index.json oluşturuldu ({len(index_data)} dizi)")
        
        if save_json_file(valid_series, f"{file_prefix}-detay.json"):
            print(f"   📁 {file_prefix}-detay.json oluşturuldu")
        
        # ⭐ BURASI ÖNEMLİ: logoUrl EKLENİYOR!
        main_index.append({
            "name": category_name,
            "indexUrl": f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}/{file_prefix}-index.json",
            "detailUrl": f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}/{file_prefix}-detay.json",
            "logoUrl": logo_url  # ✅ LOGO URL EKLENDİ - NULL DEĞİL!
        })
        
        time.sleep(0.5)
    
    if all_series:
        if save_json_file(all_series, "tum_diziler.json"):
            print(f"\n📦 tum_diziler.json oluşturuldu (Toplam {len(all_series)} dizi)")
    
    # ⭐ BURASI DA ÖNEMLİ: index.json logoUrl ile birlikte kaydediliyor
    if save_json_file(main_index, "index.json"):
        print(f"\n✅ index.json oluşturuldu ({len(main_index)} kategori)")
        print("\n📋 index.json içeriği (ilk 2 kategori):")
        for i, cat in enumerate(main_index[:2]):
            print(f"   {i+1}. {cat.get('name')} -> logoUrl: {cat.get('logoUrl', 'MISSING!')}")
    
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("🎉 İŞLEM TAMAMLANDI!")
    print("=" * 60)
    print(f"📊 İSTATİSTİKLER:")
    print(f"   • İşlenen Dosya: {processed_count}")
    print(f"   • Hata Alan Dosya: {error_count}")
    print(f"   • Toplam Dizi: {len(all_series)}")
    print(f"   • Toplam Kategori: {len(main_index)}")
    print(f"   • Süre: {elapsed_time:.2f} saniye")
    
    print("\n📱 Uygulamada kullanılacak URL:")
    print("   https://raw.githubusercontent.com/braveheart1983/atakseries/main/index.json")
    
    print("\n📁 Oluşturulan dosyalar:")
    for item in os.listdir("."):
        if item.endswith(".json"):
            size_kb = os.path.getsize(item) / 1024
            print(f"   - {item} ({size_kb:.1f} KB)")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
