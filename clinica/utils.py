import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

def sincronizar_google_sheet(cita):
    """Exporta contexto de la cita; no confirma un movimiento económico."""
   
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
   
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales_google.json', scope)
    client = gspread.authorize(creds)

    
    sheet = client.open("REPORTE GENERAL").worksheet("Datos")

    
    periodo = cita.fecha.strftime("%B %Y").capitalize() 
    
    
    fila_nueva = [
        cita.fecha.day,                 # Columna A: Dia
        periodo,                        # Columna B: Periodo
        str(cita.hora)[:5],             # Columna C: Hora
        str(cita.division),             # Columna D: División
        str(cita.paciente.nombre),      # Columna E: Paciente
        str(cita.paciente.sexo),        # Columna F: Sexo
        str(cita.servicio),             # Columna G: Servicio
        str(cita.terapeuta),            # Columna H: Terapeuta
        str(cita.consultorio),          # Columna I: Consultorio
        float(cita.costo),              # Columna J legacy: importe de cita
        cita.metodo_pago,               # Columna K: método registrado en cita
        "",                             # Columna L: Tarjeta (Vacío por ahora)
        cita.folio_fiscal or "NA",      # Columna M: Folio
        cita.notas or "",               # Columna N: Notas
        str(cita.fecha)                 # Columna O legacy: fecha de cita
    ]

   
    sheet.append_row(fila_nueva)
    print(" Cita sincronizada con Excel")
