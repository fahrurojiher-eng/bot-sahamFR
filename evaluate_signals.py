import os
import requests
from datetime import datetime

from analyzer import ringkas_data
from history import load_history, save_history

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# minimal berapa jam sejak sinyal sebelum dievaluasi (biar ada waktu gerak harganya)
MIN_JAM_SEBELUM_EVALUASI = 3


BATAS_PANJANG_TELEGRAM = 4000  # sedikit di bawah limit asli (4096) buat jaga-jaga


def pecah_teks(teks, batas=BATAS_PANJANG_TELEGRAM):
    """Pecah teks panjang jadi beberapa bagian, coba potong di baris kosong biar rapi."""
    if len(teks) <= batas:
        return [teks]

    bagian = []
    sisa = teks
    while len(sisa) > batas:
        potong_di = sisa.rfind("\n\n", 0, batas)
        if potong_di == -1:
            potong_di = sisa.rfind("\n", 0, batas)
        if potong_di == -1:
            potong_di = batas
        bagian.append(sisa[:potong_di])
        sisa = sisa[potong_di:].lstrip("\n")
    bagian.append(sisa)
    return bagian


def _kirim_satu_pesan(teks):
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

    resp2 = requests.post(url, data={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": teks,
    })

    if not resp2.ok:
        print(f"GAGAL KIRIM TELEGRAM (plain text juga gagal): {resp2.status_code} - {resp2.text}")
        raise RuntimeError(f"Telegram sendMessage gagal total: {resp2.text}")
    else:
        print("Pesan Telegram berhasil terkirim (plain text, fallback).")


def kirim_telegram(teks):
    bagian_bagian = pecah_teks(teks)
    total = len(bagian_bagian)
    for i, bagian in enumerate(bagian_bagian, start=1):
        label_bagian = f" ({i}/{total})" if total > 1 else ""
        _kirim_satu_pesan(bagian + (f"\n\n_lanjut...{label_bagian}_" if i < total else ""))


def sudah_waktunya(entry):
    waktu_sinyal = datetime.fromisoformat(entry["id"].split("-", 1)[1])
    selisih_jam = (datetime.now() - waktu_sinyal).total_seconds() / 3600
    return selisih_jam >= MIN_JAM_SEBELUM_EVALUASI


def evaluasi_benar(sinyal, perubahan_persen):
    if sinyal in ("BELI", "SCALPING_BUY"):
        return perubahan_persen > 0
    elif sinyal == "JUAL":
        return perubahan_persen < 0
    return None  # TAHAN tidak dievaluasi benar/salah


def main():
    history = load_history()
    if not history:
        kirim_telegram("📋 *Evaluasi Sinyal*\n\nBelum ada riwayat sinyal untuk dievaluasi.")
        return

    hasil_baris = []
    cache_harga = {}

    for entry in history:
        if entry["sudah_dievaluasi"]:
            continue
        if entry["sinyal"] == "TAHAN":
            entry["sudah_dievaluasi"] = True
            continue
        if not sudah_waktunya(entry):
            continue

        ticker = entry["ticker"]
        if ticker not in cache_harga:
            d = ringkas_data(ticker)
            cache_harga[ticker] = d["harga"] if d else None

        harga_sekarang = cache_harga[ticker]
        if harga_sekarang is None:
            continue

        perubahan = (harga_sekarang - entry["harga_saat_sinyal"]) / entry["harga_saat_sinyal"] * 100
        benar = evaluasi_benar(entry["sinyal"], perubahan)

        entry["sudah_dievaluasi"] = True
        entry["harga_evaluasi"] = harga_sekarang
        entry["perubahan_persen"] = round(perubahan, 2)
        entry["benar"] = benar

        status = "✅ BENAR" if benar else "❌ MELESET"
        hasil_baris.append(
            f"{status} — {ticker} ({entry['sinyal']}, {entry['tanggal']} {entry['jam']}): "
            f"{entry['harga_saat_sinyal']:.0f} → {harga_sekarang:.0f} ({perubahan:+.2f}%)"
        )

    save_history(history)

    if not hasil_baris:
        kirim_telegram("📋 *Evaluasi Sinyal*\n\nBelum ada sinyal yang siap dievaluasi saat ini.")
        return

    total = len(hasil_baris)
    benar_count = sum(1 for h in hasil_baris if "BENAR" in h)
    akurasi = benar_count / total * 100

    teks = (
        f"📋 *Evaluasi Sinyal* (akurasi {akurasi:.0f}% dari {total} sinyal)\n\n"
        + "\n".join(hasil_baris)
    )
    kirim_telegram(teks)


if __name__ == "__main__":
    main()
