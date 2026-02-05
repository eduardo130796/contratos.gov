import os

def garantir_pastas():
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/contratos", exist_ok=True)
    os.makedirs("data/links", exist_ok=True)
    os.makedirs("data/meta", exist_ok=True)
