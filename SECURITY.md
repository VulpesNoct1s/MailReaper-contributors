# Güvenlik Politikası

## Tehdit modeli

MailReaper **yalnızca yerel kullanım** için tasarlanmıştır. Arayüzde kimlik doğrulama yoktur ve
sunucu varsayılan olarak `127.0.0.1` üzerinde dinler. Uygulamayı internete veya paylaşılan bir ağa açma;
`MAILREAPER_HOST` değişkenini `0.0.0.0` yapmak, ağdaki herkesin arama geçmişine ve soruşturma dosyalarına erişmesi anlamına gelir.

Flask hata ayıklama modu (Werkzeug konsolu) bilerek kapalıdır.

## Açık bildirme

Güvenlik açığı bulduysan lütfen herkese açık bir issue açma. Depo sahibine GitHub'ın
**Security → Report a vulnerability** özelliğiyle özel olarak bildir. Mümkünse şunları ekle:

- Etkilenen sürüm / commit
- Yeniden üretme adımları
- Beklenen ve gözlenen davranış

## Kapsam dışı

- Üçüncü taraf sitelerin (GitHub, Reddit, crt.sh, vb.) kendi güvenlik sorunları
- Aracın yetkisiz hedeflere karşı kullanılması — bu, kullanıcı sorumluluğundadır (bkz. README → Sorumlu kullanım)
