import json
import requests
from glob import glob
import os

# ================= KONFİGÜRASYON =================
# GitHub repo bilgileri
GITHUB_USER = "braveheart1983"
REPO_NAME = "atakseries"
BRANCH = "main"
SOURCE_FOLDER = "diziler"  # Orijinal JSON'ların olduğu klasör

# Platform adı -> (Görünen Kategori Adı, Dosya Öneki) eşlemesi
CATEGORY_MAP = {
    "amazon-prime": ("Amazon Prime", "amazon-prime"),
    "animeker": ("Anime", "animeker"),
    "asya-dizileri": ("Asya Dizileri", "asya-dizileri"),
    "cocuk": ("Çocuk", "cocuk"),
    "disney": ("Disney+", "disney"),
    "exen": ("Exen", "exen"),
    "hbo": ("HBO Max", "hbo"),
    "netflix": ("Netflix", "netflix"),
    "puhutv": ("PuhuTV", "puhutv"),
    "star-tv": ("Star TV", "star-tv"),
    "tabii": ("Tabii", "tabii"),
    "tod": ("TOD", "tod"),
    "yerli-diziler": ("Yerli Diziler", "yerli-diziler"),
    "atv": ("ATV", "atv"),
    "showtv": ("Show TV", "showtv")
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

def main():
    print("🚀 GitHub Seri Birleştirici Başladı")
    print("=" * 50)
    
    # GitHub'dan dosya listesini al
    json_files = get_file_list_from_github()
    if not json_files:
        print("❌ Hiç JSON dosyası bulunamadı!")
        return
    
    all_series = []  # Tüm diziler buraya eklenecek
    main_index = []  # Ana index.json için
    
    for file_name in json_files:
        platform_name = file_name.replace(".json", "")
        category_name, file_prefix = CATEGORY_MAP.get(platform_name, (platform_name, platform_name))
        
        print(f"\n📄 İşleniyor: {file_name} (Kategori: {category_name})")
        
        # GitHub'dan JSON'u çek
        file_path = f"{SOURCE_FOLDER}/{file_name}"
        data = get_json_from_github(file_path)
        
        if data is None or not isinstance(data, list):
            print(f"   ⚠️ Geçersiz format veya boş dosya, atlanıyor.")
            continue
        
        # Tüm dizileri ana listeye ekle (pretty format için)
        for series in data:
            if isinstance(series, dict) and series.get('name'):
                all_series.append(series)
        
        # Index için hafif veri hazırla
        index_data = []
        for series in data:
            if isinstance(series, dict) and series.get('name'):
                index_data.append({
                    "id": series.get("id", f"{platform_name}_{len(index_data)}"),
                    "name": series.get("name"),
                    "poster": series.get("poster", "")
                })
        
        print(f"   ✅ {len(index_data)} dizi işlendi")
        
        # Ayrıca ayrı dosyalar da oluştur (pretty format - alt alta)
        # index dosyası
        with open(f"{file_prefix}-index.json", "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        print(f"   📁 {file_prefix}-index.json oluşturuldu ({len(index_data)} dizi)")
        
        # detay dosyası
        with open(f"{file_prefix}-detay.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"   📁 {file_prefix}-detay.json oluşturuldu")
        
        # Ana index'e ekle
        main_index.append({
            "name": category_name,
            "indexUrl": f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}/{file_prefix}-index.json",
            "detailUrl": f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO_NAME}/{BRANCH}/{file_prefix}-detay.json"
        })
    
    # Tüm dizileri tek bir dosyada birleştir (pretty format - alt alta)
    if all_series:
        with open("tum_diziler.json", "w", encoding="utf-8") as f:
            json.dump(all_series, f, indent=2, ensure_ascii=False)
        print(f"\n📦 tum_diziler.json oluşturuldu (Toplam {len(all_series)} dizi)")
    
    # Ana index.json'u oluştur (pretty format)
    with open("index.json", "w", encoding="utf-8") as f:
        json.dump(main_index, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ index.json oluşturuldu ({len(main_index)} kategori)")
    print("\n" + "=" * 50)
    print("🎉 İŞLEM TAMAMLANDI!")
    print("\n📱 Uygulamada kullanılacak URL:")
    print("   https://raw.githubusercontent.com/braveheart1983/atakseries/main/index.json")
    print("\n📁 Oluşturulan dosyalar:")
    for item in os.listdir("."):
        if item.endswith(".json"):
            size_kb = os.path.getsize(item) / 1024
            print(f"   - {item} ({size_kb:.1f} KB)")

if __name__ == "__main__":
    main()
