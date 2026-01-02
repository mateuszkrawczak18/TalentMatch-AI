# 🎬 TalentMatch AI – Scenariusz Prezentacji (Demo Script)

## 📋 Setup (Wymagane przed startem)

### 1. Przygotuj dane:
```bash
# Wyczyść bazę (jeśli reset_db.py istnieje)
python reset_db.py

# Uruchom pipeline generacji danych
python 1_generate_data.py             # Generuje 30 CV
python 2_data_to_knowledge_graph.py   # Wgrywa ludzi i stawki
python 2b_ingest_projects.py          # Zajmuje 10 osób (Legacy)
python 3_match_team.py                # 🚀 AUTOMAT: Obsadza nowe projekty RFP (~13 osób)
```


### 2. Uruchom aplikację:
```bash
streamlit run app.py
```

### 3. Przygotuj terminal:
Miej otwarty plik `5_compare_systems.py` w VS Code gotowy do uruchomienia.

---

## 🎤 Prezentacja

### 1️⃣ Wstęp (Dashboard & Storytelling)
**Pokaż Dashboard w przeglądarce:**

*"Cześć, to jest TalentMatch AI. System rozwiązuje problem 'ślepoty' zwykłych modeli LLM na stan firmy w czasie rzeczywistym.*

*Spójrzcie na liczby na górze – to nie są halucynacje. System widzi, że mamy **30 pracowników**, z czego **~20 jest dostępnych**, a **średnia stawka to około $107/h**. To dane prosto z bazy grafowej Neo4j, aktualizowane na żywo."*

---

### 2️⃣ Scenariusz 1: Dostępność (Availability Logic)
**W pasku bocznym kliknij przycisk:**  
`👥 Check Availability`

*(Lub wpisz ręcznie: "Who is currently available?")*

**Komentarz:**  
*"Zwykły RAG odpowiedziałby 'Nie wiem', bo w CV nie jest napisane, czy ktoś ma projekt **dzisiaj**.*

*GraphRAG sprawdza relację `ASSIGNED_TO` w grafie. Widzimy listę osób wolnych. To **100% pewna informacja biznesowa**, nie zgadywanie."*

---

### 3️⃣ Scenariusz 2: Precyzyjna Rekrutacja (Complex Matching)
**W pasku bocznym kliknij przycisk:**  
`🐍 Senior Python Devs`

*(Lub wpisz: "Find all Senior Python Developers with their rates.")*

**Komentarz:**  
*"System łączy tu dane **nieustrukturyzowane** (Seniority wywnioskowane z CV przez LLM) z **twardymi danymi** (Stawka godzinowa z bazy).*

*Zwraca gotową listę kandydatów z cenami, których możemy od razu zatrudnić. To niemożliwe w zwykłym vector search."*

---

### 4️⃣ Scenariusz 3: Analiza Sieciowa (Multi-hop Reasoning)
**W pasku bocznym kliknij przycisk:**  
`🔗 Network Analysis`

*(Lub wpisz: "Who has worked with Jacob Young in the past?")*

**Komentarz:**  
*"To jest **'GraphRAG' w czystej postaci**. Szukamy powiązań między ludźmi.*

*System wie, kto pracował z Jacobem, przechodząc przez węzły **Firm** lub **Projektów** w przeszłości. To kluczowe przy budowaniu **zgranych zespołów** – możemy unikać konfliktów lub celowo łączyć sprawdzone pary."*

---

### 5️⃣ Finał: Dowód Wyższości (Benchmark)
**Przełącz się na terminal i uruchom:**
```bash
python 5_compare_systems.py
```

**Komentarz:**  
*"Na koniec twardy dowód. Porównałem mój system (GraphRAG) z klasycznym Vector RAG:*

- **Scenario 1 (Average Rate):**  
  *GraphRAG podaje dokładną średnią (np. $107.40). Naive RAG zgaduje lub mówi 'I don't know'.*

- **Scenario 3 (Availability):**  
  *GraphRAG rozumie, że ludzie są zajęci/wolni na podstawie relacji `ASSIGNED_TO`. Naive RAG nie ma pojęcia o stanie projektów.*

*Jak widać w wynikach, GraphRAG osiąga **100% accuracy** na zapytaniach biznesowych, podczas gdy Vector RAG odpowiada poprawnie tylko w **~40% przypadków**."*

---

## ✅ Koniec

**Podsumowanie:**  
*"TalentMatch AI to dowód, że **Graph beats Vectors** w aplikacjach biznesowych wymagających relacji, stanów i logiki. Dziękuję za uwagę!"*