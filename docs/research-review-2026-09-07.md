# AI Model Prices: programowanie i agenci

Stan badania: 7 września 2026. Audyt bazuje na commicie `f5912c2` oraz publicznych źródłach pobranych tego dnia. To audyt danych, obliczenia scenariuszowe i projekt badania. Nie uruchamialiśmy płatnych testów modeli; wyniki zadań i opóźnienia nie są własnymi pomiarami.

## Wniosek produktowy

Projekt powinien pomagać wybrać model do konkretnej pracy: najpierw wymagania i dostęp, następnie skuteczność na zadaniach użytkownika, dopiero potem całkowity koszt. Cena miliona tokenów jest użytecznym składnikiem, ale sama nie mierzy opłacalności. Aktualny katalog i historie cen warto zachować; uniwersalny wynik 0–100 należy zastąpić jawnym porównaniem kosztu i jakości.

W tej zmianie rozdzielono kategorie Coding i Agentic. Zestawienia BenchLM pozostają poglądowe: wspólna skala nie oznacza jednakowych testów. Etykieta Pareto wskazuje tylko brak innego wybranego modelu, który kosztuje nie więcej i ma wynik nie niższy, z co najmniej jedną ścisłą poprawą. Nie dowodzi statystycznej przewagi ani jakości na prywatnym repozytorium.

## Ustalenia i poprawki

| Priorytet | Dowód w wersji bazowej | Skutek | Zmiana |
|---|---|---|---|
| P0 | Anthropic: ostatni sukces 1 IX, parser wymagał `Base Input Tokens`, źródło podaje `Base input tokens` | Nowe modele i ceny nie były aktualizowane | Dopasowanie nagłówków bez rozróżniania wielkości liter; test prawdziwej tabeli |
| P0 | DeepSeek: ostatni sukces 5 IX; tabela ma wiersze PEAK/OFF-PEAK i rowspan | Brak aktualizacji; wybór pierwszej stawki zaniżałby koszt w szczycie | Kanoniczny URL ze slashem; odczyt ostatnich kolumn, jawne stawki PEAK |
| P0 | `qualityForValue` wybierał kompozyt albo średnią GPQA/HLE zależnie od modelu | Porównywanie różnych definicji jakości w jednym rankingu | Jedna wybrana kategoria, brak wyniku pozostaje brakiem |
| P1 | Cena + jakość + efektywność, następnie arbitralny mnożnik pewności | Koszt uwzględniany dwa razy; pozorna precyzja | Usunięte wagi, mnożnik, pierwiastek i skala 0–100; koszt, wynik i ograniczenia osobno |
| P1 | GPT-5.4: `verifiedDisplayScore=62`, ale `scoreInterval90=68.16–73.76` opisuje `displayScore=70.96` | Przedział nie dotyczył prezentowanej liczby, również w kategoriach | Oryginalny przedział zachowany pod właściwą nazwą; nie jest pokazywany przy innej metryce |
| P1 | Liczba zweryfikowanych rekordów całego modelu uznawana za weryfikację każdej komórki | Zawyżona pewność źródeł surowych wyników | Oznaczenie `verification_scope=model_only`, brak grupy kontrolowanego porównania |
| P1 | Nieobecne lub wycofane dane agregatora pozostawały w JSON | Wynik mógł pozostać po utracie podstawy źródłowej | Po poprawnym imporcie usuwane są wyłącznie stare komórki agregatora; źródła producentów pozostają |
| P1 | Parser Gemini brał również output modeli TTS | Tokeny audio mogły udawać koszt tekstu | Rodziny audio/live/transcribe/streaming wyłączone z kalkulatora tekstowego |
| P1 | Ranking dopuszczał stare ceny, ograniczony dostęp i zerowy workload | Niepraktyczne rekomendacje i dzielenie przez sztuczne epsilon | Aktywna pozycja, poprawny skan dostawcy, cena z ostatnich 48 h, dodatni koszt; estimated domyślnie wyłączone |

Źródła cen: [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/), [Google](https://ai.google.dev/gemini-api/docs/pricing). Definicje i pola agregatora: [BenchLM dataset](https://benchlm.ai/data), [models.json](https://benchlm.ai/data/models.json). Weryfikacja komórek nadal wymaga dotarcia do pierwotnego raportu; nie deklarujemy, że cały historyczny katalog badań został ponownie potwierdzony.

## Porównanie kosztów

Poniższe kwoty oblicza `scripts/research_snapshot.py`. Pełne stawki, daty odczytu i źródła zapisano w [research-snapshot-2026-09-07.json](research-snapshot-2026-09-07.json).

Profile są założeniami sumarycznego wolumenu wielu zapytań, a nie obietnicą zużycia jednego zadania:

- **Patch:** 100 tys. tokenów input bez cache i 20 tys. płatnego output.
- **Agent z odczytem cache:** 400 tys. input bez cache, 600 tys. odczytów cache, 80 tys. output. Zakładamy już istniejący cache; utworzenie i utrzymanie trzeba doliczyć.
- **Dużo output:** 100 tys. input bez cache i 100 tys. output.

W każdym profilu output obejmuje rozliczane rozumowanie. Używamy podstawowego progu kontekstu każdego żądania, stawek standardowych i PEAK DeepSeek. Brak batch/flex, narzędzi, infrastruktury, podatków i abonamentów. To porównanie przy identycznych liczbach tokenów; realny tekst ma różne tokenizacje.

| Model | Patch USD | Agent/cache USD | Dużo output USD |
|---|---:|---:|---:|
| GPT 5.6 Luna | 0.0440 | 0.1880 | 0.1400 |
| GPT 5.6 Terra | 0.4400 | 1.8800 | 1.4000 |
| GPT 5.6 Sol | 0.8000 | 3.4400 | 2.4000 |
| Claude Sonnet 5 | 0.4000 | 1.7200 | 1.2000 |
| Claude Opus 5 | 1.0000 | 4.3000 | 3.0000 |
| Claude Fable 5.1 | 2.0000 | 8.1500 | 6.0000 |
| Deepseek V4 Flash 0731 | 0.0704 | 0.2900 | 0.1760 |
| Deepseek V4 Pro 0813 | 0.2112 | 0.8712 | 0.5280 |
| Gemini 3.1 Flash-Lite | 0.0550 | 0.2350 | 0.1750 |
| Gemini 3.8 Flash | 0.1500 | 0.6450 | 0.4500 |
| Kimi k3 | 0.6000 | 2.5800 | 1.8000 |

Stawki pochodzą z [OpenAI API pricing](https://developers.openai.com/api/docs/pricing), [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/) i [Moonshot K3](https://platform.kimi.ai/docs/pricing/chat-k3).

Przykładowo, przy profilu Patch Sonnet 5 kosztuje 0,40 USD, a Opus 5 1,00 USD. Aby wyrównać sam koszt na zaakceptowane zadanie w uproszczonym modelu jednakowych kosztów próby, Opus musiałby osiągać 2,5 raza wyższą skuteczność. To warunek algebraiczny, nie zmierzona różnica jakości. Czas człowieka, narzędzia i różne długości odpowiedzi mogą zmienić wynik decyzji.

Koszt cache nie kończy się na cache hit. Anthropic rozróżnia zapis 5-minutowy i godzinny; Google dolicza przechowywanie. Z kolei DeepSeek ma harmonogram zniżek poza szczytem. Różne warunki taryfy trzeba zapisać jako osobne warianty, zamiast nadpisywać jedną cenę. [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [Google](https://ai.google.dev/gemini-api/docs/pricing), [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing/).

## Jak wykorzystać istniejące badania

SWE-bench Verified w widoku Bash Only uruchamia modele w tym samym mini-SWE-agent na 500 zadaniach. To lepszy punkt wyjścia do porównania modeli niż łączenie rekordów producentów z różnymi agentami. Nadal należy zachować wersję agenta, commit, limity i surowe ślady wykonania. [Oficjalny SWE-bench](https://www.swebench.com/).

Terminal-Bench pokazuje model, agenta, skuteczność, koszt i tokeny; aktualna strona dotyczy wersji 4.0. Istniejący importer projektu pobiera pole `terminalBench2`, dlatego nie wolno automatycznie przypisać nowych wyników do starej kolumny ani zestawiać ich jako jednego testu. [Oficjalny Terminal-Bench](https://www.tbench.ai/).

Kategorie BenchLM służą do stworzenia listy kandydatów. `supported` i `estimated` opisują pozycję w metodologii agregatora, nie statystyczną pewność wygranej w naszych zadaniach. Liczba rekordów nie jest liczbą niezależnych badań. Brak kategorii Agentic nie oznacza zerowej jakości. [Metodologia i zakres danych BenchLM](https://benchlm.ai/data).

## Proponowane własne badanie

1. Wybrać sześć rzeczywiście dostępnych kandydatów z różnych przedziałów cen. Przykładowa lista kosztowa do sprawdzenia dostępu: Sonnet 5, Opus 5, GPT-5.6 Sol, GPT-5.6 Terra, DeepSeek V4 Pro i Gemini 3.8 Flash. To lista eksperymentu, nie ranking skuteczności.
2. Przygotować 60 zadań z projektów użytkownika: po 15 napraw błędów, zmian wielu plików, pracy z testami i działań agenta w terminalu. Oddzielić przykłady do strojenia instrukcji od zbioru oceny. Zadania powinny mieć automatyczne kryterium akceptacji i kontrolę niepożądanych zmian.
3. Najpierw pilotaż 12 zadań × 2 powtórzenia × 6 modeli = 144 wykonania. Z niego ustalić rzeczywisty budżet; dopiero później 60 × 3 × 6 = 1080 wykonań. W tej aktualizacji niczego z tych pul nie uruchomiono.
4. Zamrozić snapshot modelu, agenta i repozytorium, prompt, narzędzia, limity czasu, retry, budżet tokenów i rozumowania. Wspólny limit rozumowania nie zawsze jest dostępny; wtedy raportować oddzielny wariant, nie deklarować identycznych warunków.
5. Rejestrować sukces, koszt każdej próby, input/cache read/cache write/output, czas do akceptacji, wywołania narzędzi, retry i minuty interwencji człowieka. Nie liczyć oddzielnie reasoning, jeśli jest już zawarty w output dostawcy.
6. Publikować skuteczność oraz przedział 95%, koszt na zaakceptowane zadanie i p50/p95 czasu. Porównania liczyć na tych samych zadaniach, z niepewnością uwzględniającą powtórzenia w obrębie zadania. Nie traktować powtórzeń jako nowych, niezależnych problemów.

**Podstawowa miara ekonomiczna:** suma kosztów wszystkich prób, narzędzi i interwencji / liczba zaakceptowanych zadań. Przy zerze sukcesów koszt na sukces jest nieokreślony/nieskończony, nigdy zero. Stawkę godziny pracy człowieka użytkownik ustala jawnie.

## Następne etapy

**Dane:** rozdzielić encje model/snapshot, endpoint/dostawca, taryfa i obserwacja benchmarku. Każda obserwacja powinna mieć `benchmark_version`, `harness_commit`, `model_snapshot`, `reasoning_effort`, `task_count`, `run_budget`, `source_url`, `observed_at` i `comparison_group`. Żadnego dopasowania wyłącznie po nazwie marketingowej.

**Koszt:** dodać strukturalne progi kontekstu, tryby standard/batch/flex, cache write/storage, region i czas obowiązywania taryfy. Obecny kalkulator świadomie ogranicza się do podstawowych tokenów. Dostęp API i abonament IDE wymagają osobnych tabel.

**Jakość aktualizacji:** fixture dla każdego dostawcy, kontrola ubytku katalogu, monitoring świeżości cen i osobno badań, archiwizacja obserwacji źródłowych. Obecna poprawka dodaje testy dwóch uszkodzonych parserów, wykluczenia audio, integralności aktualizacji, importu badań i obliczeń; nie jest pełnym pokryciem wszystkich układów cenników.

**Interfejs:** zachować lekki GitHub Pages. Dodać profile własnych zadań, eksport wyników eksperymentu i wykres koszt–skuteczność z niepewnością dopiero po zebraniu porównywalnych pomiarów. Obecne oznaczenia Pareto dotyczą wyłącznie poglądowych kategorii.
