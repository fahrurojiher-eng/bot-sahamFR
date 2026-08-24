import os
import sys
import time
import requests
import google.generativeai as genai

from analyzer import ringkas_data
from news import ambil_berita
from history import tambah_sinyal
from idx_scraper import ambil_top_saham_murah

# ==== Ambil dari GitHub Secrets (environment variables) ====
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# sesi dikirim sebagai argumen dari workflow: "pagi" atau "sore"
SESI = sys.argv[1] if len(sys.argv) > 1 else "pagi"

WATCHLIST = ["BBRI.JK", "BBCA.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]
HARGA_MAKS_MURAH = 300

# Daftar CADANGAN (fallback) - dipakai HANYA kalau scraping IDX real-time gagal.
WATCHLIST_MURAH_CADANGAN = ["BUMI.JK", "ENRG.JK", "DEWA.JK", "ELSA.JK", "WSKT.JK", "WIKA.JK"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.6-flash")  # model stabil terkini (bukan yg paling baru, jatah gratis lebih longgar)


def kirim_telegram(teks):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Coba kirim dengan format Markdown dulu
    resp = requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": teks,
        "parse_mode": "Markdown",
    })

    if resp.ok:
        print("Pesan Telegram berhasil terkirim (Markdown).")
        return

    print(f"Markdown gagal ({resp.status_code}): {resp.text}")
    print("Coba kirim ulang sebagai teks polos (tanpa formatting)...")

    # Fallback: kirim tanpa parse_mode (teks polos), paling aman, jarang gagal
    resp2 = requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": teks,
    })

    if not resp2.ok:
        print(f"GAGAL KIRIM TELEGRAM (plain text juga gagal): {resp2.status_code} - {resp2.text}")
        raise RuntimeError(f"Telegram sendMessage gagal total: {resp2.text}")
    else:
        print("Pesan Telegram berhasil terkirim (plain text, fallback).")


def hitung_level_trading(harga, tp_persen, sl_persen):
    """Hitung entry, take profit, dan stop loss berdasarkan harga saat ini + persentase target."""
    return {
        "entry": harga,
        "tp": harga * (1 + tp_persen / 100),
        "sl": harga * (1 - sl_persen / 100),
    }


def buat_prompt(data_list, berita, sesi, kode_saham_murah):
    konteks_sesi = (
        "User biasa beli saham pagi dan jual sore (scalping intraday)."
        if sesi == "pagi" else
        "User biasa beli saham sore dan jual besok pagi (overnight/swing pendek)."
    )

    baris = []
    for d in data_list:
        if not d:
            continue
        rsi = f"{d['rsi']:.1f}" if d["rsi"] is not None else "N/A"
        ma20 = f"{d['ma20']:.0f}" if d["ma20"] is not None else "N/A"
        ma50 = f"{d['ma50']:.0f}" if d["ma50"] is not None else "N/A"
        vol_avg = f"{d['vol_avg20']:.0f}" if d["vol_avg20"] is not None else "N/A"
        is_murah = d["ticker"] in kode_saham_murah
        tanda_murah = " [SAHAM HARGA RENDAH]" if is_murah else ""

        # Saham murah = target lebih lebar (lebih volatil)
        tp_pct, sl_pct = (4.0, 2.5) if is_murah else (2.5, 1.5)
        level = hitung_level_trading(d["harga"], tp_pct, sl_pct)
        d["level"] = level

        baris.append(
            f"- {d['ticker']}{tanda_murah}: harga {d['harga']:.0f}, perubahan {d['perubahan_persen']:.2f}%, "
            f"RSI {rsi}, MA20 {ma20}, MA50 {ma50}, volume {d['volume']:.0f} (avg20: {vol_avg}) | "
            f"Entry: {level['entry']:.0f} | Take Profit (+{tp_pct}%): {level['tp']:.0f} | "
            f"Stop Loss (-{sl_pct}%): {level['sl']:.0f}"
        )
    data_teks = "\n".join(baris)

    berita_teks = "\n".join(f"- {b}" for b in berita) if berita else "Tidak ada berita relevan."

    prompt = f"""Kamu adalah asisten analisis saham untuk trader retail Indonesia.
{konteks_sesi}

Data teknikal saham hari ini (saham dengan tanda [SAHAM HARGA RENDAH] adalah saham harga rendah/
"gorengan" yang jauh lebih volatil dan rawan manipulasi dibanding saham blue-chip lainnya.
Entry/Take Profit/Stop Loss SUDAH DIHITUNG, jangan diubah, tinggal jelaskan alasannya):
{data_teks}

Berita pasar terbaru:
{berita_teks}

Tugas kamu:
1. Untuk tiap saham, beri kesimpulan singkat: BELI / TAHAN / JUAL / HINDARI, dengan alasan 1-2 kalimat berdasarkan RSI, MA, volume, dan berita jika relevan.
2. WAJIB cantumkan angka Entry, Take Profit, dan Stop Loss PERSIS seperti yang sudah dihitung di atas untuk tiap saham - jangan menghitung ulang atau mengubah angkanya.
3. Untuk saham yang bertanda [SAHAM HARGA RENDAH], tambahkan catatan singkat soal risiko ekstra (volatilitas tinggi, rawan manipulasi/likuiditas tipis, potensi ARB/ARA mendadak) - jangan rekomendasikan BELI dengan percaya diri tinggi untuk jenis saham ini.
4. Tutup dengan catatan singkat bahwa ini bukan saran finansial resmi, angka TP/SL adalah target kasar berbasis persentase (bukan jaminan), dan risiko ditanggung sendiri.
5. Gunakan bahasa Indonesia santai tapi jelas, format dengan bullet point per saham, jangan bertele-tele.

ATURAN PENTING: Bahas HANYA saham yang tercantum di "Data teknikal saham hari ini" di atas.
Jangan pernah mengganti atau menambahkan saham lain (termasuk saham luar negeri) meskipun
disebut di berita. Kalau berita tidak relevan dengan saham-saham tsb, abaikan saja bagian berita.
"""
    return prompt


def label_sinyal_sederhana(d):
    """Sinyal rule-based sederhana, dipakai buat catatan riwayat (bukan yang ditampilkan)."""
    if not d or d["rsi"] is None or d["ma20"] is None or d["ma50"] is None:
        return "TAHAN"
    skor = 0
    if d["rsi"] < 30:
        skor += 2
    elif d["rsi"] > 70:
        skor -= 2
    if d["ma20"] > d["ma50"]:
        skor += 1
    else:
        skor -= 1
    if skor >= 2:
        return "BELI"
    elif skor <= -2:
        return "JUAL"
    return "TAHAN"


def panggil_gemini(prompt, percobaan_maks=3):
    """Panggil Gemini dengan retry otomatis kalau kena rate limit (error 429)."""
    for i in range(percobaan_maks):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            pesan_error = str(e)
            print(f"Percobaan {i+1} ke Gemini gagal: {pesan_error}")
            if "429" in pesan_error or "quota" in pesan_error.lower() or "rate" in pesan_error.lower():
                tunggu = 30 * (i + 1)
                print(f"Kena rate limit, tunggu {tunggu} detik sebelum coba lagi...")
                time.sleep(tunggu)
            else:
                raise
    raise RuntimeError("Gemini tetap gagal setelah beberapa kali percobaan (rate limit).")


def main():
    watchlist_murah = ambil_top_saham_murah(harga_maks=HARGA_MAKS_MURAH, jumlah=6)
    if watchlist_murah:
        print(f"Pakai {len(watchlist_murah)} saham murah dari IDX (real-time).")
    else:
        print("IDX gagal diakses, pakai daftar cadangan (fallback) untuk saham murah.")
        watchlist_murah = WATCHLIST_MURAH_CADANGAN

    semua_kode = WATCHLIST + watchlist_murah
    data_list_raw = [ringkas_data(t) for t in semua_kode]
    data_valid = [d for d in data_list_raw if d]

    if not data_valid:
        # Semua data gagal diambil -> jangan panggil AI (biar tidak ngarang saham lain)
        kirim_telegram(
            "⚠️ *Gagal ambil data saham*\n\n"
            "Data teknikal untuk semua saham di watchlist gagal diambil dari Yahoo Finance "
            "(kemungkinan server sedang diblokir/timeout). Sinyal tidak dikirim kali ini. "
            "Cek log run di GitHub Actions untuk detail error."
        )
        return

    berita = ambil_berita(jumlah=4)

    prompt = buat_prompt(data_valid, berita, SESI, kode_saham_murah=watchlist_murah)
    hasil = panggil_gemini(prompt)

    label = "🌅 Sinyal Pagi" if SESI == "pagi" else "🌇 Sinyal Sore"
    kirim_telegram(f"*{label}*\n\n{hasil}")

    # simpan tiap sinyal ke riwayat, buat dievaluasi nanti
    for d in data_valid:
        sinyal = label_sinyal_sederhana(d)
        tambah_sinyal(d["ticker"], sinyal, d["harga"], tipe=f"reguler-{SESI}")


if __name__ == "__main__":
    main()
