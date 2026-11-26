# Agent do odpowiadania na pytania dotyczące trendów i zależności w publikacjach naukowych

Autorzy: Mateusz Jamroż, Szymon Kiełtyka. Etap 2, spotkanie 05.11.2026.

Dokument przedstawia plan rozwiązania oraz wstępny raport o danych. Z aplikacji będzie korzystał użytkownik końcowy, który zadaje pytania w oknie rozmowy. Osobną rolę będzie miał analityk danych. Za pomocą kodu pomocniczego przygotuje zbiór, wyznaczy kierunki badawcze, zbuduje bazę wektorową i policzy potrzebne zestawienia.

## Propozycja rozwiązania

Planujemy zbudować agenta konwersacyjnego typu RAG. Po zadaniu pytania system najpierw wyszuka odpowiednie publikacje albo odczyta wcześniej policzone zestawienie. Dopiero na tej podstawie model językowy ułoży odpowiedź. Nie powinien dopisywać publikacji, lat ani autorów, których nie ma w wyniku. Pod odpowiedzią pokażemy źródła: tytuł, rok i DOI, jeżeli jest dostępny.

### Ocena narzędzi i technik

Narzędzia dobieramy do pracy lokalnej i do zbioru liczącego około 622 tysiące publikacji. Przy wyborze bierzemy pod uwagę jakość wyników po polsku i angielsku, czas przygotowania całego zbioru, szybkość pojedynczej odpowiedzi, zużycie pamięci oraz łatwość odtworzenia rozwiązania na komputerze autorów. Przygotowanie indeksu będzie osobnym zadaniem wykonywanym przez analityka, a podczas rozmowy system skorzysta z gotowej bazy.

| Składnik | Wybór | Rozważane | Uzasadnienie |
| --- | --- | --- | --- |
| Język | Python 3.11 | Java, R | Python ma dojrzałe biblioteki do modeli embeddingowych, uczenia maszynowego, wyszukiwania i budowy API. Dzięki temu cały przepływ przygotujemy w jednym języku, bez łączenia kilku środowisk. Java wymagałaby dodatkowej integracji z narzędziami uczenia maszynowego, a R lepiej nadaje się do analizy niż do budowy całej aplikacji. |
| Interfejs programistyczny | FastAPI | Flask, Django | FastAPI automatycznie sprawdza strukturę danych wejściowych i tworzy dokumentację API, co ułatwi testowanie komunikacji z interfejsem. Flask jest prosty, ale wymagałby ręcznego dodania walidacji. Django oferuje panel administracyjny i obsługę kont, których nie planujemy. |
| Metadane | SQLite | PostgreSQL | Aplikacja ma działać lokalnie i nie przewidujemy wielu osób zapisujących dane jednocześnie. SQLite obsłuży powiązane tabele publikacji, autorów i kierunków, a cała baza pozostanie jednym łatwym do przeniesienia plikiem. PostgreSQL byłby uzasadniony dopiero przy pracy sieciowej i wielu równoczesnych użytkownikach. |
| Baza wektorowa | Chroma | FAISS, pgvector, Oracle 23ai Free | Chroma zapisze wektory razem z identyfikatorami i metadanymi publikacji, obsłuży trwały zapis na dysku oraz wyszukiwanie cosinusowe bez osobnego serwera. FAISS zapewnia szybkie wyszukiwanie, ale metadane trzeba przechowywać osobno. pgvector wymaga PostgreSQL, a Oracle 23ai Free nie oblicza embeddingów i uzależniłby prezentację od usługi w chmurze. |
| Embedding | BAAI/bge-m3 | intfloat/multilingual-e5-large, intfloat/multilingual-e5-base, all-mpnet-base-v2, all-MiniLM-L6-v2 | Najważniejszy przypadek to polskie pytanie dopasowane do angielskiego abstraktu. bge-m3 obsługuje oba języki, przyjmuje do 8192 tokenów i zwraca wektor 1024-wymiarowy. e5-large osiąga nieco lepszy wynik w krótkim teście polskim, ale przy 512 tokenach może uciąć przygotowany tekst. e5-base jest słabszy, a modele mpnet i MiniLM są nastawione głównie na angielski. Trafność bge-m3 sprawdzimy na pytaniach polskich i angielskich, w tym na przypadkach międzyjęzykowych. |
| Kierunki | grupowanie KMeans na wektorach, nazwa ze słów kluczowych | samo liczenie słów kluczowych, klasyfikator z gotowymi etykietami | Zbiór nie zawiera gotowych kierunków ani etykiet do uczenia klasyfikatora. KMeans pozwoli pogrupować publikacje o podobnej treści bez danych uczących, a słowa kluczowe posłużą do nazwania grup. Liczbę grup porównamy dla kilku ustawień, a jakość ocenimy na próbce publikacji pod względem spójności treści i czytelności nazw. |
| Wyszukiwanie | połączenie wyszukiwania wektorowego i słownego (BM25, RRF) | samo BM25, sam wektor | Wektor pomaga znaleźć publikacje opisane innymi słowami, natomiast BM25 lepiej obsługuje dokładne tytuły, nazwiska i rzadkie terminy. RRF połączy kolejność obu list bez porównywania niezgodnych skal wyników. Skuteczność rozwiązania porównamy z samym BM25 i samym wyszukiwaniem wektorowym. |
| Model językowy | lokalny model wybrany po testach, przez API zgodne z OpenAI | Qwen3 4B, Qwen3 8B, Llama 3.2 3B, usługa w chmurze | Modele porównamy na tych samych pytaniach pod względem zgodności z przekazanymi źródłami, poprawności języka polskiego i angielskiego, czasu odpowiedzi oraz zużycia pamięci. Wybierzemy najmniejszy model, który będzie działał płynnie i nie będzie dopisywał informacji spoza wyników wyszukiwania lub zestawień. |
| Interfejs | Streamlit | React | Streamlit działa w Pythonie i wystarczy do przygotowania rozmowy, listy czatów oraz źródeł, więc ograniczy liczbę technologii i czas integracji. React dawałby większą swobodę wyglądu, ale wymagałby osobnego projektu frontendowego bez istotnej korzyści dla planowanych funkcji. |
| Uruchomienie | rozmowa na komputerze autorów, jednorazowe liczenie wektorów na dwóch GPU | sam procesor laptopa, Oracle Free Tier, klaster jako część aplikacji | Najbardziej kosztowne będzie jednorazowe policzenie około 622 tysięcy wektorów, dlatego planujemy wykorzystać dwie karty NVIDIA T4 w Kaggle i obliczenia FP16. Gotowe pliki pobierzemy na komputer i zbudujemy z nich lokalną bazę Chroma. Podczas rozmowy powstaje tylko jeden wektor pytania, więc ten etap powinien działać na procesorze i nie wymagać stałego dostępu do chmury ani klastra. |

### Założenia techniki modelowania

W danych nie ma gotowej nazwy kierunku badawczego. Planujemy traktować kierunek jako grupę publikacji o podobnej treści. Przed grupowaniem ustalimy liczbę takich grup i podamy ją przy wynikach, ponieważ wpływa ona na poziom szczegółowości podziału. Nazwę każdej grupy utworzymy z najczęstszych słów kluczowych należących do niej publikacji. Będzie to pomocnicza etykieta, a nie informacja pochodząca bezpośrednio ze zbioru.

Wzorzec rozwoju będziemy wyznaczać na podstawie liczby publikacji z danego kierunku w kolejnych latach. System opisze, czy liczba prac rośnie, maleje, czy pozostaje na podobnym poziomie. Wartości roku spoza zakresu 1900–2026 pominiemy, a pojedynczego roku nie będziemy przedstawiać jako wieloletniego trendu.

Podczas wyszukiwania system porówna pytanie z wektorami publikacji utworzonymi z tytułu, dostępnych abstraktów i słów kluczowych. Jeżeli rekord ma abstrakt polski i angielski, połączymy oba teksty, a całość ograniczymy do 3200 znaków. Samo podobieństwo wektorów nie gwarantuje jeszcze trafnej odpowiedzi, dlatego przy ocenie sprawdzimy, czy właściwa publikacja pojawia się wśród pierwszych wyników.

Autorów będziemy łączyć przede wszystkim po ORCID. Jeżeli go zabraknie, użyjemy kolejno uuid i identyfikatora autora z rekordu. Osoby o tym samym imieniu i nazwisku, ale różnych identyfikatorach, pozostaną oddzielone. W profilu pokażemy dopasowane osoby i ich publikacje.

Model językowy nie będzie sam wyszukiwał publikacji ani liczył trendów. Otrzyma gotowe wyniki z pozostałych modułów i na ich podstawie ułoży odpowiedź w języku pytania.

### Plan oceny skuteczności

Wyszukiwanie ocenimy na przygotowanym zestawie pytań po polsku i angielsku. Dla każdego pytania wskażemy publikacje, które powinny zostać znalezione, a następnie porównamy trzy warianty: samo wyszukiwanie słowne, samo wyszukiwanie wektorowe oraz wynik połączony. Sprawdzimy, w którym wariancie właściwe prace najczęściej pojawiają się w pierwszych dziesięciu wynikach i jak wysoko są na liście. Osobno uwzględnimy pytania polskie prowadzące do angielskich abstraktów.

Grupowanie kierunków sprawdzimy dla kilku wartości liczby grup. Porównamy spójność wektorów wewnątrz grup oraz ręcznie przejrzymy przykładowe publikacje i utworzone nazwy. Wybierzemy ustawienie, które daje grupy możliwe do zrozumienia i nie łączy wyraźnie różnych tematów.

Zestawienia liczbowe zweryfikujemy przez porównanie odpowiedzi systemu z wynikami zapytań wykonanych bezpośrednio na danych. W przypadku modelu językowego sprawdzimy, czy odpowiedź jest zgodna z przekazanymi rekordami, zawiera właściwe źródła i nie dodaje publikacji, autorów ani wartości liczbowych spoza wyniku. Zmierzymy także czas odpowiedzi i zużycie pamięci na komputerze autorów.

## Raport danych

Zbiór znajduje się w jednym pliku JSONL o rozmiarze 1 979 261 045 bajtów. Zawiera 621 515 rekordów. Wszystkie linie są poprawnym zapisem JSON, a identyfikatory publikacji nie powtarzają się. W rekordach znajdują się identyfikator, tytuł, rok, abstrakty, słowa kluczowe, lista autorów oraz DOI, jeżeli zostało podane.

Plik jest odfiltrowanym zbiorem publikacji przygotowanym pod to zadanie. Zawiera pola potrzebne do wyszukiwania i zestawień: identyfikator, tytuł, rok, DOI, abstrakty, słowa kluczowe i autorów. Nie zakładamy, że rekord ma abstrakt tylko w jednym języku ani że DOI jest zawsze obecne.

### Wstępna eksploracja

Zdecydowana większość rekordów ma rok mieszczący się w przyjętym zakresie. Dane obejmują wiele dekad, przy czym najwięcej publikacji przypada na nowszą część zbioru. Taki rozkład pozwoli analizować zmiany liczby publikacji w czasie.

Najczęściej występują abstrakty angielskie, a drugą dużą grupę stanowią abstrakty polskie. Jedna publikacja może mieć obie wersje językowe. W mniejszej liczbie występują również abstrakty w innych językach. Ponieważ użytkownik może zadać pytanie po polsku o publikację opisaną po angielsku, planujemy użyć wielojęzycznego modelu embeddingowego i uwzględniać dostępne wersje abstraktu.

DOI występuje w ponad połowie publikacji. Każde wystąpienie autora ma identyfikator, natomiast stabilne identyfikatory ORCID i uuid są dostępne tylko dla części osób. Dlatego przy łączeniu autorów nie będziemy opierać się wyłącznie na imieniu i nazwisku.

Informacja o otwartym dostępie nie jest prostą wartością „tak” lub „nie”. W większości sprawdzonych rekordów pole było puste, a w pozostałych zawierało między innymi licencję i wersję tekstu. Nie będziemy więc opierać odpowiedzi na tym polu.

### Ocena jakości

Każdy rekord ma tytuł, słowa kluczowe i listę autorów. Abstraktu brakuje w 601 rekordach. Dla takich publikacji wektor utworzymy na podstawie tytułu i słów kluczowych.

W 161 rekordach rok znajduje się poza zakresem 1900–2026; pojawiają się tam między innymi wartości −1 i 2916. Mimo że jest to niewielka część zbioru, takie wartości mogłyby zniekształcić analizę zmian w czasie. Pominiemy je przy liczeniu trendów, ale pozostawimy same publikacje w bazie.

To samo imię i nazwisko przy więcej niż jednym ORCID występuje dla 3 411 nazw. Scalanie po samym nazwisku połączyłoby różne osoby. Profil pokazuje dopasowane identyfikatory i ich prace.

Na podstawie tej analizy zakładamy, że dane pozwolą wyszukiwać publikacje po treści, wyznaczać kierunki badawcze i porównywać ich liczebność w kolejnych latach.

### Plan przygotowania wektorów

Początkowo do jednorazowego policzenia wektorów braliśmy pod uwagę klaster wydziałowy. To zadanie jest jednak niezależne od późniejszego działania aplikacji, dlatego planujemy wykonać je w sesji Kaggle na dwóch kartach NVIDIA T4. Gotowe pliki pobierzemy na komputer autorów i wykorzystamy w lokalnym wyszukiwaniu.

Model bge-m3 będzie pracował równolegle na obu kartach w trybie FP16, który zmniejsza zużycie pamięci i skraca czas obliczeń. Zapiszemy użyte parametry oraz czas wykonania, aby proces można było później powtórzyć. Kaggle posłuży tylko do przygotowania danych i nie będzie potrzebny podczas korzystania z aplikacji.

Wynik podzielimy na pliki obejmujące po 10 000 publikacji. Każdy plik z wektorami będzie miał odpowiadającą mu listę identyfikatorów, dzięki czemu połączymy wynik z właściwymi rekordami. W metadanych zapiszemy nazwę modelu, wymiar wektora, sposób porównywania, limit tekstu, liczbę rekordów i czas wykonania. Po zakończeniu sprawdzimy kompletność plików i poprawność wektorów. Następnie wykonamy testowe wyszukiwania po polsku i angielsku, aby ocenić, czy oczekiwane publikacje pojawiają się wysoko na liście wyników.

Akceptacja promotora: .................................................. Data: 05.11.2026
