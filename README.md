# Táborová Hra - Území

Webová aplikace pro táborovou hru o zabírání území s GPS ověřením a úkoly.

## Jak spustit lokálně
1. Ujistěte se, že máte nainstalovaný Python 3.
2. Nainstalujte potřebné knihovny:
   ```bash
   pip install -r requirements.txt
   ```
3. Spusťte hru dvojklikem na `run_game.bat` nebo příkazem:
   ```bash
   python app.py
   ```
4. Otevřete prohlížeč na `http://localhost:5000`.
   - Pro přístup z mobilů musí být počítač i mobily na stejné Wi-Fi.
   - Použijte IP adresu počítače (zobrazí se v konzoli po spuštění, např. `http://192.168.1.X:5000`).

## Nasazení na Railway (nebo jiný cloud)
Tento projekt je připraven pro nasazení na [Railway.app](https://railway.app).

### Postup:
1. Nahrajte tento projekt na **GitHub**.
2. Vytvořte nový projekt na Railway a vyberte "Deploy from GitHub repo".
3. Railway automaticky detekuje `requirements.txt` a `Procfile`.
4. Po nasazení získáte veřejnou URL adresu (např. `https://taborova-hra.up.railway.app`).
   - **Pozor:** Na veřejné URL bude fungovat GPS geolokace na mobilech bez problémů (díky HTTPS).

### Soubory pro nasazení:
- `Procfile`: Říká cloudu, jak aplikaci spustit (pomocí Gunicorn).
- `requirements.txt`: Seznam závislostí.
- `runtime.txt`: Verze Pythonu.
- `.gitignore`: Ignorované soubory (nebudou na GitHubu).

## Pravidla a Ovládání
1. **Přihlášení:**
   - Heslo pro všechny týmy i admina je `1234`.
   - Vyberte si tým nebo roli "Admin".

2. **Hráč (Tým):**
   - Klikne na území na mapě.
   - Potvrdí zabrání -> odešle se GPS poloha.
   - Čeká na schválení adminem.
   - Po schválení dostane úkol -> Vyplní text nebo nahraje fotku/video.
   - Po schválení úkolu se území přebarví barvou týmu.

3. **Admin:**
   - Vidí panel "Příchozí žádosti".
   - Schvaluje/Zamítá polohu hráčů (vidí jejich GPS souřadnice).
   - Zadává úkoly.
   - Kontroluje odpovědi (čte text, prohlíží fotky).
   - Schvaluje splnění -> území je zabráno.

## Struktura
- `app.py`: Backend server (Python/Flask).
- `index.html`: Hlavní stránka (Frontend).
- `CTH_geo.geojson`: Data o územích.
- `uploads/`: Složka pro nahrané fotky/videa (v cloudu se může mazat po restartu, pokud není použito perzistentní úložiště!).
