# simdi — Case Study: Sektör Sözlüğü (NACE → Halk Dili Eşleme)

## Merhaba İlhan,

Önce şunu söyleyelim: bu case study'yi sana özel hazırladık — herkese giden standart bir ödev değil. CV'ne baktığımızda gördüğümüz şeyler bizim her gün uğraştığımız problemin tam kalbinde duruyor. Leagle'da bir milyondan fazla belge üzerinde kurduğun RAG ajanı, Jotform'da açık kaynakladığın değerlendirme framework'ü (Warden), ve özellikle BILGE ile modellerin Türkçede nasıl tökezlediğini ölçen çalışman — bunlar bizi durdurup "bu arkadaşla konuşmalıyız" dedirtti. O yüzden sana soyut bir algoritma sorusu çözdürmek yerine, burada gerçekten yapacağın işin küçük ama gerçek bir kesitini vermek istedik. Hem sen işin nasıl bir his olduğunu gör, hem biz senin nasıl düşündüğünü görelim.

Biz kimiz: **simdi**, Türkiye'deki KOBİ'ler için yapay zekâ destekli bir iş operasyonları platformu kuruyoruz. Küçük ve hızlı bir ekibiz — burada bir kişinin yazdığı şey raflarda beklemez, doğrudan gerçek müşterilere gider. İşimiz dağınık, gerçek, Türkçe veriyle; steril laboratuvar problemleriyle değil. Bu yüzden bizde teknik beceri kadar **yargı**, **dürüstlük** ve "neyi yapmayacağına karar verebilmek" de değerli. Aşağıdaki görev tam olarak bunu yokluyor.

Acele etme, ama mükemmelleştirmeye de çalışma. Bizi asıl ilgilendiren çıktının her satırı değil, oraya nasıl vardığın.

## Bağlam

simdi, Türkiye KOBİ'lerine yönelik bir yapay zekâ iş operasyonları platformu. Kullanıcı kaydolurken sektörünü belirtiyor; biz de ona uygun araçları öne çıkarıyoruz.

Sorun şu: kullanıcı kendini **kendi diliyle** tanımlar — "galericiyim", "nalburum", "kuyumcuyum". Oysa resmi sınıflama (NACE) **resmi dille** konuşur — "Motorlu kara taşıtlarının ticareti". Bu ikisi arasında köprü yok. Galerici, NACE listesinde "galerici" diye bir terim aramaz; bizim onu doğru yere oturtmamız gerekir.

Üç katmanlı bir yapı kurduk:

- **Layer 1 — Kaba sektör (10 kova):** `manufacturing`, `trade`, `food`, `textile`, `construction`, `logistics`, `technology`, `services`, `agriculture`, `other`. Araç önerisini bu besliyor.
- **Layer 2 — NACE düğümleri:** resmi, eksiksiz omurga. Her düğüm tam olarak bir Layer 1 kovasına bağlı.
- **Layer 3 — Halk dili meslek etiketleri:** kullanıcının yazdığı/seçtiği şey. **Eksik olan, üretmeni istediğimiz kısım bu.**

## Görev

Layer 3'ü üret. Yani: bir kullanıcının kendini tanımlarken yazacağı serbest-metin meslek/sektör ifadelerini doğru NACE düğümüne, oradan da doğru Layer 1 kovasına eşleyen bir yapı kur.

**Kapsam: tüm kovalar.** Tek bir sektörle sınırlı değil — sistemin herhangi bir KOBİ'yi karşılayabilmesi gerekiyor.

Bizim asıl ilgilendiğimiz çıktı bir **liste değil, tekrarlanabilir bir yöntem.** Yarın elimize farklı bir kontrollü sözlük ya da farklı bir kaynaktan gelen serbest-metin veri geldiğinde, aynı yöntemi yeniden çalıştırabilmek istiyoruz. Bunu aklında tut.

## Sana sağlananlar

- **NACE Rev.2 (TR) resmi faaliyet listesi** (ekte) — kod + resmi ad.
- Yukarıdaki **10 Layer 1 kovası** ve kısa anlamları.

## Beklenen çıktılar

1. **Eşleme tablosu** — yüklenebilir ve temiz bir biçimde (ör. CSV/JSON). Her satır: bir serbest-metin/alias terim → NACE kodu → Layer 1 kovası, beraberinde bir güven değeri ve kaynağın (provenance) ne olduğu.
2. **Çözümleyici (resolver)** — verilen serbest-metin bir girdi için ("oto galericisiyim") sıralı NACE adaylarını ve kovayı döndüren çalışır bir fonksiyon/servis. Prod-grade olması gerekmiyor; **çalışan, yeniden üretilebilir bir prototip yeterli.**
3. **Kısa değerlendirme** — yöntemin ne kadar işe yaradığını gösteren küçük bir test. Kendi oluşturacağın gerçekçi girdilerle bir isabet ölçümü (ör. top-1 / top-3) yeterli.
4. **Yöntem notu (1–2 sayfa)** — nasıl ürettin, hangi kaynakları ve teknikleri kullandın, nerede ödünleşme (tradeoff) yaptın, neyi kapsam dışı bıraktın ve neden.

## Neye bakıyoruz

- **Kapsam yargısı:** Her NACE kodunu tek tek alias'lamaya mı kalkıyorsun, yoksa gerçek bir KOBİ'nin yazacağı yüksek-frekanslı kümeye mi odaklanıp uzun kuyruğu ayrı bir mekanizmayla mı çözüyorsun?
- **Tekrarlanabilirlik:** Elle mi yazdın, yoksa ölçeklenen bir akış (pipeline) mı kurdun? "Tüm kovalar" bunun için var — yöntemin ölçeklenip ölçeklenmediğini görmek istiyoruz.
- **Belirsizlik:** Bazı terimler birden fazla düğüme oturur, bazı düğümler birden çok terime karşılık gelir. Örneğin "oto galerici" satış mı, tamir mi? Bu tür durumları nasıl ele alıyorsun?
- **Doğrulama:** Çıktının doğruluğunu nasıl ölçtün? Ürettiğin şeye körlemesine güvenmek yerine kontrol ettin mi?
- **Temizlik ve anlatım:** Çıktı düzenli ve yüklenebilir mi? Kararlarının nedenini açıkça anlatabiliyor musun?

## Sınırlar ve beklentiler

- Kabaca **bir günlük efor** düşün — süre kısıtlı (son teslim aşağıda). Mükemmelleştirmeye uğraşma; yöntemi **uçtan uca çalışır göstermek**, yüzde yüz kapsamadan daha önemli.
- **Takıldığın ya da belirsiz bulduğun her yeri sorabilirsin.** Soru sorman eksi değil, artı sinyal.
- Hangi dilleri, kütüphaneleri ve araçları kullanacağın tamamen sana kalmış.

## Teslim

**Son teslim: en geç Cumartesi (13 Haziran) sabah 09:00.**

Çalışmanı bir Git deposu olarak paylaş (kod + çıktı tablosu + yöntem notu). Sonrasında kısa bir görüşmede yöntemini ve verdiğin kararları birlikte konuşacağız.
