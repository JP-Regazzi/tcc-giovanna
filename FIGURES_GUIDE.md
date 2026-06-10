# Guia de Figuras Profissionais — TCC POF

## Overview

Este guia documenta como usar os novos gráficos em Plotly (`src/pof/plots_plotly.py`) 
e testes estatísticos (`src/pof/statistics.py`) para análise profissional de educação 
e dívida em empréstimos.

**Convenção importante:** Todo código em Python está em **inglês** (variáveis, 
funções, docstrings). Mas todos os **gráficos exibem texto em português** 
(títulos, eixos, legendas, p-valores).

## Executar o Notebook

```bash
pip install -r requirements.txt
jupyter lab main.ipynb    # ou run all cells
```

A seção 5.2 ("Interactive Plotly Figures with Statistical Tests") gera todos 
os gráficos automaticamente.

## Figuras Disponíveis

### 1. `income_by_education()` — Renda por Escolaridade
- **Mostra:** Renda mensal média por nível de educação com barras de erro
- **Teste estatístico:** ANOVA (p-value no título)
- **Salva em:** `figures/income_by_education.html`
- **Interpretação:** Se p < 0.05, renda diferencia significativamente entre 
  grupos de educação

### 2. `debt_spending_by_education()` — Gasto em Empréstimo
- **Mostra:** Gasto anual médio em empréstimo por educação (toda população)
- **Teste estatístico:** Nenhum (estatística descritiva)
- **Salva em:** `figures/debt_spending_by_education.html`
- **Interpretação:** Mostra o nível absoluto de endividamento, não relativo

### 3. `debt_burden_by_education()` — Proporção Empréstimo/Renda (Debt-to-Income)
- **Mostra:** Razão gasto/renda em percentual por educação
- **Teste estatístico:** Kruskal-Wallis (não-paramétrico; p-value no título)
- **Salva em:** `figures/debt_burden_by_education.html`
- **Interpretação:** **A figura mais importante.** Mostra se a educação está 
  relacionada ao ônus relativo da dívida. Se p < 0.05, o padrão é estatisticamente 
  significativo.

**Resultado esperado:** Famílias com MENOS educação têm maior debt-to-income 
(% maior da renda vai para pagar empréstimos).

### 4. `debt_prevalence_by_education()` — Porcentagem com Dívida
- **Mostra:** % de famílias com qualquer gasto em empréstimo por educação
- **Teste estatístico:** Chi-quadrado (p-value no título)
- **Salva em:** `figures/debt_prevalence_by_education.html`
- **Interpretação:** Se prevalência não difere por educação (p > 0.05), não é 
  acesso que difere, mas carga relativa.

### 5. `debt_distribution_debtors_only()` — Gasto entre Devedores
- **Mostra:** Gasto médio anual em empréstimo apenas para UCs com dívida
- **Teste estatístico:** Kruskal-Wallis (p-value no título)
- **Salva em:** `figures/debt_distribution_debtors_only.html`
- **Interpretação:** Compara QUANTIDADE de empréstimo entre educação, excluindo 
  zeros. Se flat (p > 0.05), menos educados pegam empréstimos similares em tamanho 
  mas carregam proporcionalmente mais (porque ganham menos).

### 6. `income_debt_scatter_by_education()` — Scatter: Renda vs Dívida
- **Mostra:** Scatter plot com renda no eixo X, gasto em Y, cores por educação
- **Teste estatístico:** Nenhum
- **Salva em:** `figures/income_debt_scatter_by_education.html`
- **Interpretação:** Mostra a relação bivariada. Escala log-log para melhor 
  visualização. Permite identificar outliers e padrões não-lineares.

### 7. `debt_ratio_distribution_by_education()` — Box Plots da Razão
- **Mostra:** Box plots (25º, mediana, 75º percentil, outliers) de debt-to-income 
  por educação
- **Teste estatístico:** Nenhum
- **Salva em:** `figures/debt_ratio_distribution_by_education.html`
- **Interpretação:** Mostra dispersão completa, não apenas médias. Útil para 
  relatórios complementares sobre desigualdade (IQR, assimetria).

### 8. `comprehensive_dashboard()` — Painel 4-em-1
- **Mostra:** 4 painéis: renda, prevalência, burden, volume (devedores)
- **Teste estatístico:** Nenhum individual (use as figuras acima para p-values)
- **Salva em:** `figures/comprehensive_dashboard.html`
- **Interpretação:** Visão geral para slides/apresentações. Resumo rápido de 
  4 dimensões.

### 9. `summary_statistics_table()` — Tabela Resumida com P-valores
- **Mostra:** CSV table com:
  - n (famílias ponderadas) por banda de educação
  - média de renda
  - % com dívida
  - debt-to-income médio
  - gasto médio entre devedores
  - **p-values de todos os 4 testes**
- **Salva em:** `outputs/summary_statistics.csv`
- **Interpretação:** Coloque esta tabela no apêndice da tese. Contém exatamente 
  o que os leitores precisam para reproducir / verificar.

## Testes Estatísticos

### Teste de Renda: ANOVA
```
H₀: Media[renda | educação_i] = Media[renda | educação_j] para todos i, j
H₁: Existe pelo menos um par com médias diferentes
Teste: ANOVA (análise de variância)
Resultado: F-statistic, p-value
Significância: p < 0.05 rejeita H₀
```

### Teste de Debt-to-Income: Kruskal-Wallis
```
H₀: Distribuição[d/i | educação_i] = Distribuição[d/i | educação_j] para todos i, j
H₁: Pelo menos uma distribuição difere
Teste: Kruskal-Wallis (não-paramétrico; não assume normalidade)
Razão: Debt-to-income é altamente skewned (assimétrico) e tem muitos zeros
Resultado: H-statistic, p-value
Significância: p < 0.05 rejeita H₀
```

### Teste de Prevalência: Chi-Quadrado
```
H₀: Proporção[com_dívida | educação_i] = Proporção[com_dívida | educação_j] 
    para todos i, j
H₁: Proporções diferem
Teste: Teste do χ² (chi-quadrado)
Resultado: χ²-statistic, p-value, graus de liberdade
Significância: p < 0.05 rejeita H₀
```

### Teste de Volume (Devedores): Kruskal-Wallis
```
(Mesma como debt-to-income, mas apenas entre UCs com dívida > 0)
```

## Como Interpretar P-valores

| p-value | Significância | Notação | Interpretação |
|---|---|---|---|
| p < 0.001 | *** | Altamente significante | Relação muito forte, praticamente certa |
| 0.001 ≤ p < 0.01 | ** | Muito significante | Relação forte, confiável |
| 0.01 ≤ p < 0.05 | * | Significante | Relação moderada, aceitável |
| p ≥ 0.05 | ns | Não significante | Sem evidência de relação |

## Fluxo Recomendado para o TCC

1. **Renda (income_by_education)** — Contextualize que educação varia com renda 
2. **Prevalência (debt_prevalence)** — Mostre que endividamento é similar entre 
   educação (não é apenas falta de acesso)
3. **Burden (debt_burden)** — A figura-chave: educação-menor = burden-maior 
   (estatisticamente significante)
4. **Volume (debt_distribution)** — Detalhe: empréstimos de tamanho similar, 
   mas burden diferente por causa da renda
5. **Scatter (income_debt_scatter)** — Mostra a relação bivariada e outliers
6. **Distribuição (debt_ratio_distribution)** — Para análise de desigualdade / 
   dispersão
7. **Dashboard (comprehensive_dashboard)** — Resumo visual para apresentações

## Checklist para Tese

- [ ] Tabela de resumo (summary_statistics.csv) no apêndice
- [ ] Todas 8 figuras Plotly inseridas ou referenciadas
- [ ] P-valores explicados na seção de metodologia/resultados
- [ ] Interpretação econômica de cada figura escrita
- [ ] Limitações dos testes (pesos complexos, não toda a variância de desenho) 
      documentadas
- [ ] Figuras com alta resolução (HTML interativo é profissional; salve PNGs 
      via screenshot se precisar estática)

## Reproduzibilidade

Todos os gráficos são **completamente reproduzíveis:**
1. Rode `main.ipynb` (todas as seções)
2. Gráficos em `figures/*.html` + CSV em `outputs/summary_statistics.csv`
3. Compare com seu git history se números mudarem (por mudança em parâmetros 
   de config)

## Troubleshooting

### Gráfico não aparece / erro de Plotly
- Certifique-se de ter instalado `plotly`: `pip install plotly>=5.0`
- Reinicie o kernel do Jupyter
- Se erro é "missing column", verificar se dataset foi construído (seção 4)

### P-valores muito altos (não significantes)
- Pode significar que a educação não afeta essa métrica
- Ou que a amostra é pequena (mas n=57k é grande)
- Verifique se aplicou filtros no config

### Cores diferentes entre runs
- Plotly escolhe cores aleatoriamente às vezes; código define cores explícitas 
  para cada figura, não deveria variar
- Se cores variam, pode indicar error em plotly_figs init

## Contato / Questões

Veja docs/04_architecture.md para estrutura dos módulos.
Código comentado está em src/pof/plots_plotly.py e src/pof/statistics.py.
