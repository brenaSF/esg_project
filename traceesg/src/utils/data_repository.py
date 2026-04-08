import json
import pandas as pd
from datetime import datetime

class DataRepository:
    """Responsável por persistir os dados em JSON e CSV/Excel."""
    
    @staticmethod
    def save_raw_extraction(data, filename=None):
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"raw_extraction_{timestamp}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"💾 JSON de extração salvo em: {filename}")

    @staticmethod
    def save_final_csv(registro, filename="base_power_bi.csv"):
        df = pd.DataFrame([registro])
        df.to_csv(filename, index=False, sep=";", encoding="utf-8-sig")
        print(f"📊 CSV para Power BI salvo em: {filename}")