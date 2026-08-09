# AI Model Prices Dashboard

Statyczny dashboard cen tokenów API modeli OpenAI, Anthropic, Google Gemini, xAI, DeepSeek, Alibaba/Qwen i Moonshot/Kimi. Publikacja działa przez GitHub Pages, a GitHub Actions co 30 minut sprawdza oficjalne źródła, aktualizuje ceny i automatycznie dodaje nowo wykryte modele. Nie potrzebujesz backendu, VPS-a, Dockera ani usługi działającej na własnym komputerze.

> **Ważne — pierwsza weryfikacja:** `data/prices.json` zawiera snapshot startowy z 9 sierpnia 2026. Po utworzeniu repozytorium uruchom ręcznie workflow **Update AI prices** i porównaj wynik z oficjalnymi cennikami. Strony producentów zmieniają strukturę bez uprzedzenia, a część cen ma progi kontekstu, regiony, tryby lub promocje, których pojedyncza liczba nie oddaje w pełni.

## Co znajduje się w repozytorium

```text
.
├── index.html
├── data/
│   ├── prices.json
│   ├── history.json
│   └── benchmarks.json
├── scripts/
│   ├── update_prices.py
│   └── update_benchmarks.py
├── requirements.txt
└── .github/workflows/
    ├── update-prices.yml
    └── pages.yml
```

Updater izoluje błędy dostawców. Jeśli pobranie albo parser jednego źródła zawiedzie, jego dotychczasowy katalog pozostaje bez zmian, a pozostali dostawcy nadal są sprawdzani. Nowe wiersze oficjalnych tabel są automatycznie dopisywane do `data/prices.json`. Historia rejestruje dodanie modelu, zmianę ceny, ponowne pojawienie się i zniknięcie z aktualnego cennika.

Ten sam workflow uzupełnia benchmarki z publicznego zbioru [BenchLM](https://benchlm.ai/data), udostępnionego na licencji MIT. Import obejmuje wyłącznie dokładnie dopasowane modele ze statusem `supported`, bez wygenerowanych rekordów, i tylko surowe wyniki identycznie nazwanych testów. Wyniki oraz estymacje kompozytowe BenchAlign nie są przepisywane jako rezultaty badań. Dane z oficjalnej karty producenta mają zawsze pierwszeństwo przed agregatorem.

## Zakres automatycznego katalogu

- **OpenAI:** modele tekstowe z aktualnych tabel Standard oraz tabel kategorii w oficjalnym cenniku;
- **Anthropic:** wszystkie wiersze głównej tabeli Claude API, włącznie z oznaczeniami limited i retired;
- **Google Gemini:** modele z płatną ceną input i output w pierwszej tabeli Standard każdej sekcji modelu;
- **xAI:** wszystkie modele z tabeli Text API, według ceny short context;
- **DeepSeek:** wszystkie kolumny modeli z oficjalnej macierzy Models & Pricing;
- **Alibaba/Qwen:** celowo mały katalog: bieżąca generacja `qwen3.8-max` i poprzednia `qwen3.7-max`. Snapshoty, preview i wyspecjalizowane warianty nie są osobnymi pozycjami. `qwen3.8-max` jest dostępny w Qwen Cloud/Model Studio, ale dopóki nie ma publicznej stawki USD za token, jest oznaczony jako nieporównywalny cenowo i nie wchodzi do rankingu.
- **Moonshot/Kimi:** aktualne K3 oraz bezpośrednio poprzednie K2.7 Code i K2.6, odczytywane z oficjalnych tabel Moonshot API.

Modele multimodalne z wieloma osobnymi stawkami audio/obrazu nie są mieszane z jedną stawką tekstową, jeżeli oficjalna tabela nie daje jednoznacznej pary input/output. Dzięki temu ranking nie porównuje różnych jednostek jakby były tym samym kosztem.

## Benchmarki i opłacalność badawcza

`data/benchmarks.json` zawiera wyłącznie wyniki podane w cytowanych źródłach: MMLU-Pro, GPQA Diamond, Humanity's Last Exam bez narzędzi, LiveCodeBench, SWE-Bench Pro, Terminal-Bench i FrontierSWE. Każda komórka z wynikiem prowadzi do źródła właściwego dla tej konkretnej liczby oraz ma podpowiedź z warunkami uruchomienia. Identyfikatory cen są łączone z wynikami przez dokładny klucz lub jawny alias — podobna nazwa nie wystarcza.

Przykład kontroli mapowania: oficjalna karta Gemini 2.0 Flash-Lite podaje dla wariantu Public Preview `71,6% MMLU-Pro`, `51,5% GPQA Diamond` i `28,9% LiveCodeBench v5`. Dashboard przypisuje te wyniki wyłącznie do `google:gemini-2.0-flash-lite`. `MMLU-Pro` i `MMMU-Pro` są różnymi benchmarkami i nie trafiają do tej samej kolumny.

Wskaźnik **Wartość badawcza** nie używa nazw modeli ani szacunków. Dla modelu z pełnymi danymi oblicza średnią `GPQA Diamond` i `HLE bez narzędzi`, dzieli ją przez koszt workloadu z kalkulatora, a następnie skaluje wynik 0–100 wyłącznie w grupie modeli mających oba wyniki. Brak wyniku jest pokazywany jako `—` i wyłącza model z rankingu wartości. Testy codingowe pozostają osobnymi kolumnami, ponieważ różne zestawy/harnessy nie są rzetelnie wymienne.

Panel **Najlepsze do programowania** pozwala wybrać osobno Terminal-Bench, LiveCodeBench, SWE-Bench Pro albo FrontierSWE. Ranking zawsze używa jednego testu naraz; wyniki nie są łączone w sztuczną średnią.

Benchmarki nie są automatycznie zgadywane na podstawie wyników wyszukiwarki. Dodanie nowego modelu do cennika nie oznacza automatycznie dostępnego i porównywalnego wyniku badania: najpierw musi istnieć źródło pierwotne, dokładna wersja modelu i opis trybu testu. Brak wyniku pozostaje oznaczony jako `—`.

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
- nowe identyfikatory modeli są automatycznie dodawane;
- podejrzanie duże skoki cen są odrzucane;
- model znika z aktywnego katalogu dopiero po trzech kolejnych pełnych skanach bez jego obecności; jego ostatnia cena pozostaje w danych;
- zapis jest atomowy, więc przerwany proces nie zostawia połowy JSON-a;
- `last_checked_at` zapisuje czas próby, a `last_success_at` czas udanego parsera;
- `history.json` rejestruje dodania modeli, zmiany cen oraz zmiany dostępności;
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

- [OpenAI API pricing](https://developers.openai.com/api/docs/pricing)
- [Anthropic Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [xAI pricing](https://docs.x.ai/developers/pricing)
- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [Alibaba Cloud Model Studio pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing)
- [Qwen3.8-Max availability](https://help.aliyun.com/en/model-studio/web-search)
- [Moonshot / Kimi pricing](https://platform.kimi.ai/docs/pricing/chat-k3)
- [OpenAI GPT-5.4 evaluation report](https://openai.com/index/introducing-gpt-5-4-mini-and-nano/)
- [Kimi K3 technical report](https://arxiv.org/abs/2607.24653)

## Utrzymanie

Gdy dostawca zmieni układ strony, popraw odpowiednią funkcję `parse_*` w `scripts/update_prices.py`, uruchom ją z `--provider NAZWA --dry-run --verbose`, a dopiero potem zatwierdź zmianę. Dostępne nazwy: `openai`, `anthropic`, `google`, `xai`, `deepseek`, `alibaba`, `moonshot`. Każdy parser ma minimalny oczekiwany rozmiar katalogu, więc przypadkowe pobranie niepełnej strony nie oznaczy masowo modeli jako brakujące.

Nie są wymagane żadne klucze API ani sekrety. Updater czyta wyłącznie publiczne strony cenników.
