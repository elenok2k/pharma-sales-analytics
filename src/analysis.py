import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

encodings_to_try = ['cp1251', 'utf-8-sig', 'latin-1', 'cp866']

for enc in encodings_to_try:
    try:
        df_sales = pd.read_csv(
            'dannye_dlya_analiza.csv',
            delimiter=';',
            thousands=' ',
            encoding=enc,
            dtype={'product_id': str}
        )
        print(f"✅ Файл загружен в кодировке: {enc}")
        break
    except (UnicodeDecodeError, UnicodeError):
        continue
else:
    print("❌ Не удалось загрузить файл.")
    exit()

print(f"✅ Загружено строк: {len(df_sales):,}")

if len(df_sales.columns) == 1:
    col_name = df_sales.columns[0]
    df_sales = df_sales[col_name].str.split(';', expand=True)
    df_sales.columns = ['branch', 'region', 'product_id', 'quarter', 'sell_month', 'amount']

df_sales['product_id'] = df_sales['product_id'].astype(str).str.strip()
df_sales['amount'] = df_sales['amount'].astype(str).str.replace(' ', '').astype(float)
df_sales['sell_month'] = pd.to_numeric(df_sales['sell_month'], errors='coerce')
df_sales['quarter'] = pd.to_numeric(df_sales['quarter'], errors='coerce')

print(f"✅ Данные готовы: {len(df_sales):,} записей")

df_prices = pd.read_excel('spravochnik_ceny.xlsx')
df_prices['ID препарата'] = df_prices['ID препарата'].astype(str).str.strip()

df_products = pd.read_excel('spravochnik_po_preparatam.xlsx')
df_products['ID препарата'] = df_products['ID препарата'].astype(str).str.strip()
df_products['Период выхода'] = pd.to_datetime(df_products['Период выхода'], errors='coerce')

print(f"✅ Загружено цен: {len(df_prices)} записей")
print(f"✅ Загружено препаратов: {len(df_products)} записей")

df = df_sales.merge(df_prices, left_on='product_id', right_on='ID препарата', how='left')
df = df.merge(df_products, left_on='product_id', right_on='ID препарата', how='left')

null_prices = df['Цена'].isna().sum()
if null_prices > 0:
    print(f"⚠️ Записей без цены: {null_prices} (заполнены 0)")
    df['Цена'] = df['Цена'].fillna(0)


df['Выручка'] = df['amount'] * df['Цена']


df['Год'] = 2025

def calculate_age(row):
    if pd.isna(row['Период выхода']):
        return 0
    try:
        sale_date = datetime(2025, int(row['sell_month']), 1)
        years = (sale_date - row['Период выхода']).days / 365.25
        return round(years, 1)
    except:
        return 0

df['Возраст_препарата'] = df.apply(calculate_age, axis=1)

df['Категория'] = 'Зрелые (более 2 лет)'
df.loc[df['Возраст_препарата'] <= 0.5, 'Категория'] = 'Новинки (до 6 мес.)'
df.loc[(df['Возраст_препарата'] > 0.5) & (df['Возраст_препарата'] <= 2), 'Категория'] = 'Активно растущие (6-24 мес.)'

total_revenue = df['Выручка'].sum()
new_share = (df[df['Категория']=='Новинки (до 6 мес.)']['Выручка'].sum() / total_revenue * 100) if total_revenue > 0 else 0

print("\n" + "="*60)
print("АГРЕГАЦИЯ ДАННЫХ")
print("="*60)

quarterly = df.groupby(['Год', 'quarter']).agg({
    'Выручка': 'sum',
    'amount': 'sum'
}).reset_index()

all_products = df.groupby('Наименование КП').agg({
    'Выручка': 'sum',
    'amount': 'sum',
        'Категория': lambda x: x.mode()[0] if len(x) > 0 else 'Зрелые' 
}).sort_values('Выручка', ascending=False).reset_index()

all_products['Доля_%'] = (all_products['Выручка'] / total_revenue * 100).round(2)
all_products['Накопленная_доля_%'] = all_products['Доля_%'].cumsum().round(2)

def abc_category(row):
    if row['Накопленная_доля_%'] <= 80:
        return 'A'
    elif row['Накопленная_доля_%'] <= 95:
        return 'B'
    else:
        return 'C'

all_products['ABC'] = all_products.apply(abc_category, axis=1)

top_products = all_products.head(10).copy()

all_regions = df.groupby('branch').agg({
    'Выручка': 'sum',
    'amount': 'sum'
}).sort_values('Выручка', ascending=False).reset_index()
all_regions['Доля_%'] = (all_regions['Выручка'] / total_revenue * 100).round(2)

regional_top = all_regions.head(10).copy()

category_stats = df.groupby('Категория').agg({
    'Выручка': 'sum'
}).reset_index()
category_stats['Доля_%'] = (category_stats['Выручка'] / total_revenue * 100).round(2)

q1 = quarterly[quarterly['quarter'] == 1]['Выручка'].sum()
q2 = quarterly[quarterly['quarter'] == 2]['Выручка'].sum()
q3 = quarterly[quarterly['quarter'] == 3]['Выручка'].sum()
q4 = quarterly[quarterly['quarter'] == 4]['Выручка'].sum()

if q1 > 0 and q2 > 0 and q3 > 0 and q4 > 0:
    growth_1_2 = q2 / q1
    growth_2_3 = q3 / q2
    growth_3_4 = q4 / q3
    avg_growth = (growth_1_2 + growth_2_3 + growth_3_4) / 3
    
    forecast_base = q4 * avg_growth
    forecast_pessimistic = q4 * (avg_growth - 0.05)
    forecast_optimistic = q4 * (avg_growth + 0.05)
    
    print(f"\n📊 Квартальная динамика:")
    print(f"   Q1→Q2: {growth_1_2:.1%}")
    print(f"   Q2→Q3: {growth_2_3:.1%}")
    print(f"   Q3→Q4: {growth_3_4:.1%}")
    print(f"   Средний рост: {avg_growth:.1%}")
    
    print(f"\n🔮 Прогноз Q1 2026:")
    print(f"   Базовый: {forecast_base:,.0f} руб.")
    print(f"   Диапазон: {forecast_pessimistic:,.0f} - {forecast_optimistic:,.0f} руб.")
else:
    print("⚠️ Недостаточно данных для прогноза")
    forecast_base = quarterly['Выручка'].mean() * 1.05
    forecast_pessimistic = forecast_base * 0.9
    forecast_optimistic = forecast_base * 1.1


# Настройка стиля
sns.set_style("whitegrid")
plt.rcParams['font.size'] = 10

# Создаём фигуру с 4 графиками (2x2)
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('ДАШБОРД: ЭФФЕКТИВНОСТЬ ПРОДАЖ ЛЕКАРСТВЕННЫХ ПРЕПАРАТОВ', 
             fontsize=20, fontweight='bold', y=0.98)




# ---- ГРАФИК 1: Динамика выручки ----
ax1 = axes[0, 0]
if len(quarterly) > 0:
    quarterly_sorted = quarterly.sort_values(['Год', 'quarter'])
    labels = [f"Q{row['quarter']} {row['Год']}" for _, row in quarterly_sorted.iterrows()]
    values = quarterly_sorted['Выручка'] / 1_000_000
    ax1.plot(labels, values, marker='o', linewidth=2, markersize=8, color='#2E86C1')
    ax1.set_title('Динамика выручки по кварталам (млн руб.)', fontsize=13, fontweight='bold')
    ax1.set_xlabel('Квартал')
    ax1.set_ylabel('Выручка, млн руб.')
    ax1.grid(True, alpha=0.3)
    ax1.axvline(x=len(labels)-0.5, color='red', linestyle='--', alpha=0.5, linewidth=2, label='Прогноз Q1 2026')
    ax1.legend(loc='upper left')

# ---- ГРАФИК 2: Топ-10 препаратов ----
ax2 = axes[0, 1]
if len(top_products) > 0:
    top_plot = top_products.sort_values('Выручка', ascending=True)
    ax2.barh(top_plot['Наименование КП'], top_plot['Выручка'] / 1_000_000, color='#28B463')
    ax2.set_title('Топ-10 препаратов по выручке', fontsize=13, fontweight='bold')
    ax2.set_xlabel('Выручка, млн руб.')
    ax2.set_ylabel('Препарат')
    ax2.tick_params(axis='y', labelsize=8)
    
    for i, v in enumerate(top_plot['Выручка'] / 1_000_000):
        ax2.text(v + 1, i, f'{v:.1f} млн', va='center', fontsize=8)
    ax2.set_xlim(0, top_plot['Выручка'].max() / 1_000_000 * 1.15)

# ---- ГРАФИК 3: Топ-10 регионов ----
ax3 = axes[1, 0]
if len(regional_top) > 0:
    regional_plot = regional_top.sort_values('Выручка', ascending=True)
    ax3.barh(regional_plot['branch'], regional_plot['Выручка'] / 1_000_000, color='#D4AC0D')
    ax3.set_title('Топ-10 регионов по выручке (млн руб.)', fontsize=13, fontweight='bold')
    ax3.set_xlabel('Выручка, млн руб.')
    ax3.set_ylabel('Регион')
    ax3.tick_params(axis='y', labelsize=8)
    
    for i, v in enumerate(regional_plot['Выручка'] / 1_000_000):
        ax3.text(v + 1, i, f'{v:.1f} млн', va='center', fontsize=8)

# ---- ГРАФИК 4: Категории (пирог) ----
ax4 = axes[1, 1]
if len(category_stats) > 0:
    colors = ['#E74C3C', '#F39C12', '#2E86C1']
    wedges, texts, autotexts = ax4.pie(
        category_stats['Выручка'],
        labels=category_stats['Категория'],
        autopct='%1.1f%%',
        colors=colors,
        startangle=90
    )
    ax4.set_title('Распределение выручки по возрасту препаратов', fontsize=13, fontweight='bold')
    legend_text = f"Всего: {total_revenue/1_000_000:.1f} млн руб."
    ax4.text(1.5, 0.5, legend_text, fontsize=11, bbox=dict(boxstyle="round", facecolor="wheat"))

# Настройка отступов
plt.tight_layout()
plt.subplots_adjust(top=0.88)  # Оставляем место для KPI текста
plt.savefig('dashboard.png', dpi=300, bbox_inches='tight')
print("✅ Дашборд с KPI-текстом сохранен как 'dashboard.png'")

try:
    with pd.ExcelWriter('pharma_analysis_report.xlsx', engine='openpyxl') as writer:
        
        df.head(10000).to_excel(writer, sheet_name='Данные_продаж_пример', index=False)
        quarterly.to_excel(writer, sheet_name='Квартальная_динамика', index=False)
        all_products.to_excel(writer, sheet_name='Все_препараты', index=False)
        top_products.to_excel(writer, sheet_name='Топ_препаратов', index=False)
        all_regions.to_excel(writer, sheet_name='Все_регионы', index=False)
        regional_top.to_excel(writer, sheet_name='Топ_регионов', index=False)
        
        # Динамика регионов
        quarterly_pivot = df.pivot_table(
            index='branch',
            columns=['Год', 'quarter'],
            values='Выручка',
            aggfunc='sum'
        ).fillna(0)
        quarterly_pivot.columns = [f'Q{q}_{g}' for g, q in quarterly_pivot.columns]
        quarters = sorted(quarterly_pivot.columns)
        if len(quarters) >= 2:
            last_q = quarters[-1]
            prev_q = quarters[-2]
            quarterly_pivot['Изменение_%'] = ((quarterly_pivot[last_q] - quarterly_pivot[prev_q]) / quarterly_pivot[prev_q] * 100).round(2)
            quarterly_pivot['Динамика'] = quarterly_pivot['Изменение_%'].apply(
                lambda x: '📈 Рост' if x > 0 else '📉 Падение' if x < 0 else '➖ Стабильно'
            )
            regions_dynamics = quarterly_pivot.sort_values('Изменение_%').reset_index()
            regions_dynamics.to_excel(writer, sheet_name='Динамика_регионов', index=False)
        
        # Прогноз (расширенный)
        forecast_df = pd.DataFrame({
            'Показатель': [
                'Q1 2025 (факт)',
                'Q2 2025 (факт)',
                'Q3 2025 (факт)',
                'Q4 2025 (факт)',
                'Средний темп роста',
                'Прогноз Q1 2026 (базовый)',
                'Прогноз Q1 2026 (пессимистичный)',
                'Прогноз Q1 2026 (оптимистичный)'
            ],
            'Значение': [
                f"{q1:,.0f}",
                f"{q2:,.0f}",
                f"{q3:,.0f}",
                f"{q4:,.0f}",
                f"{avg_growth:.1%}",
                f"{forecast_base:,.0f}",
                f"{forecast_pessimistic:,.0f}",
                f"{forecast_optimistic:,.0f}"
            ]
        })
        forecast_df.to_excel(writer, sheet_name='Прогноз', index=False)
        
        category_stats.to_excel(writer, sheet_name='Категории', index=False)
        
        summary_stats = pd.DataFrame({
            'Показатель': [
                'Общая выручка (руб.)',
                'Всего продано упаковок',
                'Средняя цена (руб.)',
                'Количество уникальных препаратов',
                'Количество регионов',
                'Доля новинок (%)',
                'Прогноз Q1 2026 (базовый)',
                'Количество препаратов с нулевыми продажами'
            ],
            'Значение': [
                f"{total_revenue:,.0f}",
                f"{df['amount'].sum():,.0f}",
                f"{df['Цена'].mean():.2f}",
                f"{df['product_id'].nunique()}",
                f"{df['branch'].nunique()}",
                f"{new_share:.1f}",
                f"{forecast_base:,.0f}",
                f"{len(all_products[all_products['Выручка'] == 0])}"
            ]
        })
        summary_stats.to_excel(writer, sheet_name='Сводка', index=False)
        
    print("✅ Отчет сохранен как 'pharma_analysis_report.xlsx'")
    
except Exception as e:
    print(f"⚠️ Ошибка: {e}")

print(f"""
📌 КЛЮЧЕВЫЕ ВЫВОДЫ:
1. Год: 2025 (все данные)
2. Общая выручка: {total_revenue:,.0f} руб.
3. Всего продано: {df['amount'].sum():,.0f} упаковок
4. Средняя цена: {df['Цена'].mean():.2f} руб.
5. Уникальных препаратов: {df['product_id'].nunique()}
6. Регионов: {df['branch'].nunique()}
7. Доля новинок (до 6 мес.): {new_share:.1f}%
8. Прогноз Q1 2026: {forecast_base:,.0f} руб.
   Диапазон: {forecast_pessimistic:,.0f} - {forecast_optimistic:,.0f} руб.
""")

