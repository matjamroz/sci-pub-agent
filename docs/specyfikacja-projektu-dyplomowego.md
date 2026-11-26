# Specyfikacja projektu

Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych. Autorzy: Jamroż, Szymon Kiełtyka.

Dokument opisuje zamierzenie. Prace implementacyjne jeszcze się nie zaczęły.

## Cel biznesowy

Publikacje naukowe są zapisane jako rekordy: tytuł, rok, identyfikator, abstrakt, słowa kluczowe i autorzy. Osoba, która chce wiedzieć, jakie kierunki dominują, jak wygląda wzorzec ich rozwoju, które tematy wiążą się ze sobą albo kto z kim publikuje, musi dziś przeglądać rekordy i liczyć je ręcznie. Wyszukiwanie po słowach zwraca listę prac, a nie odpowiedź na pytanie.

Celem jest zaprojektowanie i implementacja agenta konwersacyjnego. Agent odpowiada na pytania o trendy, zależności i wzorzec rozwoju w publikacjach naukowych. Pozwala eksplorować cały wczytany zbiór w języku naturalnym, wskazywać dominujące kierunki badawcze oraz analizować związki między autorami i tematami. Odpowiedź wynika z rekordów bazy i wskazuje, na jakich publikacjach się opiera.

Aplikacja jest gotowa, gdy obejmuje cały uzgodniony zakres: wczytanie i indeks zbioru, klasyfikację tematyczną, wyszukiwanie semantyczne w bazie wektorowej, zestawienia trendów i zależności, profile autorów, złożenie odpowiedzi przez model językowy oraz interfejs do rozmowy po polsku i po angielsku. Konta użytkowników i wdrożenie produkcyjne nie wchodzą w ten cel.

## Wizja systemu

Użytkownikiem jest osoba analizująca dorobek naukowy. Może prowadzić wiele czatów. Przy zakładaniu czatu wybiera, czy ma on dostać kontekst innego, już istniejącego czatu, czy ma zacząć bez tej historii. W obrębie jednego czatu zadaje pytanie zwykłym zdaniem i prowadzi rozmowę dalej, bez powtarzania tytułu albo nazwiska, jeśli wynika ono z poprzedniej wypowiedzi tego czatu. Dostaje odpowiedź wraz ze źródłami. Przy liczebności tematów i zmianie w latach widzi też zestawienie, które da się odczytać jako wykres.

Aplikacja jest systemem typu RAG opartym na modelu językowym i zintegrowanym z bazą publikacji. Składa się z warstw, które działają razem, a nie z jednego okna wyszukiwania.

Warstwa danych wczytuje plik ze zbiorem, porządkuje metadane i scala autorów po trwałym identyfikatorze, jeśli jest w rekordzie.

Warstwa klasyfikacji grupuje publikacje metodami uczenia maszynowego na podstawie treści, przede wszystkim tytułu i abstraktu. Dzięki temu da się pytać o kierunki badawcze i o to, które z nich są najliczniejsze, a nie tylko o pojedynczy tytuł.

Warstwa wyszukiwania zapisuje tytuł i abstrakt w bazie wektorowej i znajduje publikacje najbliższe znaczeniowo pytaniu. To jest moduł wyszukiwania semantycznego.

Warstwa zestawień liczy na metadanych to, czego sam wektor nie policzy: popularność tematów, liczebność w kolejnych latach, wzorzec rozwoju kierunku oraz profil autora, czyli jego publikacje i kierunki, które z tych publikacji wychodzą.

Warstwa odpowiedzi rozpoznaje, o co chodzi w wypowiedzi, woła wyszukiwanie, zestawienie albo oba, i zleca modelowi językowemu ułożenie krótkiej odpowiedzi w języku pytania. Model składa zdanie wyłącznie z wyników tych warstw. Twierdzenia o konkretnych pracach, latach i osobach pochodzą z rekordów. Gdy rekordu nie ma, aplikacja tak mówi i przyjmuje kolejne pytanie.

Zakres aplikacji obejmuje więc przetwarzanie i indeksowanie publikacji, ich klasyfikację, wyszukiwanie semantyczne, analizę trendów czasowych i popularności tematów, związki autora z kierunkami jego prac, integrację z modelem językowym oraz interfejs rozmowy.

Aplikacja obsługuje w szczególności: znalezienie prac o wskazanym zagadnieniu, listę autorów wskazanej pracy, listę dominujących kierunków, liczbę publikacji kierunku w latach i opis wzorca rozwoju, dorobek osoby i tematy jej prac oraz dopytanie o pracę albo osobę wspomnianą wcześniej w rozmowie.

## Wymagania funkcjonalne

Aplikacja przyjmuje wypowiedź w języku naturalnym, po polsku albo po angielsku, i zwraca odpowiedź opartą na wczytanym zbiorze. Pusta wypowiedź nie jest poleceniem wobec bazy: aplikacja informuje, że brakuje treści, i nie zapisuje nowego rekordu.

Zbiór jest wczytywany z pliku jsonl. Każda publikacja wnosi identyfikator, tytuł, rok, abstrakt, słowa kluczowe i listę autorów. Po wczytaniu widać, ile rekordów jest w bazie i jaki zakres lat obejmują. Podanie pliku, którego nie ma, kończy się komunikatem o niepowodzeniu i nie kasuje danych znajdujących się w bazie.

Tytuł i abstrakt każdej pracy trafiają do bazy wektorowej. Pytanie o treść albo o zagadnienie jest zamieniane na ten sam rodzaj reprezentacji i aplikacja wybiera publikacje najbliższe pytaniu. Odpowiedź podaje co najmniej tytuł i rok oraz wskazuje te prace jako źródła. W ten sposób użytkownik znajduje publikacje po sensie pytania, także gdy w pytaniu nie ma dokładnego tytułu.

Klasyfikacja przypisuje publikacjom kierunki badawcze. Aplikacja potrafi podać nazwy dominujących kierunków i liczbę publikacji w każdym z nich, dla całego zbioru albo dla wskazanego roku. Przy pytaniu o zmianę w czasie albo o wzorzec rozwoju podaje liczebność kierunku w kolejnych latach, które są w danych, i na tej podstawie opisuje, czy kierunek rośnie, maleje, czy trzyma podobny poziom. Gdy zbiór ma jeden rok, podaje liczebność za ten rok i nie przedstawia jednego punktu jako wieloletniego trendu. Obok tekstu jest wykres liczebności.

Związki autora z tematami aplikacja czyta z rekordu: przy pracy jest lista autorów, a kierunek pochodzi z klasyfikacji jej treści. Dla wskazanej pracy podaje autorów zapisanych przy tym rekordzie. Dla wskazanej osoby pokazuje jej publikacje, lata i kierunki. Dla wskazanego kierunku pokazuje, którzy autorzy mają w zbiorze prace z tego kierunku. Brak osoby w zbiorze jest mówiony wprost, bez dopisywania dorobku spoza bazy. Profil pokazuje dopasowane osoby i ich prace, żeby dało się zobaczyć, kogo aplikacja wzięła.

Użytkownik może założyć wiele czatów i wracać do każdego z nich. Przy nowym czacie zaznacza, czy ma on zawierać kontekst innego czatu. Jeśli tak, wskazuje który, i dalsze wypowiedzi mogą odwoływać się także do tamtej historii. Jeśli nie, czat widzi tylko własne wypowiedzi. Kolejna wypowiedź w danym czacie może odwoływać się do pracy, autora albo kierunku z dostępnej historii. Aplikacja ustala, o który rekord chodzi. Gdy z tej historii nie da się tego rozstrzygnąć, mówi o tym i czeka na doprecyzowanie. Przy powitaniu albo pytaniu niezwiązanym ze zbiorem odpowiada krótko i proponuje pytania o publikacje, bez udawania wyniku wyszukiwania.

Model językowy układa odpowiedź po tym, jak warstwy danych zwrócą rekordy i liczby. Nie jest źródłem faktów o zbiorze. Każda odpowiedź oparta na publikacjach ma listę źródeł. Wynik jest w interfejsie rozmowy: tekst, źródła i wykres tam, gdzie zestawienie ma szereg albo ranking.

<div class="pagebreak"></div>

### Przypadki użycia

| ID | Przypadek | Przebieg |
| --- | --- | --- |
| PU-01 | Wczytanie zbioru | Osoba przygotowująca aplikację podaje plik jsonl. System zapisuje metadane, liczy kierunki i buduje bazę wektorową z tytułu i abstraktu. Po zakończeniu widać liczbę publikacji i zakres lat. Gdy pliku nie ma, baza pozostaje bez zmian, a użytkownik dostaje komunikat o niepowodzeniu. |
| PU-02 | Znalezienie prac po treści | Użytkownik pyta o zagadnienie własnymi słowami, bez dokładnego tytułu. Warstwa wyszukiwania porównuje pytanie z bazą wektorową i zwraca najbliższe publikacje. Odpowiedź podaje tytuł, rok i źródła. |
| PU-03 | Dominujące kierunki | Użytkownik pyta, jakie kierunki są najczęstsze, ewentualnie w podanym roku. Aplikacja podaje nazwy kierunków, liczby publikacji i wykres liczebności. |
| PU-04 | Wzorzec rozwoju kierunku | Użytkownik pyta, jak zmienia się liczba prac w danym kierunku. Aplikacja podaje liczebność w kolejnych latach obecnych w zbiorze i opisuje, czy jest wzrost, spadek, czy podobny poziom. Przy jednym roku podaje liczebność za ten rok. |
| PU-05 | Autorzy wskazanej pracy | Użytkownik pyta, kto jest autorem konkretnej publikacji. Aplikacja podaje osoby zapisane przy tym rekordzie. |
| PU-06 | Dorobek osoby | Użytkownik podaje imię i nazwisko. Aplikacja pokazuje dopasowane osoby, ich publikacje, lata i kierunki. Gdy osoby nie ma w zbiorze, mówi o tym i nie dopisuje prac spoza bazy. |
| PU-07 | Autorzy kierunku | Użytkownik pyta, kto publikuje w danym kierunku. Aplikacja wskazuje autorów, których prace zostały do tego kierunku zaklasyfikowane, razem z tymi pracami. |
| PU-08 | Dopytanie | Po odpowiedzi o pracy, osobie albo kierunku użytkownik mówi dalej w tym samym czacie, bez powtarzania nazwy. Aplikacja ustala rekord z historii dostępnej w tym czacie. Gdy nie da się go ustalić, prosi o doprecyzowanie. |
| PU-09 | Wiele czatów | Użytkownik zakłada kolejny czat. Wybiera, czy czat ma zawierać kontekst innego czatu. Przy wyborze „tak” wskazuje czat źródłowy i nowa rozmowa może nawiązywać do jego historii. Przy wyborze „nie” nowy czat nie widzi wypowiedzi z pozostałych czatów. Istniejące czaty zostają na liście i da się do nich wrócić. |
| PU-10 | Wypowiedź pusta albo spoza zbioru | Użytkownik nic nie wpisuje, wita się albo pyta o coś spoza publikacji. Aplikacja nie zmienia bazy. Przy pustym wejściu informuje o braku treści. Przy powitaniu odpowiada krótko i proponuje pytania o zbiór. |

## Opis niefunkcjonalny

Rozmowa działa po polsku i po angielsku, a zdanie odpowiedzi jest w języku wypowiedzi użytkownika. Przy faktach dotyczących prac, lat, kierunków i osób widać źródła, tak aby twierdzenie dało się sprawdzić w rekordzie. Dotyczy to zarówno wyszukanej treści, jak i liczb z zestawień oraz publikacji i kierunków przypisanych autorowi.

Baza wektorowa, grupy tematyczne i metadane powstają przy wczytaniu zbioru. Pytania o treść, trendy i autorów dotyczą tego samego zbioru.

Aplikacja uruchamia się na stanowisku autorów i da się z niej korzystać w zwykłej rozmowie: czas odpowiedzi na pojedyncze pytanie ma pozwalać na ciąg dalszy, a nie na długie oczekiwanie między zdaniami. Budowa indeksu całego zbioru jest czynnością wsadową i może trwać dłużej niż jedno pytanie. Aplikacja nie obejmuje kont użytkowników ani wdrożenia produkcyjnego.

Sprawdzenie działania ma objąć cały zakres, a nie jeden typ pytania. Dla wyszukiwania treści właściwa publikacja ma się pojawiać wśród pierwszych wyników. Dla kierunków, liczebności w latach i wzorca rozwoju liczby mają zgadzać się ze zbiorem. Dla profilu autora i związku autora z kierunkiem odpowiedź ma wskazywać osoby i prace faktycznie zapisane w danych. Dla faktów oczekiwana informacja ma być w odpowiedzi albo w dołączonych źródłach. Dopytanie w drugiej turze ma dotyczyć tej samej pracy albo osoby, o której była mowa wcześniej.

Błędna albo pusta wypowiedź nie kończy się awarią. Użytkownik dostaje komunikat, a dane, indeks i grupy tematyczne pozostają bez zmian.

## Analiza ryzyka

| ID | Ryzyko | Co z tym robimy |
| --- | --- | --- |
| R1 | Odpowiedź może podać pracę, rok albo autora, których nie ma w zbiorze. | Zdanie o faktach składamy z wyszukanych rekordów i z zestawień, i pokazujemy źródła. Sprawdzenie zgodności z danymi obejmie treści, trendy i powiązania autorów. |
| R2 | To samo nazwisko może oznaczać różne osoby. | Autorów scalamy po trwałym identyfikatorze, jeśli jest w danych. Profil pokazuje dopasowane osoby i ich prace. |
| R3 | Klasyfikacja może przypisać pracę do złego kierunku. | Kierunek bierzemy z treści rekordu: tytułu, abstraktu i słów kluczowych. Przy popularności, wzorcu rozwoju i autorach kierunku widać prace, z których wzięła się liczebność. Sprawdzenie obejmie, czy przypisanie zgadza się z tą treścią. |
| R4 | Wyszukiwanie może zwrócić pracę, która jest w zbiorze, ale nie odpowiada na pytanie. | Odpowiedź podaje tytuł i rok źródeł. Sprawdzenie obejmuje, czy właściwa praca jest wśród pierwszych wyników. |

## Harmonogram i podział pracy

| Etap | Zadania | Termin | Odpowiedzialny |
| --- | --- | --- | --- |
| 1 | Analiza literatury, zapoznanie się z bazami danych publikacji, doprecyzowanie zakresu i architektury systemu | 30.11.2026 | Jamroż, Kiełtyka |
| 2 | Przetwarzanie i eksploracja danych, indeksowanie publikacji | 31.12.2026 | Jamroż, Kiełtyka |
| 3 | Implementacja modułu wyszukiwania semantycznego (RAG) | 31.12.2026 | Jamroż |
| 4 | Klasyfikacja publikacji z wykorzystaniem uczenia maszynowego | 31.12.2026 | Jamroż, Kiełtyka |
| 5 | Implementacja interfejsu użytkownika | 31.12.2026 | Kiełtyka |
| 6 | Integracja modułów, testy i ewaluacja systemu | 31.12.2026 | Jamroż, Kiełtyka |
| 7 | Przygotowanie dokumentacji i finalnej wersji pracy dyplomowej | 31.12.2026 | Jamroż, Kiełtyka |
