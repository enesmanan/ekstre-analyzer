# KVKK Aydınlatma Metni (İskelet)

Durum: taslak · Yazılacağı faz: [Faz 4](phases/faz-4-auth-admin.md) F4-T12 · Kaynak: [security-kvkk.md](security-kvkk.md) §1 veri envanteri

Bu dosya kayıt ekranından linklenir. Aşağıdaki başlıklar zorunludur; metin hukuki görüşle tamamlanır.

1. **Veri sorumlusu** — ad/unvan, adres, e-posta. [NETLEŞTİRİLMELİ: gerçek kişi mi şirket mi]
2. **İşlenen kişisel veriler** — e-posta, şifre hash'i, maskelenmiş ekstredeki işlem satırları (tarih, açıklama, tutar, işyeri), harcama özetleri, IP ve tarayıcı bilgisi. Özel nitelikli veri uyarısı: işlem satırları sağlık harcaması (eczane, hastane) içerebilir.
3. **İşleme amaçları** — harcama analizi ve kategorileme, dönem özeti ve tavsiye üretimi, hesap güvenliği.
4. **Hukuki sebep** — sözleşmenin ifası (hizmet), açık rıza (yurt dışına aktarım ve özel nitelikli veri), meşru menfaat (güvenlik logları).
5. **Yurt dışına aktarım** — veriler Google Cloud (Belçika, `europe-west1`) üzerinde saklanır; maskelenmiş ekstre ve harcama özeti Google Gemini API'ye (ücretli tier; Google ürün geliştirmede kullanmaz) gönderilir. Bu aktarım için açık rıza ayrı kutu ile alınır.
6. **Maskelemenin sınırı** — kimlik, hesap, kart ve iletişim bilgileri sunucuda maskelenir; işlem açıklamalarındaki üçüncü kişi adları ve işyeri adları tamamen maskelenemeyebilir. Orijinal ekstre saklanmaz.
7. **Saklama süreleri** — hesap silinene kadar; yedeklerden silinme en geç 30 gün; güvenlik logları 90 gün; maskelenmiş PDF yalnızca kullanıcı açarsa, kullanıcı silene kadar ve en geç 90 gün (bucket lifecycle).
8. **Haklar** — KVKK md. 11: bilgi talebi, düzeltme, silme, itiraz, veri taşınabilirliği (uygulama içi "Verilerimi indir" ve "Hesabı sil").
9. **Başvuru yolu** — e-posta adresi; 30 gün içinde yanıt.
10. **Güncelleme tarihi** — ____
