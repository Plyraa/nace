# Yöntem Notu

Bu çalışmada hedefim "NACE'i baştan sınıflandırmak" değil, verilen sözlüğü kullanarak halk dili ile resmi kodlar arasında çalışan bir köprü kurmaktı. Kullanıcı "bakkalım", "oto galericisiyim", "nalburum" gibi kısa ve çoğu zaman eksik ifadeler yazıyor. Elimizdeki resmi taraf ise uzun NACE tanımları. Aradaki en değerli şey Excel'deki `MESLEK TANIM` alanı: resmi kod kadar kuru değil, kullanıcı dili kadar da dağınık değil.

Bu yüzden alias üretimini 1.531 NACE satırı üzerinden değil, 184 meslek düğümü üzerinden yaptım. Örneğin `Bakkallık, bayilik, büfecilik` tek bir kullanıcı niyetine yakın duruyor ama altında çok sayıda NACE kodu var. Alias'ı bu düğümde üretip bağlı kodlara yaymak hem daha ucuz, hem de dosyanın içindeki çoktan-çoğa yapıyı bozmuyor.

## Veri

İlk script (`scripts/01_ingest.py`) Excel'i okuyup başlıkları temizliyor. Kaynak dosyada `NACE REV. 2.1 KODU ` başlığının sonunda boşluk vardı; bunu ingest sırasında normalize ettim. Çıktılar:

- `data/nace_clean.csv`
- `data/nace_clean.parquet`
- `data/meslek_nodes.csv`
- `data/profile.json`

Profilde çıkan ana sayılar:

- 1.531 satır
- 184 tekil meslek düğümü
- 1.531 tekil NACE kodu
- null yok
- bir meslek düğümü 1 ile 92 arasında NACE koduna bağlanabiliyor

Bu son madde önemli. "Bir meslek = bir NACE" gibi davranmak burada yanlış olurdu. Resolver top-k dönüyor; alias tablosunda da aynı alias'ın birden fazla meslek/kodla ilişkisi korunuyor.

## 10 Kova Eşlemesi

Layer-1 için basit ve inspect edilebilir bir çözüm kullandım:

- `data/division_to_bucket.csv`: NACE division, yani ilk iki hane, hangi kovaya gidiyor?
- `data/bucket_exceptions.csv`: division seviyesinin fazla kaba kaldığı yerler.

Mesela `47` genel olarak trade, ama `47.11` ve `47.2x` gibi gıda perakendesi kodlarını `food` kovasına almak daha mantıklı. Benzer şekilde tekstil perakendesi `textile`, bilgisayar/telekom onarımları `technology` tarafına çekildi.

Bu mapping production-grade bir uzman sınıflandırması iddiasında değil. Case için yeterince açık, hızlı değiştirilebilir ve her kodu tek kovaya düşüren bir layer.

## Alias Tablosu

Alias üretiminde iki kaynak var.

`source-vocab` tarafı deterministik. Meslek tanımının kendisi, virgül/`ve` ile ayrılmış parçalar, basit Türkçe sonek kırpımları ve birkaç yaygın synonym kullanılıyor. Örnekler:

- `Terzilik` -> `terzi`
- `Hırdavatçılık` -> `nalbur`
- `Kara yolu ile yük taşımacılığı` -> `nakliyeci`
- `Oto galericilik, oto kiralama` -> `galerici`, `oto galerici`

`llm-generated` tarafı her meslek düğümü için OpenRouter üzerinden alias üretiyor. Model string tek yerde duruyor: `config.py`. Şu an `deepseek/deepseek-v4-flash`, temperature `0.2`.

LLM tarafında özellikle iki şeye dikkat ettim:

1. Her çağrı content hash ile `cache/` altına yazılıyor.
2. Repo API key olmadan tekrar çalışıyor.

Bu yüzden `run.cmd` fresh clone'da `OPENROUTER_API_KEY` boşken de çalışıyor. Cache'i commit etmek normalde her projede tercih edeceğim bir şey değil; burada case'in açık gereği buydu.

Final alias tablosu `output/alias_table.csv`:

- 24.456 satır
- kolonlar: `alias`, `normalized_alias`, `nace_code`, `nace_label`, `bucket`, `confidence`, `provenance`, `ambiguous`
- aynı normalize alias birden fazla meslek düğümüne gidiyorsa `ambiguous=true`

## Resolver

`resolver.py` içinde tek public fonksiyon var:

```python
resolve(text: str, k: int = 3) -> list[Candidate]
```

Akış şu:

1. Normalize et.
   Türkçe casing, noktalama temizliği, basit deasciify, `-cıyım/-im`, `dükkanım var`, `yapıyorum` gibi kalıplar temizleniyor.

2. Exact alias match dene.
   `normalized_alias` birebir tutarsa yüksek skorla dönüyor.

3. Fuzzy match dene.
   RapidFuzz `token_set_ratio` kullanılıyor. Eşik yaklaşık 85.

4. Gerekirse LLM fallback.
   Burada model serbestçe NACE uyduramıyor. Önce NACE açıklamaları ve meslek etiketleri üzerinden yaklaşık 30 adaylık shortlist çıkarıyorum. Prompt'a sadece bu adaylar gidiyor. Dönen kod tabloda yoksa kabul edilmiyor.

Bu tasarımda LLM ana sınıflandırıcı değil. Önce ucuz ve deterministik yol deneniyor; LLM sadece zayıf/uzun kuyruk durumlarda devreye giriyor.

Skor kullanımı için pratik kural: en iyi skor `0.86+` ve ikinci adayla fark `0.08+` ise otomatik atama düşünülebilir. Diğer durumlarda top-3'ü göstermek daha doğru. Özellikle `galerici`, `servisçi`, `boyacı`, `pazarcı` gibi kelimelerde tek cevap varmış gibi davranmak riskli.

## Eval

Eval seti `eval/test_cases.csv` içinde. 70 örnek var:

- kolay baş terimler: `bakkal`, `berber`, `kasap`
- ekli formlar: `bakkalım`, `lokantacıyım`
- belirsiz ifadeler: `galerici`, `tatlıcı`, `servisçi`
- typo/deasciify: `kuafor`, `börber`, `insaatciyim`
- uzun kuyruk: `drone ile düğün çekiyorum`, `evden pasta yapıp satıyorum`

Gold NACE listeleri alias tablosundan değil, temizlenmiş resmi mapping'den `meslek_kodu` üzerinden dolduruldu. Bunu özellikle yaptım; alias üretildikten sonra test yazmak kolayca kontaminasyon yaratırdı.

Son keyless koşu:

- Top-1 NACE accuracy: `0.8714`
- Top-3 NACE accuracy: `0.8857`
- Bucket accuracy: `0.8000`
- LLM fallback: `10 / 70`

Kategori bazında top-1:

- easy: `1.00`
- suffix: `0.90`
- ambiguous: `0.80`
- typo: `0.80`
- long_tail: `0.80`

Bucket accuracy'nin daha düşük çıkması şaşırtıcı değil. Bazı meslek düğümleri resmi olarak birkaç kovaya yayılıyor. Örneğin bakkal/bayi/pazar gibi örneklerde hem gıda hem trade tarafı var. Bu prototip her NACE koduna tek bucket veriyor; kullanıcı niyetini ayrıca sormuyor.

## Nerede Bilerek Kıstım?

Tam validasyon yapmadım. İkinci LLM pass sadece örneklem üzerinde çalışıyor: 150 satır seçildi, 140 satır için kullanılabilir verdict geldi. `no` ve `unsure` confidence düşürüyor. Bu, mekanizmayı göstermek için yeterliydi; 24k satırı tekrar LLM'e doğrulatmak bir günlük scope için iyi maliyet değil.

Embedding eklemedim. Prod'da fallback tarafını muhtemelen cached embeddings + reranker ile kurardım. Burada RapidFuzz + shortlist + cached LLM daha hızlı bitti ve daha kolay okunuyor.

Çok faaliyetli işletmeleri çözmedim. "Hem pasta yapıyorum hem kafe işletiyorum" gibi bir girdi için doğru ürün davranışı muhtemelen follow-up soru sormak veya multi-label dönmek olurdu. Bu case'te top-3 aday döndürmekle sınırladım.

Bucket mapping'i uzman review'dan geçmedi. Division-level mapping + birkaç exception var. Bu kasıtlı: mapping'in nerede durduğunu açıkça görmek, gizli model kararından daha iyi.

## En Zayıf Noktalar

Birincisi bucket tarafı. NACE top-1 iyi görünse de bucket accuracy daha düşük. Çünkü resmi kod doğru ailede olsa bile seçilen ilk kodun bucket'ı kullanıcının beklediği kaba sektörden sapabiliyor.

İkincisi typo coverage. `kuafor` gibi sık örnekler iyi; ama `börber` gibi daha bozuk yazımlar bazen LLM'e kalıyor. Bunu production'da gerçek kullanıcı loglarıyla genişletmek gerekir.

Üçüncüsü LLM fallback skorları. Model bazı uzun kuyruklarda doğru semantik yakalıyor, bazılarında yüksek confidence ile yanlış dönebiliyor. Bu yüzden fallback'i auto-assign için değil, top-3 öneri için kullanmak daha güvenli.

## Bir Hafta Daha Olsa

Önce gerçek kullanıcı girdilerinden daha iyi bir eval seti yapardım. Sonra bucket mapping'i domain review ile düzeltirdim. Ardından LLM fallback'i embedding shortlist + reranker ile değiştirirdim. En son da ambiguous girdiler için follow-up soru mekanizması eklerdim.

Bu haliyle repo hedeflediğim şeyi yapıyor: Excel'den başlayıp alias tablosu, resolver, eval raporu ve yöntem notunu tekrar üretilebilen bir pipeline olarak veriyor. Mükemmel coverage değil; ama çalışan, ölçülen ve nerede zayıf olduğu belli bir prototip.
