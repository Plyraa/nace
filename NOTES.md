# Yöntem Notu

Bu prototip, verilen meslek-sektör sözlüğünü resmi NACE kodları ile halk dilindeki Türkçe işletme ifadeleri arasında köprü olarak kullanır. Ham NACE tanımlarını doğrudan alias'lamak yerine alias üretimini `MESLEK KODU / MESLEK TANIM` düğümleri üzerinden yaptım. Bunun nedeni, sağlanan dosyanın zaten yarı-kürate edilmiş bir ara katman içermesi: örneğin `Bakkallık, bayilik, büfecilik` birden fazla NACE koduna bağlı ama kullanıcı diline NACE tanımlarından daha yakın. Bu katmandan alias üretmek hem maliyeti düşürür, hem de çoktan-çoğa ilişkiyi korur.

## Veri ve Kova Eşlemesi

`scripts/01_ingest.py` Excel dosyasını okur, başlıkları temizler ve `data/nace_clean.csv` ile `data/meslek_nodes.csv` üretir. Profil sonucu:

- 1.531 NACE satırı
- 184 benzersiz meslek düğümü
- 1.531 benzersiz NACE kodu
- Kaynakta `NACE REV. 2.1 KODU ` başlığında sonda boşluk var; ingest bunu normalize ediyor.
- Bir meslek düğümü 1 ile 92 arasında NACE koduna bağlanabiliyor; bu çoktan-çoğa ilişki korunuyor.

Layer-1 kovaları için `data/division_to_bucket.csv` içinde bölüm düzeyi elle yazılmış bir eşleme var. `data/bucket_exceptions.csv` ise bölümün tek kovaya yetmediği yerleri düzeltir: örneğin `47.11`, `47.2x` ve bazı `46.3x` kodları `food`, tekstil perakendesi/toptanı `textile`, bilgisayar/telekom onarımları `technology`. Her NACE kodu resolver tarafında tam olarak bir kovaya düşer.

## Alias Üretimi

Alias tablosu iki kaynaktan oluşur:

- `source-vocab`: meslek tanımının kendisi, virgül/“ve” ile ayrılmış parçalar, basit Türkçe kök/sonek kırpımları ve az sayıda yüksek frekanslı deterministik eş anlamlı. Örnek: `Terzilik -> terzi`, `Hırdavatçılık -> nalbur`, `Kara yolu ile yük taşımacılığı -> nakliyeci`.
- `llm-generated`: her 184 meslek düğümü için bir OpenRouter çağrısı ile 5-15 halk dili alias. Çağrılar `config.py` içindeki tek model sabitiyle yapılır: `deepseek/deepseek-v4-flash`, sıcaklık `0.2`.

Tüm LLM çağrıları `llm_client.py` üzerinden geçer. İstek içeriği, model ve parametreler hash'lenir; yanıtlar `cache/*.json` olarak saklanır. Bu yüzden repo API anahtarı olmadan yeniden çalışır. Yanıt JSON değilse bir JSON-onarım çağrısı denenir. Üretim sonunda `output/alias_table.csv` şu kolonları içerir: `alias`, `normalized_alias`, `nace_code`, `nace_label`, `bucket`, `confidence`, `provenance`, `ambiguous`.

Belirsizlik gizlenmez. Aynı normalize alias birden fazla meslek düğümüne gidiyorsa `ambiguous=true` işaretlenir ve satırlar korunur. Resolver aynı NACE kodunu gruplayarak maksimum skoru alır ama farklı kodları atmaz; çağıran taraf top-3 gösterebilir.

## Resolver

`resolver.py` şu sırayla çalışır:

1. Türkçe duyarlı normalize: `İ/i`, `I/ı`, noktalama temizliği, basit deasciify, “dükkanım var”, “yapıyorum”, “-cıyım/-im” gibi kişi/işletme ifadeleri.
2. `normalized_alias` üzerinde exact match. Exact skor yüksek tutulur; alias güveni skoru küçük ölçüde etkiler.
3. RapidFuzz `token_set_ratio` ile fuzzy match. Eşik yaklaşık 85.
4. En iyi aday zayıfsa LLM fallback. Prompt'a kullanıcı metni, 10 kova açıklaması ve NACE/meslek metinlerinden fuzzy seçilmiş yaklaşık 30 gerçek kod verilir. Model yalnızca bu listeden top-3 seçebilir. Geçersiz kod veya parse sorunu olursa NACE açıklaması fuzzy shortlist'i düşük skorla döner.

Pratik karar eşiği: skor `0.86+` ve ikinci adayla fark `0.08+` ise otomatik atama yapılabilir; aksi halde top-3 gösterilmelidir. Bu eşik küçük eval setinde exact/fuzzy sonuçların genelde güvenilir, LLM fallback sonuçlarının ise daha değişken olmasına göre seçildi. Prod ortamında LLM fallback yerine cached embedding shortlist + reranker tercih ederdim; latency ve maliyet daha kontrol edilebilir olur.

## Değerlendirme

`eval/test_cases.csv` alias tablosuna bakmadan, temizlenmiş resmi kaynak kodları üzerinden hazırlandı. 70 örnek var: kolay baş terimler, ekli formlar, belirsiz ifadeler, typo'lar ve uzun kuyruk ifadeler.

Son keyless koşu sonucu:

- Top-1 NACE accuracy: 0.8714
- Top-3 NACE accuracy: 0.9000
- Bucket accuracy: 0.7571
- LLM fallback top-1 sayısı: 10 / 70
- Match type dağılımı: exact 49, fuzzy 11, LLM 10

Kategori kırılımı: easy top-1 `1.00`, suffix `0.90`, ambiguous `0.80`, typo `0.80`, long_tail `0.80`. Bucket accuracy daha düşük çünkü bazı meslek düğümleri resmi olarak birden fazla kovaya yayılıyor; örneğin pazar/elektrik/boya gibi ifadelerde resmi kod seçimi doğru meslek ailesinde kalsa bile ilk kodun kovası beklenen iş niyetinden farklı olabiliyor.

Validasyon adımı maliyet için örneklendi: 150 LLM-generated satır seçildi, model 140 satır için kullanılabilir verdict döndürdü; `no` ve `unsure` yanıtları confidence düşürdü. Bu bir kalite sinyali olarak yeterli, tam tabloyu ikinci kez etiketlemek bu kapsam için gereksiz maliyet olurdu.

## Bilinçli Kapsam Kesintileri

- Çok faaliyetli işletmeler ayrıştırılmadı. “Hem pasta yapıyorum hem kafe işletiyorum” gibi girdiler top-3 ile yüzeye çıkarılır.
- Nadir NACE kodları için özel alias avlanmadı; uzun kuyruk LLM fallback ve NACE açıklaması shortlist'i ile karşılanıyor.
- Servis/web API yok; istenen kapsam script + CSV + resolver fonksiyonu olduğu için CLI yeterli.
- Ağır NLP, morfolojik çözümleyici ve embedding altyapısı eklenmedi. Basit Türkçe normalize + RapidFuzz bu prototipte daha hızlı ve denetlenebilir.
- Bucket mapping üretim sınıfı bir vergi/NACE uzmanlığı iddiası taşımıyor; bölüm düzeyi pratik bir Layer-1 eşlemesi ve birkaç açık istisnadan oluşuyor.
