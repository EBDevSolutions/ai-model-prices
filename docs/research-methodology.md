# Metodologia i źródła badań

Aktualizacja: 8 września 2026. Zakres: wybór modeli do programowania i pracy agentów. Badania pochodzą od wskazanych autorów; nie przedstawiamy ich jako własnych pomiarów.

## Co było niekompletne

Poprzedni importer ograniczał się do kilkunastu kluczy BenchLM. Nie pobierał pełnych wyników Artificial Analysis, a domyślna kategoria Coding pomijała modele bez kompozytu. Flaga estimated na poziomie całego modelu mogła odsunąć od rankingu model z dostępnymi pomiarami. Usunięcie mylących rankingów nie rozwiązało braku pokrycia źródeł.

W tym samym zbiorze **51 aktywnych pozycji z porównywalną ceną tekstu** poprzednie dane zawierały surowe wyniki dla **28 modeli**. Nowe źródło AA daje wyniki dla **38**. Nie jest to wzrost liczby wyników tego samego testu: import rozszerza liczbę modeli i zakres metryk. Katalog ma również pozycje nieaktywne lub bez porównywalnej ceny; nie zwiększają tego mianownika.

| Test w nowym źródle | Modele z przynajmniej jednym zmapowanym wariantem |
|---|---:|
| Terminal-Bench 4.0 | 27/51 |
| Terminal-Bench 2.1 | 30/51 |
| SciCode | 29/51 |
| AutomationBench | 29/51 |
| GPQA Diamond | 38/51 |
| Humanity’s Last Exam | 38/51 |

To pokrycie źródłowe, a nie liczba modeli dopuszczonych do konkretnego rankingu. Wybrany wariant może mieć mniej wyników. Reguły mapowania są w `data/research-model-map.json`; obserwacje i bieżące liczniki w `data/research.json`.

## Źródła i ich role

| Źródło | Zastosowanie | Warunek użycia |
|---|---|---|
| Artificial Analysis | Główne niezależne pomiary jakości, warianty rozumowania, koszt zadań własnego indeksu, szybkość | Zachować konkretny test, wersję, konfigurację oraz jednostkę |
| Oficjalne SWE-bench / Terminal-Bench | Porównania systemów model + agent; weryfikacja warunków eksperymentu | Ten sam zbiór i wersja agenta; wyników różnych konfiguracji nie podpisywać jako jeden wynik modelu |
| Oficjalne raporty producentów | Nowości, specyficzne możliwości, wyniki nieobecne u niezależnego badacza | Oznaczenie vendor-reported; nie mieszać z niezależnym pomiarem w jednej komórce |
| BenchLM | Uzupełniający katalog i odnośniki do badań | Status i pochodzenie osobno; kompozyt nie zastępuje brakującego wyniku konkretnego testu |
| Własne zadania użytkownika | Ostateczna decyzja ekonomiczna | Ten sam zestaw zadań, kryteria akceptacji i ewidencja kosztów wszystkich prób |

Źródła: [Artificial Analysis](https://artificialanalysis.ai/), [SWE-bench](https://www.swebench.com/), [Terminal-Bench](https://www.tbench.ai/), [BenchLM dataset](https://benchlm.ai/data). Integracja tej zmiany dotyczy AA. Nie deklaruje automatycznego importu całych pozostałych leaderboardów.

## Jedna obserwacja, konkretne znaczenie

Identyfikujemy dostawcę, rodzinę i wariant na podstawie jawnej mapy. Każdy wariant AA zachowuje stabilny identyfikator źródła, slug, nazwę z poziomem rozumowania i informacją o fallback, URL oraz datę odczytu. Wersje i warunki testów są w rejestrze metryk. Nie potwierdzamy dokładnego snapshotu API, jeżeli źródło go nie identyfikuje; zakres mapowania jest jawny.

`retrieved_at` oznacza pobranie danych. `evaluated_at` pozostaje puste, gdy data wykonania nie została udostępniona. Zmiana cennika lub przebieg workflow nie odświeża daty wykonania badania. Zera pozostają zerami, null nie staje się zerem, a brak dopasowania nie oznacza, że badanie nie istnieje.

Domyślny wariant wskazuje jawna mapa, zazwyczaj główna strona źródła. Nie wybieramy wariantu maksymalizującego wynik. Użytkownik może go zmienić; wybór pozostaje widoczny i zapisuje się lokalnie.

## Rozdzielenie benchmarków

Terminal-Bench 4.0 w AA obejmuje 66 zadań z mini-SWE-agent 2.4.6, pass@1 i trzema powtórzeniami. Wersja 2.1 ma 89 zadań oraz Terminus 2. To oddzielne kolumny, bez wspólnego rankingu. SciCode 1.0.1 oznacza wynik podproblemów z dodatkowym kontekstem naukowym. AutomationBench-AA używa prywatnego podzbioru 657 zadań wersji 1.0.6; importowane pole jest wynikiem częściowym, nie wskaźnikiem całkowitego ukończenia zadań. [Metodologia AA](https://artificialanalysis.ai/methodology/intelligence-benchmarking).

Nie mieszamy procentów, punktów indeksu i Elo. Nie uśredniamy Terminal-Bench, SciCode i GPQA w nowy autorski „Coding score”. AA Intelligence Index 4.3 jest osobną opublikowaną miarą. Indeksy AA oraz BenchLM nie są tą samą skalą. Flaga szacowania indeksu nie unieważnia automatycznie surowych pomiarów tego wariantu.

## Astra: przykład brakującego pokrycia

W poprzednim katalogu Astra miała dwa surowe wyniki z agregatora i brak Coding. Nowy import pokazuje 14 opublikowanych miar dla wariantu **GPT-6 Astra (max)**, w tym:

| Miara | Wynik |
|---|---:|
| Terminal-Bench 4.0 · AA | 59,09% |
| SciCode · AA | 56,48% |
| AutomationBench · AA, wynik częściowy | 68,49% |
| GPQA Diamond · AA | 96,06% |
| AA Intelligence Index 4.3 | 52,81 pkt |

Wyniki odczytano z danych wykresów [strony Astry w Artificial Analysis](https://artificialanalysis.ai/models/gpt-6-astra). To jeden wariant i jedna wersja źródła, nie stała cecha wszystkich konfiguracji Astry.

Publiczny katalog AA zawiera również etykietę Astra non-reasoning. Oficjalna karta OpenAI wymienia poziomy low, medium, high, xhigh i max. Dlatego tę obserwację pokazujemy wyłącznie informacyjnie, bez łączenia z ceną w rankingu. [Oficjalna karta GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra). Analogicznie traktujemy niepotwierdzone przejście preview → stabilny endpoint. Konfiguracje z fallback są widoczne, ale nie łączymy ich z ceną jednego modelu w rankingu kosztowym: wykonanie może obejmować więcej niż jeden model.

## Trzy różne koszty

1. **Koszt tokenów użytkownika:** założony wolumen × ceny API. Pomaga planować wydatki, ale nie mierzy liczby prób potrzebnych do sukcesu.
2. **Koszt zadania AA Index:** koszt opublikowany dla ważonego zestawu zadań całego indeksu. Pokazujemy go oddzielnie w szczegółach; nie podpisujemy jako kosztu SciCode lub Terminal-Bench. Rozbicie i zakres publikuje [AA](https://artificialanalysis.ai/models/gpt-6-astra).
3. **Koszt zaakceptowanego zadania użytkownika:** wszystkie próby, narzędzia, infrastruktura i czas człowieka podzielone przez liczbę zaakceptowanych rezultatów. Wymaga własnego eksperymentu; obecny import go nie dostarcza.

Iloraz jakości wybranego testu przez scenariusz tokenowy jest poglądowy. Oznaczenia Pareto zależą od wyboru modeli i wariantów; nie dowodzą statystycznej przewagi. Warto mierzyć równolegle skuteczność oraz p50/p95 czasu. Szybkość output i czas do pierwszego tokena nie oznaczają czasu ukończenia zadania agenta.

## Aktualizacja i odporność

Importer czyta publiczne dane serializowane dla wykresów strony AA. Nie wykonuje JavaScript pobranej strony ani nie odwołuje się do chronionych endpointów. Wymaga rozpoznanej wersji indeksu 4.3, poprawnego schematu, co najmniej 100 wariantów, spójnych identyfikatorów i poprawnych zakresów liczb. Zmiana wersji, duży ubytek katalogu lub błąd sieci zachowuje ostatnie obserwacje z oznaczeniem błędu źródła.

Nowe modele i warianty wymagają przeglądu mapowania. Rezygnujemy z automatycznego dopasowania „podobnej nazwy”: przypadki DeepSeek Flash/Vision, Grok 0309/v2/multi-agent i endpointy highspeed pokazują ryzyko takiego skrótu. Po poprawnym odczycie wycofany wynik znika z bieżącej obserwacji, zamiast pozostawać bezterminowo.

Czytanie wyników jest niezależne od rankingu. Starsze obserwacje są nadal widoczne; błędny lub starszy niż 7 dni odczyt AA nie zasila rankingu kosztowego. To polityka świeżości odczytu, nie gwarancja wieku eksperymentu. Cena ma oddzielny próg 48 godzin.

AA oferuje także [oficjalne Data API](https://artificialanalysis.ai/api-reference). Wymaga klucza, a dokumentacja nakazuje atrybucję i buforowanie poza przeglądarką. Obecny importer nie wymaga klucza. API jest sensownym przyszłym adapterem, ale migracja musi zachować wersje testów oraz zakres dostępnych pól; przykład dokumentacji nie obejmuje wszystkich aktualnych benchmarków. Dane strony mogą zmienić strukturę, więc testy fixture i widoczny status źródła pozostają konieczne.

## Pozostałe luki i kolejne badania

13 aktywnych pozycji z ceną tekstową nie ma zatwierdzonego mapowania AA: Qwen 3.7 Flash, Mythos 5/5.1, DeepSeek Flash Vision Exp, Gemini Computer Use / Omni / Robotics, Kimi K2.7 Code Highspeed, chat-latest, Grok 4.20 multi-agent oraz Grok Build 0.1. To kolejka weryfikacji tożsamości i źródeł, nie lista modeli „bez badań”. Dokładne identyfikatory są w `research.json` ze statusem unmapped.

Następnie należy pozyskać wyniki z oficjalnych leaderboardów do osobnych obserwacji, uzupełnić dokładne snapshoty i koszty dla pojedynczych benchmarków, a potem przeprowadzić pilotaż na własnych zadaniach. Protokół tego pilotażu pozostaje w [raporcie z 7 września](research-review-2026-09-07.md). Tej pracy nie zastępuje zwiększenie liczby kolumn w tabeli.
