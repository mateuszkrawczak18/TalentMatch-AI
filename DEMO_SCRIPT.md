# 🎬 TalentMatch AI – Scenariusz Prezentacji (Demo Script)

## 📋 Setup (Wymagane przed startem)

### 1. Inicjalizacja Pełnego Pipeline'u (Terminal):

Aby zaprezentować pełną funkcjonalność (od struktury bazy, przez ETL, aż po AI Agentów), uruchom skrypty w tej kolejności:

```bash
# KROK 0: Reset bazy (Opcjonalne, w Neo4j Browser)
# Wejdź na http://localhost:7474 (Neo4j Browser)
# Wykonaj Cypher command:
# MATCH (n) DETACH DELETE n;

# KROK 1: Fundament Bazy (Constraints & Indexes)
# Tworzy strukturę, zapewnia unikalność ID i szybkie wyszukiwanie.
python 0_init_schema.py

# KROK 2: Generowanie Danych
# Tworzy 30 syntetycznych plików PDF z CV oraz fałszywe dane biznesowe.
python 1_generate_data.py

# KROK 3: ETL (Extract-Transform-Load) do Grafu
# LLM czyta PDFy i buduje węzły Person/Skill/Experience w Neo4j.
python 2_data_to_knowledge_graph.py

# KROK 4: Symulacja "Żywego" Biznesu
# Przypisuje ludzi do trwających projektów (Legacy/Maintenance).
# Dzięki temu część osób będzie zajęta (allocation < 1.0) - kluczowe dla demo dostępności.
python 2b_ingest_projects.py

# KROK 5: AI Headhunter (Real-time Matching)
# Automatyczny agent analizuje nowe pliki RFP i dobiera do nich zespoły.
python 3_match_team.py
```

### 2. Uruchom aplikację:

```bash
streamlit run app.py
```

Aplikacja pojawi się na `http://localhost:8501`

### 3. Przygotuj terminal dla Benchmarku:

W drugim oknie terminala/PowerShell bądź gotowy do uruchomienia:

```bash
cd benchmarks
python 5_compare_systems.py
```

---

## 🎤 Scenariusze Prezentacji

### 1️⃣ Wstęp (Dashboard & Storytelling)

**Pokaż Dashboard w przeglądarce:**

_"Cześć, to jest **TalentMatch AI**. Rozwiązujemy problem 'halucynacji' w HR. Zwykłe LLM-y zgadują, my sprawdzamy twarde fakty w bazie._

_Spójrzcie na liczby na górze – system widzi **30 pracowników**, z czego **~20 jest dostępnych**, a **średnia stawka to około $107/h**. To dane live z bazy grafowej Neo4j, aktualizowane w czasie rzeczywistym. Nie to statyczny tekst z CV, ale dynamiczny stan przedsiębiorstwa."_

---

### 2️⃣ Scenariusz 1: Dostępność (Business Logic)

**W pasku bocznym kliknij przycisk:**  
`👥 Check Availability`

_(Lub wpisz ręcznie: "Who is currently available?")_

**Komentarz:**

_"Zwykły RAG tutaj polegnie, bo w CV nie ma informacji o tym, co pracownik robi dzisiaj. Ktoś może być świetnym programistą, ale może być zajęty na innym projekcie._

_GraphRAG sprawdza relację `ASSIGNED_TO` w grafie. Widzi pracowników, którzy nie są przypisani do żadnego projektu. Ta lista to **twarde fakty biznesowe** – nie zgadywanie, tylko math na grafie. Zero halucynacji."_

---

### 3️⃣ Scenariusz 2: Złożona Rekrutacja (Complex Filtering)

**W pasku bocznym kliknij przycisk:**  
`🔗 Network Analysis`

_(Lub wpisz: "Who is assigned to 'FinTech AI Platform' AND 'Healthcare Portal'? List their names.")_

**Komentarz:**

_"Tu pytamy o ludzi przypisanych do **dwóch projektów naraz**. Zwykły model czasem się gubi w logice – nie wiadomo, czy szukamy AND czy OR._

_Nasz `bi_engine` rozumie pytanie i wie, że szukamy relacji. System widzi, że Tomek jest na obu projektach. To nie zgadywanie – to **logika biznesowa z walidacją typów** w Cypher."_

---

### 4️⃣ Scenariusz 3: Analiza Sieciowa (Multi-hop)

**W pasku bocznym kliknij przycisk:**  
`🔐 Relationship Analysis`

_(Lub wpisz: "Who has worked with Jacob Young in the past?")_

**Komentarz:**

_"To jest **GraphRAG w czystej postaci**. Szukamy powiązań między ludźmi._

_System zna historię projektów (węzły `Project`, `Company`), które Jakub i inni robili razem. To kluczowe przy budowaniu **zgranych zespołów** – możemy unikać konfliktów lub celowo łączyć sprawdzone pary, które już pracowały razem i dobrze się znają."_

---

### 5️⃣ Scenariusz 4: Precyzyjna Agregacja (Structured Data)

**W pasku bocznym kliknij przycisk:**  
`💰 Senior Developer Rates`

_(Lub wpisz: "What is the average hourly rate of Senior Python Developers?")_

**Komentarz:**

_"LLM-y są słabe w matematyce. Mogą zmyślić: '$115.43, ale nie jestem pewny'._

_My delegujemy obliczenia do bazy danych. Wynik (np. $114.24) jest wyliczony **co do centa** z aktualnych stawek zapisanych jako atrybuty węzłów w grafie. To 100% precyzji."_

---

### 6️⃣ Finał: Dowód Wyższości (Benchmark)

**Przełącz się na terminal i uruchom:**

```bash
python benchmarks/5_compare_systems.py
```

**Komentarz:**

_"Na koniec **twardy dowód**. Porównuję mój system (GraphRAG) z klasycznym Vector RAG na ChromaDB:_

**Scenario 1 - Średnia stawka:**

- GraphRAG podaje dokładną średnią ($107.40)
- Naive RAG zgaduje lub mówi 'I don't know'

**Scenario 3 - Relacje:**

- GraphRAG widzi powiązania między ludźmi (traversal)
- Naive RAG mówi 'Nie mogę tego sprawdzić'

**Wyniki:**

- GraphRAG: **100% accuracy** na zapytaniach biznesowych
- Naive RAG: ~40% accuracy (halucynuje, myli się na filtrowaniu)

_To jest **Graph beats Vectors** – nie z ideologii, ale z faktów."_

---

### 7️⃣ (Opcjonalnie) Stress Test & Scalability

Jeśli starczy czasu i chcesz zaprezentować wydajność:

```bash
python benchmarks/6_stress_test_scalability.py
```

_"Mamy też testy obciążeniowe – system skaluje się do 600+ węzłów (osób), obsługując 500+ concurrent zapytań z latencją <3s. To jest enterprise-grade."_

---

### 8️⃣ (Opcjonalnie) Database Cleanup Demo

Jeśli chcesz pokazać, że system łatwo się resetuje:

```bash
python benchmarks/8_cleanup_clones.py
```

_"Ten skrypt czyści bazę z duplikatów i przywraca stan demo jednym klikiem. Gotowe do następnego demo za 30 sekund."_

---

## ✅ Koniec Prezentacji

**Podsumowanie:**

_"TalentMatch AI to dowód, że **Graph beats Vectors** w aplikacjach biznesowych wymagających:_

- _Relacji (kto pracował z kim)_
- _Stanów (kto jest teraz dostępny)_
- _Logiki (AND/OR filtry)_
- _Precyzji (bez halucynacji)_

_Dziękuję za uwagę! Pytania?"_

---

## 🔧 Troubleshooting During Demo

| Problem                            | Rozwiązanie                                                                 |
| ---------------------------------- | --------------------------------------------------------------------------- |
| Neo4j nie łączy się                | Sprawdź: `docker-compose ps`. Jeśli neo4j pada, `docker-compose logs neo4j` |
| Aplikacja Streamlit czasami zawisa | Refresh strony (F5). System wysyła długie zapytania do Azure.               |
| API zwraca błąd auth               | Sprawdź `.env`: `AZURE_OPENAI_API_KEY` musi być ważny.                      |
| Benchmark timeout                  | Jeśli Neo4j jest powolny, pomiń stress test (benchmark 6)                   |

---

## 📝 Notes for Presenter

- **Czas demo**: ~7-10 minut (bez deep-dive w kod)
- **Kluczowy moment**: Benchmark 5 – pokazanie precyzji vs halucynacji
- **Wyjaśnić publiczności**: Różnica między "I don't know" (RAG) a "Znam, bo to w grafie" (GraphRAG)
- **Bonus slide** (jeśli pytania): Pokaż Neo4j Browser (`http://localhost:7474`) – wizualizacja grafu jest piękna ✨
