"""
Veri toplama paketi.

Paket içindeki scriptler ilerlemeyi ✓/✗ gibi işaretlerle yazdırıyor.
Windows'ta stdout sistemin kod sayfasını kullandığı (bu makinede cp1254)
ve çıktı bir dosyaya yönlendirildiğinde de bu değişmediği için, bu
karakterleri yazdırmak UnicodeEncodeError fırlatıp scripti düşürüyordu —
üstelik iş (API çağrısı, veritabanı yazımı) çoktan yapıldıktan sonra.

Çıktıyı paket seviyesinde UTF-8'e sabitliyoruz ki her yeni script bunu
ayrıca düşünmek zorunda kalmasın.
"""

from data_collection.console import force_utf8_output

force_utf8_output()
