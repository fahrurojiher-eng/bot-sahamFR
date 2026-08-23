# Setup Bot Saham — GitHub Actions + Gemini (100% Gratis, Tanpa Server)

## Cara Kerja
GitHub Actions menjalankan script otomatis 2x sehari (pagi & sore, hari kerja),
ambil data saham, minta Google Gemini bikin analisis, kirim ke Telegram kamu.
Tidak perlu laptop/server nyala — semua jalan di server GitHub gratis.

---

## 1. Buat Bot Telegram
1. Chat **@BotFather** di Telegram → `/newbot` → ikuti instruksi
2. Simpan **TOKEN** yang diberikan

## 2. Cari Chat ID Kamu
1. Chat bot kamu dengan pesan apa saja (misal "hi")
2. Buka: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Cari angka di `"chat": {"id": ...}` — itu Chat ID kamu

## 3. Buat API Key Gemini (Gratis)
1. Buka **https://aistudio.google.com/app/apikey**
2. Login pakai akun Google
3. Klik **Create API Key** → copy key-nya
   (free tier cukup untuk pakai 2x/hari seperti ini)

## 4. Buat Repository di GitHub
1. Buat akun GitHub kalau belum punya (github.com)
2. Buat repo baru, **boleh public boleh private** (public = menit Actions unlimited gratis)
3. Upload semua file yang saya buatkan (analyzer.py, news.py, run_analysis.py,
   requirements.txt, folder `.github/workflows/sinyal.yml`) ke repo tsb
   - Bisa lewat web GitHub (Add file → Upload files), atau `git push` kalau familiar

## 5. Simpan Token & Key sebagai Secrets (supaya aman, tidak keliatan publik)
Di repo GitHub kamu:
1. Masuk **Settings → Secrets and variables → Actions**
2. Klik **New repository secret**, buat 3 secret ini:
   - `TELEGRAM_BOT_TOKEN` → isi token dari BotFather
   - `TELEGRAM_CHAT_ID` → isi chat ID kamu
   - `GEMINI_API_KEY` → isi API key dari Google AI Studio

## 6. Aktifkan Actions
1. Masuk tab **Actions** di repo kamu
2. Kalau ada tombol "I understand my workflows, go ahead and enable them" → klik
3. Workflow **"Sinyal Saham"** otomatis jalan sesuai jadwal (08:45 & 14:30 WIB, hari kerja)

## 7. Tes Manual (opsional, biar cepat lihat hasilnya)
1. Masuk tab **Actions** → pilih workflow **Sinyal Saham**
2. Klik **Run workflow** (di kanan) → pilih sesi "pagi" atau "sore" → Run
3. Cek Telegram kamu, pesan harusnya masuk dalam 1-2 menit

---

## Fitur Tambahan

### 🔥 Scan Scalping
Jalan otomatis jam **10:00 & 12:00 WIB** (hari kerja). Bot scan ~30 saham likuid
(BBRI, BBCA, GOTO, ANTM, dll — bisa diedit di `scan_scalping.py` bagian `UNIVERSE`),
cari yang volume & momentumnya lagi naik, lalu kirim kandidat scalping ke Telegram.

### 📋 Evaluasi Sinyal
Jalan otomatis jam **15:50 WIB**. Bot cek semua sinyal yang sudah dikirim
(minimal 3 jam sebelumnya), bandingkan harga saat sinyal vs harga sekarang,
lalu kirim laporan mana yang **✅ benar** dan mana yang **❌ meleset**, plus
persentase akurasi keseluruhan.

Riwayat semua sinyal tersimpan di `signals_history.json` di repo kamu —
otomatis ter-update tiap kali workflow jalan (lewat auto-commit).

### Cara pakai manual (opsional)
Di tab **Actions**, klik **Run workflow**, pilih aksi: `pagi`, `sore`, `scalping`, atau `evaluasi`.

## Mengubah Watchlist / Jadwal
- Watchlist: edit list `WATCHLIST` di `run_analysis.py`
- Jadwal: edit bagian `cron` di `.github/workflows/sinyal.yml`
  (ingat: GitHub pakai waktu UTC, WIB = UTC + 7)

## ⚠️ Catatan
- Ini alat bantu analisis, **bukan rekomendasi resmi/nasihat finansial**.
- Gemini API gratis (aistudio.google.com) punya batas kuota harian — cukup untuk
  pemakaian 2x/hari seperti ini, tapi kalau dipakai berlebihan bisa kena limit.
- GitHub Actions gratis untuk repo public tanpa batas menit; repo private ada
  kuota ~2000 menit/bulan (script ini ringan, jauh di bawah itu).
- Jangan pernah upload TOKEN/API key langsung ke file — selalu lewat Secrets.
