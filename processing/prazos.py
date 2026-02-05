from datetime import datetime

def dias_para_encerrar(data_fim):
    if not data_fim:
        return None
    fim = datetime.fromisoformat(data_fim)
    return (fim - datetime.now()).days
