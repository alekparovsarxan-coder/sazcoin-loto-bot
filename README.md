# SazCoin Loto Bot

Telegram loto botu — sazcoin balans sistemi, avtomatik tirajlar, admin paneli.

## Xüsusiyyətlər

- Daimi işləyən tirajlar (1 / 5 / 10 dəqiqə + gündəlik 21:00)
- Real müştəri sayına görə qalib müəyyən etmə
- Kassanın faizinə uyğun uduş (60% / 50% / 40%)
- Telegram Stars ilə balans artırma
- Adminə yazaraq balans artırma
- Çıxarış sistemi (10% xidmət haqqı, yalnız uduşdan)
- Tam admin paneli

## Quraşdırma

1. Bot yaradın: @BotFather → /newbot → tokeni götürün
2. Öz Telegram ID-nizi öyrənin: @userinfobot
3. `config.py` faylını redaktə edin:

```python
BOT_TOKEN = "123456:ABC..."
ADMIN_IDS = [987654321]  # sizin ID
```

4. Asılılıqları quraşdırın:

```bash
pip install -r requirements.txt
```

5. Botu işə salın:

```bash
python main.py
```

## Fayl strukturu

```
sazcoin_loto_bot/
├── main.py              # Başlanğıc + scheduler
├── config.py            # Bütün tənzimləmələr
├── requirements.txt
├── database/
│   └── db.py            # SQLite əməliyyatları
├── handlers/
│   ├── user.py          # İstifadəçi komandaları
│   └── admin.py         # Admin paneli
├── keyboards/
│   └── inline.py
└── services/
    └── draw_service.py  # Tiraj məntiqi
```

## Vacib qeydlər

- Bot VPS-də (və ya daimi işləyən kompüterdə) işləməlidir.
- Scheduler hər 15 saniyədə bitmiş tirajları yoxlayır.
- Gündəlik tiraj hər gün saat 21:00-da avtomatik yaradılır.
- Çıxarış tələbləri adminə mesaj olaraq gəlir.

## Sonrakı inkişaf (istəsəniz)

- Platega.io real ödəniş inteqrasiyası
- Force-win (konkret adamı qalib seçmək)
- Çox uduzanlara avtomatik bildiriş
- Referal sistem
