import os
import time
import requests
import google.generativeai as genai

from analyzer import ringkas_data
from news import ambil_berita
from history import tambah_sinyal

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Daftar saham likuid (bisa ditambah/kurangi sesuai selera)
UNIVERSE = [
    "BBRI.JK", "BBCA.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK",
    "UNVR.JK", "ICBP.JK", "ANTM.JK", "ADRO.JK", "PGAS.JK", "PTBA.JK",
    "MDKA.JK", "INCO.JK", "GOTO.JK", "BUKA.JK", "ARTO.JK", "BRIS.JK",
    "SMGR.JK", "INDF.JK", "KLBF.JK", "CPIN.JK", "AKRA.JK", "EXCL.JK",
    "ITMG.JK", "MEDC.JK", "ISAT.JK", "TOWR.JK", "AMRT.JK", "AVIA.JK",
]

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


def cocok_kriteria_scalping(d):
    """Kriteria kasar buat kandidat scalping: momentum + volume + belum overbought parah."""
    if not d or d["rsi"] is None or d["vol_avg20"] is None or d["ma20"] is None:
        return False
    volume_naik = d["volume"] > d["vol_avg20"] * 1.5
    momentum_ok = 45 <= d["rsi"] <= 70
    di_atas_ma20 = d["harga"] > d["ma20"]
    gerak_hari_ini = abs(d["perubahan_persen"]) >= 1.5
    return volume_naik and momentum_ok and di_atas_ma20 and gerak_hari_ini


def main():
    kandidat = []
    for ticker in UNIVERSE:
        d = ringkas_data(ticker)
        if cocok_kriteria_scalping(d):
            kandidat.append(d)

    if not kandidat:
        kirim_telegram("🔍 *Scan Scalping*\n\nTidak ada saham yang memenuhi kriteria momentum saat ini.")
        return

    berita = ambil_berita(jumlah=4)
    data_teks = "\n".join(
        f"- {d['ticker']}: harga {d['harga']:.0f}, perubahan {d['perubahan_persen']:.2f}%, "
        f"RSI {d['rsi']:.1f}, volume {d['volume']:.0f} (avg20: {d['vol_avg20']:.0f})"
        for d in kandidat
    )
    berita_teks = "\n".join(f"- {b}" for b in berita) if berita else "Tidak ada berita relevan."

    prompt = f"""Kamu asisten scalping saham untuk trader retail Indonesia (gaya cepat: beli-jual dalam hitungan jam/hari).

Kandidat saham dengan momentum & volume tinggi hari ini:
{data_teks}

Berita pasar terbaru:
{berita_teks}

Tugas kamu:
1. Ranking kandidat dari yang paling menarik untuk scalping, beri alasan singkat (momentum, volume, risiko).
2. Sebutkan level harga acuan kasar (entry area & area waspada/cut loss) berdasarkan data yang ada, tanpa klaim presisi tinggi.
3. Ingatkan singkat bahwa scalping berisiko tinggi, bukan saran resmi.
4. Bahasa Indonesia santai, ringkas, bullet point.

ATURAN PENTING: Bahas HANYA saham yang tercantum di "Kandidat saham" di atas. Jangan pernah
mengganti atau menambahkan saham lain (termasuk saham luar negeri) meskipun disebut di berita.
"""
    response = panggil_gemini(prompt)
    hasil = response

    kirim_telegram(f"🔥 *Kandidat Scalping Hari Ini*\n\n{hasil}")

    for d in kandidat:
        tambah_sinyal(d["ticker"], "SCALPING_BUY", d["harga"], tipe="scalping")


if __name__ == "__main__":
    main()
