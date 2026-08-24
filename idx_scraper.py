"""
Modul untuk ambil data ringkasan perdagangan harian dari IDX (Bursa Efek Indonesia)
secara langsung, supaya bisa cari saham murah yang SEDANG RAMAI hari itu
(bukan daftar tetap/fixed list).

Situs IDX pakai proteksi anti-bot (Cloudflare), jadi kita perlu browser
otomatis (headless) buat "membuka" situsnya dulu sebelum ambil datanya.
Kalau ini gagal (situs berubah / diblokir), fungsi akan return list kosong,
dan kode pemanggilnya harus punya fallback ke daftar cadangan.
"""

import json
from datetime import datetime, timedelta


def ambil_top_saham_murah(harga_maks=300, jumlah=15, min_volume=1_000_000):
    """
    Ambil daftar kode saham (format 'KODE.JK') yang harganya di bawah harga_maks
    dan sedang aktif diperdagangkan (volume tinggi) hari ini, langsung dari IDX.

    Return: list kode saham, misal ['BUMI.JK', 'ENRG.JK', ...]
    Return list kosong kalau gagal ambil data (situs berubah/diblokir/dll).
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"Playwright tidak tersedia: {e}")
        return []

    # Coba beberapa tanggal terakhir (jaga-jaga kalau hari ini libur/weekend)
    for mundur in range(0, 6):
        tanggal = datetime.now() - timedelta(days=mundur)
        tanggal_str = tanggal.strftime("%Y%m%d")
        url = (
            "https://www.idx.co.id/primary/TradingSummary/GetStockSummary"
            f"?length=9999&start=0&date={tanggal_str}"
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    )
                )
                page = context.new_page()

                # Buka homepage dulu biar dapat cookie Cloudflare
                page.goto("https://www.idx.co.id/", timeout=30000)
                page.wait_for_timeout(2000)

                # Baru akses endpoint data-nya
                response = page.goto(url, timeout=30000)
                if response is None or response.status != 200:
                    print(f"[{tanggal_str}] Gagal akses IDX, status: {response.status if response else 'no response'}")
                    browser.close()
                    continue

                body = response.text()
                browser.close()

            data = json.loads(body)
            daftar = data.get("data", [])

            if not daftar:
                print(f"[{tanggal_str}] Data IDX kosong (mungkin bukan hari bursa), coba tanggal sebelumnya...")
                continue

            # Field name di API IDX bisa berbeda-beda, coba beberapa kemungkinan nama
            kandidat = []
            for row in daftar:
                kode = row.get("StockCode") or row.get("Code") or row.get("stock_code")
                harga = row.get("Close") or row.get("close")
                volume = row.get("Volume") or row.get("volume")

                if not kode or harga is None or volume is None:
                    continue
                try:
                    harga = float(harga)
                    volume = float(volume)
                except (ValueError, TypeError):
                    continue

                if 0 < harga <= harga_maks and volume >= min_volume:
                    kandidat.append((kode.strip(), harga, volume))

            if not kandidat:
                print(f"[{tanggal_str}] Tidak ada saham yang cocok kriteria harga<={harga_maks} & volume>={min_volume}.")
                continue

            # Urutkan dari volume paling tinggi (paling ramai) ke rendah
            kandidat.sort(key=lambda x: x[2], reverse=True)
            hasil = [f"{kode}.JK" for kode, harga, vol in kandidat[:jumlah]]
            print(f"[{tanggal_str}] Berhasil dapat {len(hasil)} kandidat saham murah dari IDX: {hasil}")
            return hasil

        except Exception as e:
            print(f"[{tanggal_str}] Error ambil data IDX: {e}")
            continue

    print("Gagal ambil data dari IDX setelah beberapa percobaan tanggal.")
    return []
