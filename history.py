import json
import os
from datetime import datetime

FILE_HISTORY = "signals_history.json"


def load_history():
    if not os.path.exists(FILE_HISTORY):
        return []
    with open(FILE_HISTORY, "r") as f:
        return json.load(f)


def save_history(data):
    with open(FILE_HISTORY, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def tambah_sinyal(ticker, sinyal, harga, tipe="reguler"):
    """tipe: 'reguler' (pagi/sore) atau 'scalping'"""
    history = load_history()
    history.append({
        "id": f"{ticker}-{datetime.now().isoformat()}",
        "ticker": ticker,
        "tanggal": datetime.now().strftime("%Y-%m-%d"),
        "jam": datetime.now().strftime("%H:%M"),
        "tipe": tipe,
        "sinyal": sinyal,          # BELI / JUAL / TAHAN / SCALPING_BUY
        "harga_saat_sinyal": harga,
        "sudah_dievaluasi": False,
        "harga_evaluasi": None,
        "perubahan_persen": None,
        "benar": None,
    })
    save_history(history)
