import os
import time
import requests
import google.generativeai as genai

from analyzer import ringkas_data
from news import ambil_berita
from history import tambah_sinyal
from idx_scraper import ambil_top_saham_murah

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# Daftar saham likuid / blue chip (bisa ditambah/kurangi sesuai selera)
UNIVERSE = [
    "BBRI.JK", "BBCA.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK",
    "UNVR.JK", "ICBP.JK", "ANTM.JK", "ADRO.JK", "PGAS.JK", "PTBA.JK",
    "MDKA.JK", "INCO.JK", "GOTO.JK", "BUKA.JK", "ARTO.JK", "BRIS.JK",
    "SMGR.JK", "INDF.JK", "KLBF.JK", "CPIN.JK", "AKRA.JK", "EXCL.JK",
    "ITMG.JK", "MEDC.JK", "ISAT.JK", "TOWR.JK", "AMRT.JK", "AVIA.JK",
]

# Daftar CADANGAN (fallback) - dipakai HANYA kalau scraping IDX gagal.
# Kalau kamu tau kode saham murah favorit lain, tinggal tambahkan di sini (format: KODE.JK).
UNIVERSE_SAHAM_MURAH_CADANGAN = [
    "BUMI.JK", "ENRG.JK", "DEWA.JK", "ELSA.JK", "MYRX.JK", "SIAP.JK",
    "TRAM.JK", "BRMS.JK", "KRAS.JK", "WSKT.JK", "WIKA.JK", "WEGE.JK",
    "PGEO.JK", "TARA.JK", "MTFN.JK", "POLA.JK", "BIPI.JK", "TOBA.JK",
    "SMBR.JK", "INPC.JK", "BEKS.JK", "AGRO.JK", "PNBN.JK", "APIC.JK",
    "MPPA.JK", "NASA.JK", "COAL.JK", "PTRO.JK", "RUIS.JK", "ZINC.JK",
]

HARGA_MAKS_MURAH = 300  # ambang batas harga saham "murah" (Rupiah)

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


def hitung_level_trading(harga, tp_persen, sl_persen):
    """Hitung entry, take profit, dan stop loss berdasarkan harga saat ini + persentase target."""
    return {
        "entry": harga,
        "tp": harga * (1 + tp_persen / 100),
        "sl": harga * (1 - sl_persen / 100),
    }


def cocok_kriteria_scalping(d):
    """Kriteria kasar buat kandidat scalping blue-chip: momentum + volume + belum overbought parah."""
    if not d or d["rsi"] is None or d["vol_avg20"] is None or d["ma20"] is None:
        return False
    volume_naik = d["volume"] > d["vol_avg20"] * 1.5
    momentum_ok = 45 <= d["rsi"] <= 70
    di_atas_ma20 = d["harga"] > d["ma20"]
    gerak_hari_ini = abs(d["perubahan_persen"]) >= 1.5
    return volume_naik and momentum_ok and di_atas_ma20 and gerak_hari_ini


def cocok_kriteria_murah(d):
    """Kriteria buat saham harga rendah: harga di bawah ambang + ada tanda-tanda volume/gerakan aktif.
    Kriteria momentum dilonggarkan karena saham murah biasanya lebih liar geraknya."""
    if not d or d["vol_avg20"] is None:
        return False
    if d["harga"] > HARGA_MAKS_MURAH:
        return False
    volume_naik = d["volume"] > d["vol_avg20"] * 1.3  # sedikit lebih longgar dari kriteria blue-chip
    gerak_hari_ini = abs(d["perubahan_persen"]) >= 2.0  # saham murah butuh gerakan % lebih besar biar berarti
    return volume_naik and gerak_hari_ini


def main():
    kandidat = []
    for ticker in UNIVERSE:
        d = ringkas_data(ticker)
        if cocok_kriteria_scalping(d):
            kandidat.append(d)

    # Coba ambil daftar saham murah yang SEDANG RAMAI langsung dari IDX (dinamis)
    universe_murah = ambil_top_saham_murah(harga_maks=HARGA_MAKS_MURAH, jumlah=15)
    if universe_murah:
        print(f"Pakai {len(universe_murah)} kandidat saham murah dari IDX (real-time).")
    else:
        print("IDX gagal diakses, pakai daftar cadangan (fallback) untuk saham murah.")
        universe_murah = UNIVERSE_SAHAM_MURAH_CADANGAN

    kandidat_murah = []
    for ticker in universe_murah:
        d = ringkas_data(ticker)
        if cocok_kriteria_murah(d):
            kandidat_murah.append(d)

    if not kandidat and not kandidat_murah:
        kirim_telegram("🔍 *Scan Scalping*\n\nTidak ada saham yang memenuhi kriteria momentum saat ini.")
        return

    berita = ambil_berita(jumlah=4)
    berita_teks = "\n".join(f"- {b}" for b in berita) if berita else "Tidak ada berita relevan."

    # --- Kirim hasil blue-chip (kalau ada) ---
    if kandidat:
        TP_PERSEN_BLUECHIP = 2.0   # target profit scalping blue-chip
        SL_PERSEN_BLUECHIP = 1.5   # batas rugi

        baris = []
        for d in kandidat:
            level = hitung_level_trading(d["harga"], TP_PERSEN_BLUECHIP, SL_PERSEN_BLUECHIP)
            d["level"] = level  # simpan buat dipakai lagi nanti (riwayat, dll)
            baris.append(
                f"- {d['ticker']}: harga {d['harga']:.0f}, perubahan {d['perubahan_persen']:.2f}%, "
                f"RSI {d['rsi']:.1f}, volume {d['volume']:.0f} (avg20: {d['vol_avg20']:.0f}) | "
                f"Entry: {level['entry']:.0f} | Take Profit (+{TP_PERSEN_BLUECHIP}%): {level['tp']:.0f} | "
                f"Stop Loss (-{SL_PERSEN_BLUECHIP}%): {level['sl']:.0f}"
            )
        data_teks = "\n".join(baris)

        prompt = f"""Kamu asisten scalping saham untuk trader retail Indonesia (gaya cepat: beli-jual dalam hitungan jam/hari).

Kandidat saham dengan momentum & volume tinggi hari ini (Entry/Take Profit/Stop Loss SUDAH DIHITUNG,
jangan diubah, tinggal jelaskan alasannya):
{data_teks}

Berita pasar terbaru:
{berita_teks}

Tugas kamu:
1. Ranking kandidat dari yang paling menarik untuk scalping, beri alasan singkat (momentum, volume, risiko).
2. WAJIB cantumkan angka Entry, Take Profit, dan Stop Loss PERSIS seperti yang sudah dihitung di atas untuk
   tiap saham - jangan menghitung ulang atau mengubah angkanya.
3. Ingatkan singkat bahwa scalping berisiko tinggi, bukan saran resmi, dan angka TP/SL adalah target
   kasar berbasis persentase, bukan jaminan harga akan sampai ke sana.
4. Bahasa Indonesia santai, ringkas, bullet point.

ATURAN PENTING: Bahas HANYA saham yang tercantum di "Kandidat saham" di atas. Jangan pernah
mengganti atau menambahkan saham lain (termasuk saham luar negeri) meskipun disebut di berita.
"""
        hasil = panggil_gemini(prompt)
        kirim_telegram(f"🔥 *Kandidat Scalping Hari Ini*\n\n{hasil}")

        for d in kandidat:
            tambah_sinyal(d["ticker"], "SCALPING_BUY", d["harga"], tipe="scalping")

    # --- Kirim hasil saham murah (kalau ada), dengan peringatan ekstra ---
    if kandidat_murah:
        TP_PERSEN_MURAH = 4.0   # target lebih lebar karena saham murah lebih volatil
        SL_PERSEN_MURAH = 2.5

        baris_murah = []
        for d in kandidat_murah:
            level = hitung_level_trading(d["harga"], TP_PERSEN_MURAH, SL_PERSEN_MURAH)
            d["level"] = level
            baris_murah.append(
                f"- {d['ticker']}: harga {d['harga']:.0f}, perubahan {d['perubahan_persen']:.2f}%, "
                f"volume {d['volume']:.0f} (avg20: {d['vol_avg20']:.0f}) | "
                f"Entry: {level['entry']:.0f} | Take Profit (+{TP_PERSEN_MURAH}%): {level['tp']:.0f} | "
                f"Stop Loss (-{SL_PERSEN_MURAH}%): {level['sl']:.0f}"
            )
        data_teks_murah = "\n".join(baris_murah)

        prompt_murah = f"""Kamu asisten trading saham harga rendah (di bawah Rp{HARGA_MAKS_MURAH}) untuk trader retail
Indonesia yang mau scalping cepat. Saham jenis ini ("gorengan") sangat volatil dan rawan dipermainkan bandar.

Kandidat saham murah dengan lonjakan volume/gerakan hari ini (Entry/Take Profit/Stop Loss SUDAH DIHITUNG,
jangan diubah):
{data_teks_murah}

Berita pasar terbaru:
{berita_teks}

Tugas kamu:
1. Untuk tiap saham, jelaskan singkat apa yang sedang terjadi (lonjakan volume/harga) dan risikonya.
2. Cantumkan angka Entry, Take Profit, dan Stop Loss PERSIS seperti yang sudah dihitung di atas -
   sebagai INFORMASI, bukan ajakan. Jangan menghitung ulang atau mengubah angkanya.
3. JANGAN merekomendasikan BELI secara eksplisit - cukup sajikan fakta datanya dan risikonya, karena saham
   jenis ini sangat spekulatif dan berisiko tinggi kena "jebakan".
4. Ingatkan dengan tegas bahwa saham harga rendah rawan manipulasi, likuiditas rendah, dan bisa ARB/ARA
   mendadak - risiko kehilangan modal besar sangat nyata, dan stop loss mungkin tidak selalu bisa
   dieksekusi tepat waktu di saham likuiditas rendah.
5. Bahasa Indonesia santai, ringkas, bullet point.

ATURAN PENTING: Bahas HANYA saham yang tercantum di atas. Jangan mengarang atau menambah saham lain.
"""
        hasil_murah = panggil_gemini(prompt_murah)
        kirim_telegram(
            f"⚠️ *Saham Murah (<Rp{HARGA_MAKS_MURAH}) - Volume/Gerakan Aktif*\n\n"
            f"{hasil_murah}\n\n"
            f"‼️ *Peringatan:* saham harga rendah sangat rawan manipulasi/likuiditas tipis. "
            f"Ini info data, BUKAN ajakan beli. Riset sendiri & siapkan batas rugi ketat."
        )

        for d in kandidat_murah:
            tambah_sinyal(d["ticker"], "SCALPING_MURAH_WATCH", d["harga"], tipe="scalping-murah")


if __name__ == "__main__":
    main()
