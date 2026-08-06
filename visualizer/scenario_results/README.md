# Maakasutuse stsenaariumide juhtpaneel

See on staatiline eestikeelne veebileht Notebook 10 tulemuste vaatamiseks.
Külastaja saab valida stsenaariumi, vaadata selle 500 m ruutude kaarti ning
võrrelda tulemust teiste stsenaariumidega.

## Andmefaili loomine

Pärast Notebook 10 käivitamist ava projektikaustas terminal ja käivita:

```powershell
.\.venv\Scripts\python.exe visualizer\scenario_results\export_dashboard_data.py
```

See loob faili `data/scenario-results.json`. Käsk kasutab olemasolevaid
`scenario_summary.parquet` ja `scenario_maps/*.gpkg` faile ning ei laadi
andmeid alla ega käivita optimeerimist uuesti.

## Üleslaadimine

Laadi kogu kaust `visualizer/scenario_results` koos alamkaustaga `data` üles
staatiline veebimajutus teenusesse. Säilita kaustastruktuur:

```text
scenario_results/
├── index.html
├── styles.css
├── app.js
└── data/
    └── scenario-results.json
```

Leht ei kasuta välist kaarditausta ega muid veebiteenuseid. Seetõttu jääb kaart
toimima ka siis, kui külastaja ei saa internetist lisafaile laadida.

## Tõlgendamine

Elurikkus ja sekkumise kulu on mudeli indeksid. Need ei ole liikide arvukuse
mõõtmine ega eurodes eelarve. Protsendina näidatud maakasutus- ja märgalanäitajad
kirjeldavad mudeli arvutatud pindala muutust.
