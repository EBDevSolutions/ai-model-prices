# AI Model Prices Dashboard

Statyczny dashboard cen tokenów API modeli OpenAI, Anthropic, Google Gemini, xAI, DeepSeek i Alibaba/Qwen. Publikacja działa przez GitHub Pages, a GitHub Actions sprawdza oficjalne źródła co 30 minut. Nie potrzebujesz backendu, VPS-a, Dockera ani usługi działającej na własnym komputerze.

> **Ważne — pierwsza weryfikacja:** `data/prices.json` zawiera snapshot startowy z 9 sierpnia 2026. Po utworzeniu repozytorium uruchom ręcznie workflow **Update AI prices** i porównaj wynik z oficjalnymi cennikami. Strony producentów zmieniają strukturę bez uprzedzenia, a część cen ma progi kontekstu, regiony, tryby lub promocje, których pojedyncza liczba nie oddaje w pełni.

## Co znajduje się w repozytorium

```text
.
├── index.html
├── data/
│   ├── prices.json
│   └── history.json
├── scripts/
│   └── update_prices.py
├── requirements.txt
└── .github/workflows/
    ├── update-prices.yml
    └── pages.yml
```

Updater izoluje błędy dostawców. Jeśli pobranie albo parser jednego źródła zawiedzie, jego dotychczasowe ceny pozostają bez zmian, a pozostali dostawcy nadal są sprawdzani. Historia dostaje wpis wyłącznie wtedy, gdy zmieni się `input`, `cached_input` lub `output` konkretnego modelu.

## Uruchomienie krok po kroku

### 1. Utwórz repozytorium

1. Zaloguj się na GitHub.
2. Kliknij **New repository**.
3. Nadaj nazwę, np. `ai-model-prices`.
4. Najprościej wybierz repozytorium **Public**.
5. Nie dodawaj automatycznie README, `.gitignore` ani licencji.
6. Kliknij **Create repository**.

### 2. Wgraj pliki

Najprostsza metoda bez terminala:

1. Rozpakuj dostarczony ZIP.
2. W pustym repozytorium kliknij **uploading an existing file**.
3. Przeciągnij całą zawartość folderu, łącznie z ukrytym folderem `.github`.
4. Upewnij się, że `index.html` jest w katalogu głównym repozytorium.
5. Zatwierdź pliki do gałęzi `main`.

Jeśli interfejs przeglądarkowy pominie `.github`, wgraj jego pliki osobno przez **Add file → Create new file**, wpisując pełne ścieżki:

- `.github/workflows/update-prices.yml`
- `.github/workflows/pages.yml`

### 3. Włącz GitHub Pages

1. Wejdź w **Settings → Pages**.
2. W sekcji **Build and deployment** wybierz **Source: GitHub Actions**.
3. Przejdź do zakładki **Actions** i poczekaj na zakończenie workflow **Deploy GitHub Pages**.
4. Adres strony pojawi się w wyniku wdrożenia i w **Settings → Pages**. Zwykle ma postać `https://NAZWA-UZYTKOWNIKA.github.io/NAZWA-REPO/`.

### 4. Włącz i sprawdź Actions

1. Wejdź w zakładkę **Actions**.
2. Jeśli GitHub pokaże przycisk zezwolenia na workflow, kliknij **I understand my workflows, go ahead and enable them**.
3. Otwórz **Update AI prices**.
4. Kliknij **Run workflow → Run workflow**.
5. Po zakończeniu otwórz log kroku **Update official prices**. Status każdego dostawcy zobaczysz również na dashboardzie.
6. Sprawdź, czy commit bota zmienił `data/prices.json` i ewentualnie `data/history.json`.

Workflow używa uprawnienia `contents: write`, aby zapisać odświeżone JSON-y. Jeżeli organizacja blokuje zapis przez Actions, wejdź w **Settings → Actions → General → Workflow permissions** i wybierz **Read and write permissions**.

### 5. Pierwsza kontrola danych

Otwórz link **Źródło** przy każdym modelu i sprawdź co najmniej po jednym modelu każdego dostawcy. Zwróć szczególną uwagę na:

- progi długości kontekstu;
- region Alibaba Model Studio;
- ceny promocyjne i pory szczytu DeepSeek;
- standard, batch, flex i priority;
- różnicę między cache read a cache write.

Dashboard pokazuje podstawową cenę standardową w USD za 1 mln tokenów. Uwagi o wybranym progu lub regionie znajdują się w kolumnie modelu.

## Harmonogram

Plik `.github/workflows/update-prices.yml` używa:

```yaml
schedule:
  - cron: "7,37 * * * *"
```

To dwa uruchomienia na godzinę, o minutach `07` i `37` czasu UTC. Przesunięcie od pełnej godziny zmniejsza ryzyko opóźnienia przy dużym obciążeniu GitHub Actions. Harmonogram nie jest gwarancją wykonania dokładnie co do minuty. W publicznych repozytoriach GitHub może wyłączyć zaplanowane workflow po długiej nieaktywności; wtedy uruchom je ręcznie lub zrób commit.

## Jak działa odporność na błędy

- każdy dostawca jest pobierany i parsowany niezależnie;
- błąd HTTP, timeout albo brak oczekiwanego wzorca nie zeruje cen;
- nieznane i podejrzanie duże skoki są odrzucane;
- zapis jest atomowy, więc przerwany proces nie zostawia połowy JSON-a;
- `last_checked_at` zapisuje czas próby, a `last_success_at` czas udanego parsera;
- `history.json` zmienia się tylko przy rzeczywistej zmianie ceny;
- workflow commitujący sprawdza różnicę plików przed commitem.

Parser HTML zawsze może wymagać korekty po zmianie strony producenta. Błąd jest widoczny w polu `providers[].error` i na dashboardzie.

## Test lokalny (opcjonalny)

Do zwykłego korzystania wystarczy GitHub Pages. Jeśli chcesz przetestować repo przed publikacją:

```bash
python -m pip install -r requirements.txt
python scripts/update_prices.py --dry-run --verbose
python -m http.server 8000
```

Następnie otwórz `http://localhost:8000`. Nie otwieraj `index.html` przez `file://`, ponieważ przeglądarki zwykle blokują pobieranie lokalnego JSON-a. Lokalny serwer jest wyłącznie opcjonalnym narzędziem testowym, nie elementem rozwiązania produkcyjnego.

## Oficjalne źródła

- [OpenAI API models/pricing](https://developers.openai.com/api/docs/models/compare)
- [Anthropic Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [xAI pricing](https://docs.x.ai/developers/pricing)
- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [Alibaba Cloud Model Studio pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing)

## Utrzymanie

Gdy dostawca zmieni układ strony, popraw odpowiednią funkcję `parse_*` w `scripts/update_prices.py`, uruchom ją z `--provider NAZWA --dry-run --verbose`, a dopiero potem zatwierdź zmianę. Dostępne nazwy: `openai`, `anthropic`, `google`, `xai`, `deepseek`, `alibaba`.

Nie są wymagane żadne klucze API ani sekrety. Updater czyta wyłącznie publiczne strony cenników.
