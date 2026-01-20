import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Ustawienie stylu
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12})

# Ścieżka do pliku CSV (z Twoich logów)
csv_path = "benchmarks/ragas_evaluation_results.csv"

if not os.path.exists(csv_path):
    print("❌ Nie znaleziono pliku CSV. Uruchom najpierw skrypt 9.")
    exit()

# Wczytanie danych
df = pd.read_csv(csv_path)

# Obliczenie średnich dla każdego systemu
summary = df.groupby("System")[["faithfulness", "answer_relevancy", "context_precision"]].mean().reset_index()

# Przekształcenie danych do formatu "długiego" dla Seaborn
df_melted = summary.melt(id_vars="System", var_name="Metric", value_name="Score")

# Rysowanie wykresu
plt.figure(figsize=(10, 6))
chart = sns.barplot(
    data=df_melted, 
    x="Metric", 
    y="Score", 
    hue="System",
    palette=["#4F8BF9", "#FF9F33"] # Niebieski dla GraphRAG, Pomarańczowy dla Naive
)

# Dodatki
plt.title("GraphRAG vs Naive RAG: Performance Comparison", fontsize=16, fontweight='bold', pad=20)
plt.ylim(0, 1.0)
plt.ylabel("Score (0-1)", fontsize=12)
plt.xlabel("")
plt.legend(title="Architecture")

# Dodanie wartości liczbowych nad słupkami
for container in chart.containers:
    chart.bar_label(container, fmt='%.2f', padding=3)

# Zapis
output_path = "benchmarks/final_comparison_chart.png"
plt.tight_layout()
plt.savefig(output_path, dpi=300)
print(f"✅ Wykres zapisano jako: {output_path}")
plt.show()