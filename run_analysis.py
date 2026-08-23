import os
import sys
import requests
import google.generativeai as genai

from analyzer import ringkas_data
from news import ambil_berita
from history import tambah_sinyal

# ==== Ambil dari GitHub Secrets (environment variables) ====
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# sesi dikirim sebagai argumen dari workflow: "pagi" atau "sore"
SESI = sys.argv[1] if len(sys.argv) > 1 else "pagi"

WATCHLIST = ["BBRI.JK", "BBCA.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"]

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")  # gratis, kuota harian cukup besar


def kirim_telegram(teks):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": teks,
        "parse_mode": "Markdown",
    })


def buat_prompt(data_list, berita, sesi):
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
        baris.append(
            f"- {d['ticker']}: harga {d['harga']:.0f}, perubahan {d['perubahan_persen']:.2f}%, "
            f"RSI {rsi}, MA20 {ma20}, MA50 {ma50}, volume {d['volume']:.0f} (avg20: {vol_avg})"
        )
    data_teks = "\n".join(baris)

    berita_teks = "\n".join(f"- {b}" for b in berita) if berita else "Tidak ada berita relevan."

    prompt = f"""Kamu adalah asisten analisis saham untuk trader retail Indonesia.
{konteks_sesi}

Data teknikal saham hari ini:
{data_teks}

Berita pasar terbaru:
{berita_teks}

Tugas kamu:
1. Untuk tiap saham, beri kesimpulan singkat: BELI / TAHAN / JUAL / HINDARI, dengan alasan 1-2 kalimat berdasarkan RSI, MA, volume, dan berita jika relevan.
2. Tutup dengan catatan singkat bahwa ini bukan saran finansial resmi dan risiko ditanggung sendiri.
3. Gunakan bahasa Indonesia santai tapi jelas, format dengan bullet point per saham, jangan bertele-tele.
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


def main():
    data_list = [ringkas_data(t) for t in WATCHLIST]
    berita = ambil_berita(jumlah=4)

    prompt = buat_prompt(data_list, berita, SESI)
    response = model.generate_content(prompt)
    hasil = response.text

    label = "🌅 Sinyal Pagi" if SESI == "pagi" else "🌇 Sinyal Sore"
    kirim_telegram(f"*{label}*\n\n{hasil}")

    # simpan tiap sinyal ke riwayat, buat dievaluasi nanti
    for d in data_list:
        if not d:
            continue
        sinyal = label_sinyal_sederhana(d)
        tambah_sinyal(d["ticker"], sinyal, d["harga"], tipe=f"reguler-{SESI}")


if __name__ == "__main__":
    main()
