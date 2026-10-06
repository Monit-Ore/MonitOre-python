import csv
import time
from datetime import datetime
import psutil

def capturar_metricas_sistema(capturas_sistema="metricas_sistema.csv"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    
    cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disco = psutil.disk_usage('/')  

    with open(capturas_sistema, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", 
            "cpu_percent", 
            "ram_total_gb", 
            "ram_usada_gb", 
            "ram_percent", 
            "disco_total_gb", 
            "disco_usado_gb", 
            "disco_percent"
        ])
        writer.writerow([
            timestamp,
            cpu_percent,
            round(ram.total / (1024**3), 2),
            round(ram.used / (1024**3), 2),
            ram.percent,
            round(disco.total / (1024**3), 2),
            round(disco.used / (1024**3), 2),
            disco.percent
        ])
    print(f"Métricas do sistema salvas em: {capturas_sistema}")

def capturar_processos_ativos(capturas_sistema="processos_ativos.csv"):
  
    for proc in psutil.process_iter(['cpu_percent']):
        pass
    
    time.sleep(0.5)  

    processos = []
    campos = ['pid', 'name', 'cpu_percent', 'memory_percent', 'status']

    for proc in psutil.process_iter(campos):
        try:
            info = proc.info
            processos.append({
                "pid": info['pid'],
                "nome": info['name'],
                "cpu_percent": info['cpu_percent'] or 0.0,
                "ram_percent": round(info['memory_percent'] or 0.0, 2),
                "status": info['status']
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    
    processos.sort(key=lambda p: p["cpu_percent"], reverse=True)

    with open(capturas_sistema, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["pid", "nome", "cpu_percent", "ram_percent", "status"])
        writer.writeheader()
        writer.writerows(processos)

    print(f"Processos ativos salvos em: {capturas_sistema}")

if __name__ == "__main__":
    capturar_metricas_sistema()
    capturar_processos_ativos()