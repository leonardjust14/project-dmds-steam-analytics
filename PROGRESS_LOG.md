# Progress Log — DMDS Steam Analytics

## 2026-06-13 — Review kesiapan demo + investigasi Q3

### Status awal
- `app.py` + Q1/Q2/Q3 ternyata **sudah lengkap** (lebih maju dari catatan sebelumnya yang masih bilang TODO).
- Kedua DB (`mysql-steam-tugas` port 3307, Mongo container `PDDS` port 27017) jalan normal setelah `docker start PDDS`.

### Insight aktual dari tiap Q (dijalankan langsung)
- **Q1 (MySQL only, 27K game)**: $5-15 & $15-30 punya positive ratio tertinggi (~75%). **$0-5 justru terendah (68.4%)** — kemungkinan shovelware/asset-flip, worth disebut sebagai insight tambahan.
- **Q2 (Mongo tags + MySQL sentiment)**: konsisten dengan narasi yang sudah ditulis di app.py — Action/Casual dominan volume (72-73%), niche genre (Pixel Graphics 83.5%, Visual Novel 83.4%, Puzzle 82.3%) rating tertinggi.
- **Q3 (Mongo reviews + MySQL release_date)**: **BERMASALAH** — dari 221 game yang dianalisis, hanya **3 Free-to-Play vs 218 Paid**. Perbandingan FTP vs Paid jadi tidak meaningful secara statistik (n=3).

### Root cause Q3
`fix_etl_mongo.py` (versi lama) ambil 200 appid pertama yang ketemu berurutan di `steam_reviews.csv` (7.6GB) — kebetulan didominasi game lama/AAA berbayar (Half-Life, Portal, CS:Source, dst).

### Yang sudah dicoba (hari ini)
1. **Rewrite `fix_etl_mongo.py`** jadi stratified: ambil daftar appid FTP (price=0) dari MySQL dulu (2.556 game), lalu scan CSV cari kombinasi 40 game FTP + 160 game Paid.
   - Hasil: scan 8M baris pertama (40 chunk x 200K) → **0 game FTP ditemukan**, 101 game Paid. Collection di-drop & diisi ulang dengan ini (80.100 dokumen, 101 appid unik, semua Paid).
2. **`fix_etl_mongo_phase2.py`** (vectorized `isin` filter, chunk 500K) — scan lanjutan dari awal file mencari appid FTP saja.
   - Chunk 1-17 (8.5M baris): 0 FTP.
   - Chunk 18: ketemu 1 FTP (Phasmophobia).
   - Chunk 18-31 (total 15.5M baris / ~31% file, ~37 menit): tetap cuma **1 FTP**.
   - Dihentikan manual (`TaskStop`) — rate ~1 FTP per 15M baris, untuk dapat 5+ FTP butuh ~1 jam scan lagi. Hasil phase2 **belum di-insert** ke Mongo (proses dihentikan sebelum tahap insert).

### State Mongo SAAT INI
- `Steams_Analytics.User_Reviews`: **80.100 dokumen, 101 appid unik, SEMUA Paid (0 FTP)**.
- Ini lebih buruk dari kondisi awal (3 FTP) untuk keperluan Q3 FTP-vs-Paid — **Q3 saat ini akan error/kosong untuk kategori FTP** kalau dijalankan sekarang (`df_ret[df_ret.price_category=="Free-to-Play"]` akan empty).

### Kesimpulan
Dataset `steam_reviews.csv` (diurutkan kira-kira berdasarkan volume review, AAA besar di awal) **sangat dominan game Paid** — game FTP populer (Dota 2, CS:GO, dll mungkin tidak ada di dataset ini sama sekali, atau sangat jauh di belakang file). Mengejar sample FTP yang balanced via brute-force scan **tidak realistis** dalam waktu tersisa.

### Rekomendasi / next step (belum dieksekusi, nunggu keputusan)
**Reframe Q3** — ganti framing dari "FTP vs Paid retention" jadi salah satu:
- "Retention vs Popularitas Game" (pakai 101 game yang sudah ada, no imbalance issue)
- "Retention vs Price Tier" (reuse bucket Q1: Free/$0-5/$5-15/$15-30/$30+)

### Action items
- [ ] Putuskan framing baru Q3
- [ ] Update `analysis/q3_retention.py` sesuai framing baru
- [ ] Update teks insight & chart di `app.py` tab 3
- [ ] (Opsional) kalau mau tetap FTP vs Paid: jalankan ulang `fix_etl_mongo_phase2.py` dengan target lebih rendah (misal 3-5 FTP) dan biarkan jalan ~1 jam penuh
