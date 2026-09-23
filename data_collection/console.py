"""
Konsol çıktısı için ortak yardımcı.

Windows'ta stdout, sistemin kod sayfasını kullanıyor (bu makinede cp1254);
çıktı bir dosyaya ya da pipe'a yönlendirildiğinde de durum değişmiyor.
Toplayıcıların bastığı ✓/✗ gibi karakterler bu kod sayfasında bulunmadığı
için print() UnicodeEncodeError fırlatıyordu. Bu hata YouTube aramaları
(kota harcayan kısım) bittikten SONRA, sadece sonucu yazarken oluştuğu ve
üst katmandaki try/except tarafından "üniversite başarısız" sayıldığı için
kota boşa gidiyor, hiçbir yorum kaydedilmiyordu.
"""

import sys


def force_utf8_output():
    """stdout/stderr'i UTF-8'e sabitler; kod sayfası kaynaklı çökmeyi önler."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
