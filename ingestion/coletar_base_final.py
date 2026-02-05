import json
import os
import time
from services.api_client import APIClient
from services.contratos import ContratosService

# ================= CONFIGURAÇÕES =================

UG = "290002"
BASE_URL = "https://contratos.comprasnet.gov.br/api"
DELAY = 1.5            # respeita a API
LIMITE_TESTE = 50      # None para produção

# ================= SETUP =================

os.makedirs("data/raw", exist_ok=True)

client = APIClient(BASE_URL)
service = ContratosService(client)

# ================= 1️⃣ CONTRATOS =================

print("📄 Coletando lista de contratos...")

contratos = service.listar_por_ug(UG)

if LIMITE_TESTE:
    contratos = contratos[:LIMITE_TESTE]

with open("data/raw/contratos.json", "w", encoding="utf-8") as f:
    json.dump(contratos, f, ensure_ascii=False, indent=2)

print(f"✔ {len(contratos)} contratos salvos")

# ================= 2️⃣ HISTÓRICO E EMPENHOS =================

historicos = {}
empenhos = {}

for c in contratos:
    cid = str(c["id"])
    print(f"🔄 Contrato {cid}")

    # -------- histórico --------
    url_hist = c.get("links", {}).get("historico")
    if url_hist:
        try:
            historicos[cid] = service.obter_link(url_hist)
            time.sleep(DELAY)
        except Exception as e:
            historicos[cid] = []
            print(f"⚠️ Histórico erro ({cid}): {e}")
    else:
        historicos[cid] = []

    # -------- empenhos --------
    url_emp = c.get("links", {}).get("empenhos")
    if url_emp:
        try:
            empenhos[cid] = service.obter_link(url_emp)
            time.sleep(DELAY)
        except Exception as e:
            empenhos[cid] = []
            print(f"⚠️ Empenhos erro ({cid}): {e}")
    else:
        empenhos[cid] = []

# ================= 3️⃣ SALVAMENTO FINAL =================

with open("data/raw/historicos.json", "w", encoding="utf-8") as f:
    json.dump(historicos, f, ensure_ascii=False, indent=2)

with open("data/raw/empenhos.json", "w", encoding="utf-8") as f:
    json.dump(empenhos, f, ensure_ascii=False, indent=2)

print("✅ Coleta finalizada com sucesso")
