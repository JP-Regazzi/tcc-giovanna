"""
Interactive Plotly figures for education and debt analysis.

All plots are population-weighted (PESO_FINAL).
Labels and legends are in Portuguese; variable names remain in English.
Plots include p-values and statistical significance indicators where relevant.

This module replaces the older matplotlib-based plots.py for the thesis.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from .config import AnalysisConfig
from .statistics import WeightedStatistics, EducationDebtTests


class DescriptivePlotsPlotly:
    """Interactive descriptive figures using Plotly."""

    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.config.figures_dir.mkdir(parents=True, exist_ok=True)

    def _save_html(self, fig: go.Figure, filename: str) -> Path:
        """Save figure as interactive HTML."""
        path = self.config.figures_dir / filename.replace(".png", ".html")
        fig.write_html(str(path))
        return path

    @staticmethod
    def _wmean(values: pd.Series, weights: pd.Series) -> float:
        """Weighted mean."""
        v = pd.to_numeric(values, errors="coerce")
        w = pd.to_numeric(weights, errors="coerce")
        m = v.notna() & w.notna() & (w > 0)
        if not m.any():
            return np.nan
        return float(np.average(v[m], weights=w[m]))

    @staticmethod
    def _wstd(values: pd.Series, weights: pd.Series) -> float:
        """Weighted standard deviation."""
        v = pd.to_numeric(values, errors="coerce")
        w = pd.to_numeric(weights, errors="coerce")
        m = v.notna() & w.notna() & (w > 0)
        if not m.any():
            return np.nan
        vw = v[m]
        ww = w[m]
        mean = np.average(vw, weights=ww)
        variance = np.average((vw - mean) ** 2, weights=ww)
        return float(np.sqrt(variance))

    def _by_band(self, df: pd.DataFrame, value_col: str) -> Dict[str, float]:
        """Weighted mean of value_col per education band."""
        _, labels = self.config.education_band_spec()
        out = {}
        for band in labels:
            sub = df[df["education_band"] == band]
            out[band] = self._wmean(sub[value_col], sub["weight"]) if len(sub) else np.nan
        return out

    def _by_band_std(self, df: pd.DataFrame, value_col: str) -> Dict[str, float]:
        """Weighted std of value_col per education band."""
        _, labels = self.config.education_band_spec()
        out = {}
        for band in labels:
            sub = df[df["education_band"] == band]
            out[band] = self._wstd(sub[value_col], sub["weight"]) if len(sub) else np.nan
        return out

    def _by_band_percentiles(self, df: pd.DataFrame, value_col: str, p_lower: float = 25, p_upper: float = 75) -> tuple:
        """Weighted percentiles of value_col per education band. Returns (lower_dict, upper_dict)."""
        _, labels = self.config.education_band_spec()
        lower_out, upper_out = {}, {}
        for band in labels:
            sub = df[df["education_band"] == band]
            if len(sub) == 0:
                lower_out[band] = np.nan
                upper_out[band] = np.nan
            else:
                v = pd.to_numeric(sub[value_col], errors="coerce")
                w = pd.to_numeric(sub["weight"], errors="coerce")
                m = v.notna() & w.notna() & (w > 0)
                if not m.any():
                    lower_out[band] = np.nan
                    upper_out[band] = np.nan
                else:
                    vv = v[m].values
                    ww = w[m].values
                    # Sort by value
                    sorted_idx = np.argsort(vv)
                    vv_sorted = vv[sorted_idx]
                    ww_sorted = ww[sorted_idx]
                    # Compute cumulative weight
                    cum_weight = np.cumsum(ww_sorted)
                    cum_weight_norm = cum_weight / cum_weight[-1]
                    # Find percentiles
                    lower_out[band] = float(np.interp(p_lower / 100, cum_weight_norm, vv_sorted))
                    upper_out[band] = float(np.interp(p_upper / 100, cum_weight_norm, vv_sorted))
        return lower_out, upper_out

    def _share_with_debt(self, df: pd.DataFrame) -> Dict[str, float]:
        """% with debt per education band."""
        _, labels = self.config.education_band_spec()
        out = {}
        for band in labels:
            sub = df[df["education_band"] == band]
            out[band] = self._wmean(sub["has_debt"], sub["weight"]) * 100 if len(sub) else np.nan
        return out

    def income_by_education(
        self, df: pd.DataFrame, save: bool = True, show_stats: bool = True
    ) -> go.Figure:
        """
        Renda mensal por nível de escolaridade.
        Bar chart with percentile error bars (P25, P75) and statistical test.
        """
        _, labels = self.config.education_band_spec()
        means = self._by_band(df, "household_income")
        p25s, p75s = self._by_band_percentiles(df, "household_income", p_lower=25, p_upper=75)

        bands_plot = [b for b in labels if not np.isnan(means.get(b, np.nan))]
        values = [means[b] for b in bands_plot]
        # Error bars: distance from mean to percentile
        lower_errors = [means[b] - p25s[b] for b in bands_plot]
        upper_errors = [p75s[b] - means[b] for b in bands_plot]

        # Statistical test
        stats_result = {}
        if show_stats:
            tester = EducationDebtTests(df)
            stats_result = tester.test_income_by_education(labels)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bands_plot,
            y=values,
            error_y=dict(
                type="data",
                symmetric=False,
                array=upper_errors,
                arrayminus=lower_errors,
                visible=True
            ),
            marker=dict(color="#2E86AB", line=dict(color="#1B3A5C", width=1.5)),
            text=[f"R$ {v:,.0f}" for v in values],
            textposition="outside",
            name="Renda",
        ))

        title = "Renda Mensal Média por Nível de Escolaridade"
        if show_stats and "p_value" in stats_result:
            p_val = stats_result["p_value"]
            sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "ns"))
            title += f"<br><sub>ANOVA: p={p_val:.4f} {sig}</sub>"

        fig.update_layout(
            title=title,
            xaxis_title="Nível de Escolaridade",
            yaxis_title="Renda Mensal (R$)",
            hovermode="x unified",
            template="plotly_white",
            height=500,
            font=dict(size=12),
            showlegend=False,
        )

        if save:
            self._save_html(fig, "income_by_education.png")
        return fig

    def debt_spending_by_education(
        self, df: pd.DataFrame, save: bool = True
    ) -> go.Figure:
        """
        Gasto anual em empréstimo por nível de escolaridade (all UCs, including zeros).
        Uses percentile bars (P25, P75) instead of standard deviation.
        """
        _, labels = self.config.education_band_spec()
        means = self._by_band(df, "total_debt")
        p25s, p75s = self._by_band_percentiles(df, "total_debt", p_lower=25, p_upper=75)

        bands_plot = [b for b in labels if not np.isnan(means.get(b, np.nan))]
        values = [means[b] for b in bands_plot]
        lower_errors = [means[b] - p25s[b] for b in bands_plot]
        upper_errors = [p75s[b] - means[b] for b in bands_plot]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bands_plot,
            y=values,
            error_y=dict(
                type="data",
                symmetric=False,
                array=upper_errors,
                arrayminus=lower_errors,
                visible=True
            ),
            marker=dict(color="#C1121F", line=dict(color="#800C0C", width=1.5)),
            text=[f"R$ {v:,.0f}" for v in values],
            textposition="outside",
            name="Gasto em Empréstimo",
        ))

        fig.update_layout(
            title="Gasto Médio Anual em Empréstimo por Nível de Escolaridade<br><sub>(toda população)</sub>",
            xaxis_title="Nível de Escolaridade",
            yaxis_title="Gasto Anual (R$)",
            hovermode="x unified",
            template="plotly_white",
            height=500,
            font=dict(size=12),
            showlegend=False,
        )

        if save:
            self._save_html(fig, "debt_spending_by_education.png")
        return fig

    def debt_burden_by_education(
        self, df: pd.DataFrame, save: bool = True, show_stats: bool = True
    ) -> go.Figure:
        """
        Gasto em empréstimo / Renda Total por nível de escolaridade.
        Shows mean debt/income ratio with percentile bars (P25, P75) and statistical significance.
        """
        _, labels = self.config.education_band_spec()
        means = self._by_band(df, "debt_to_income")
        p25s, p75s = self._by_band_percentiles(df, "debt_to_income", p_lower=25, p_upper=75)

        bands_plot = [b for b in labels if not np.isnan(means.get(b, np.nan))]
        values = [means[b] * 100 for b in bands_plot]  # as percentage
        lower_errors = [(means[b] - p25s[b]) * 100 for b in bands_plot]
        upper_errors = [(p75s[b] - means[b]) * 100 for b in bands_plot]

        # Statistical test
        stats_result = {}
        if show_stats:
            tester = EducationDebtTests(df)
            stats_result = tester.test_debt_burden_by_education(labels)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bands_plot,
            y=values,
            error_y=dict(
                type="data",
                symmetric=False,
                array=upper_errors,
                arrayminus=lower_errors,
                visible=True
            ),
            marker=dict(color="#F77F00", line=dict(color="#8B4513", width=1.5)),
            text=[f"{v:.2f}%" for v in values],
            textposition="outside",
            name="Debt-to-Income",
        ))

        title = "Proporção de Gasto em Empréstimo / Renda (Debt-to-Income)"
        if show_stats and "p_value" in stats_result:
            p_val = stats_result["p_value"]
            sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "ns"))
            title += f"<br><sub>Kruskal-Wallis: p={p_val:.4f} {sig}</sub>"

        fig.update_layout(
            title=title,
            xaxis_title="Nível de Escolaridade",
            yaxis_title="Debt-to-Income (%)",
            hovermode="x unified",
            template="plotly_white",
            height=500,
            font=dict(size=12),
            showlegend=False,
        )

        if save:
            self._save_html(fig, "debt_burden_by_education.png")
        return fig

    def debt_prevalence_by_education(
        self, df: pd.DataFrame, save: bool = True, show_stats: bool = True
    ) -> go.Figure:
        """
        Porcentagem de famílias com gasto em empréstimo por escolaridade.
        """
        _, labels = self.config.education_band_spec()
        prevalence = self._share_with_debt(df)

        bands_plot = [b for b in labels if not np.isnan(prevalence.get(b, np.nan))]
        values = [prevalence[b] for b in bands_plot]

        # Statistical test
        stats_result = {}
        if show_stats:
            tester = EducationDebtTests(df)
            stats_result = tester.test_debt_prevalence_by_education(labels)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bands_plot,
            y=values,
            marker=dict(color="#06A77D", line=dict(color="#054B2A", width=1.5)),
            text=[f"{v:.1f}%" for v in values],
            textposition="outside",
            name="Prevalência",
        ))

        title = "Porcentagem de Famílias com Gasto em Empréstimo"
        if show_stats and "p_value" in stats_result:
            p_val = stats_result["p_value"]
            sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "ns"))
            title += f"<br><sub>Teste do Qui-quadrado: p={p_val:.4f} {sig}</sub>"

        fig.update_layout(
            title=title,
            xaxis_title="Nível de Escolaridade",
            yaxis_title="% de Famílias",
            yaxis=dict(range=[0, 100]),
            hovermode="x unified",
            template="plotly_white",
            height=500,
            font=dict(size=12),
            showlegend=False,
        )

        if save:
            self._save_html(fig, "debt_prevalence_by_education.png")
        return fig

    def debt_distribution_debtors_only(
        self, df: pd.DataFrame, save: bool = True, show_stats: bool = True
    ) -> go.Figure:
        """
        Distribuição de gasto em empréstimo apenas entre famílias com dívida.
        Bar chart with percentile error bars (P25, P75).
        """
        df_debt = df[df["has_debt"] == 1].copy()

        _, labels = self.config.education_band_spec()
        bands_plot = []
        means = []
        lower_errors = []
        upper_errors = []

        for band in labels:
            sub = df_debt[df_debt["education_band"] == band]
            if len(sub) == 0:
                continue

            mean_val = self._wmean(sub["total_debt"], sub["weight"])

            # Calculate percentiles for this band
            v = pd.to_numeric(sub["total_debt"], errors="coerce")
            w = pd.to_numeric(sub["weight"], errors="coerce")
            m = v.notna() & w.notna() & (w > 0)

            if m.any():
                vv = v[m].values
                ww = w[m].values
                sorted_idx = np.argsort(vv)
                vv_sorted = vv[sorted_idx]
                ww_sorted = ww[sorted_idx]
                cum_weight = np.cumsum(ww_sorted)
                cum_weight_norm = cum_weight / cum_weight[-1]

                p25_val = float(np.interp(0.25, cum_weight_norm, vv_sorted))
                p75_val = float(np.interp(0.75, cum_weight_norm, vv_sorted))

                means.append(mean_val)
                lower_errors.append(mean_val - p25_val)
                upper_errors.append(p75_val - mean_val)
                bands_plot.append(band)

        # Statistical test
        stats_result = {}
        if show_stats:
            tester = EducationDebtTests(df)
            stats_result = tester.test_debt_volume_by_education(labels)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=bands_plot,
            y=means,
            error_y=dict(
                type="data",
                symmetric=False,
                array=upper_errors,
                arrayminus=lower_errors,
                visible=True
            ),
            marker=dict(color="#8338EC", line=dict(color="#4A1A7F", width=1.5)),
            text=[f"R$ {v:,.0f}" for v in means],
            textposition="outside",
            name="Gasto em Empréstimo",
        ))

        title = "Gasto Médio Anual em Empréstimo (Apenas Devedores)"
        if show_stats and "p_value" in stats_result:
            p_val = stats_result["p_value"]
            sig = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else "ns"))
            title += f"<br><sub>Kruskal-Wallis: p={p_val:.4f} {sig}</sub>"

        fig.update_layout(
            title=title,
            xaxis_title="Nível de Escolaridade",
            yaxis_title="Gasto Anual (R$)",
            hovermode="x unified",
            template="plotly_white",
            height=500,
            font=dict(size=12),
            showlegend=False,
        )

        if save:
            self._save_html(fig, "debt_distribution_debtors_only.png")
        return fig

    def income_debt_scatter_by_education(
        self, df: pd.DataFrame, save: bool = True
    ) -> go.Figure:
        """
        Scatter: renda vs gasto em empréstimo, colored by education band.
        Allows visual inspection of correlation structure.
        """
        _, labels = self.config.education_band_spec()
        color_map = {
            labels[0]: "#E74C3C",  # red
            labels[1]: "#F39C12",  # orange
            labels[2]: "#27AE60",  # green
            labels[3]: "#3498DB",  # blue
        }

        fig = go.Figure()

        for band in labels:
            sub = df[df["education_band"] == band]
            if len(sub) == 0:
                continue

            # Sample for readability (weighted sample)
            if len(sub) > 2000:
                sample_idx = np.random.choice(
                    len(sub), 2000, replace=False,
                    p=sub["weight"].values / sub["weight"].sum()
                )
                sub = sub.iloc[sample_idx].reset_index(drop=True)

            fig.add_trace(go.Scatter(
                x=sub["household_income"],
                y=sub["total_debt"],
                mode="markers",
                name=band,
                marker=dict(
                    size=4,
                    color=color_map.get(band, "#999999"),
                    opacity=0.5,
                    line=dict(width=0.5),
                ),
                text=[f"Renda: R$ {inc:,.0f}<br>Dívida: R$ {debt:,.0f}"
                      for inc, debt in zip(sub["household_income"], sub["total_debt"])],
                hovertemplate="%{text}<extra></extra>",
            ))

        fig.update_layout(
            title="Relação entre Renda e Gasto em Empréstimo por Escolaridade",
            xaxis_title="Renda Mensal (R$)",
            yaxis_title="Gasto Anual em Empréstimo (R$)",
            hovermode="closest",
            template="plotly_white",
            height=600,
            font=dict(size=12),
            xaxis=dict(type="log"),
            yaxis=dict(type="log"),
        )

        if save:
            self._save_html(fig, "income_debt_scatter_by_education.png")
        return fig

    def debt_ratio_distribution_by_education(
        self, df: pd.DataFrame, save: bool = True
    ) -> go.Figure:
        """
        Box plots of debt-to-income ratio distribution by education band.
        (Among all UCs, including zeros which compress toward 0.)
        """
        _, labels = self.config.education_band_spec()

        fig = go.Figure()

        for band in labels:
            sub = df[df["education_band"] == band]
            if len(sub) == 0:
                continue

            ratios = pd.to_numeric(sub["debt_to_income"], errors="coerce")
            ratios = ratios.dropna()

            fig.add_trace(go.Box(
                y=ratios * 100,
                name=band,
                boxmean="sd",
            ))

        fig.update_layout(
            title="Distribuição da Proporção de Gasto em Empréstimo por Escolaridade",
            yaxis_title="Debt-to-Income (%)",
            xaxis_title="Nível de Escolaridade",
            hovermode="closest",
            template="plotly_white",
            height=600,
            font=dict(size=12),
        )

        if save:
            self._save_html(fig, "debt_ratio_distribution_by_education.png")
        return fig

    def debt_ratio_distribution_by_education_no_outliers(
        self, df: pd.DataFrame, save: bool = True
    ) -> go.Figure:
        """
        Box plots of debt-to-income ratio by education band with outliers removed.
        Uses the 1.5*IQR rule: values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] are removed.
        """
        _, labels = self.config.education_band_spec()

        fig = go.Figure()

        for band in labels:
            sub = df[df["education_band"] == band]
            if len(sub) == 0:
                continue

            ratios = pd.to_numeric(sub["debt_to_income"], errors="coerce")
            ratios = ratios.dropna()

            if len(ratios) == 0:
                continue

            q1 = ratios.quantile(0.25)
            q3 = ratios.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            filtered_ratios = ratios[(ratios >= lower_bound) & (ratios <= upper_bound)]

            fig.add_trace(go.Box(
                y=filtered_ratios * 100,
                name=band,
                boxmean="sd",
            ))

        fig.update_layout(
            title="Distribuição da Proporção de Gasto em Empréstimo por Escolaridade<br><sub>(Outliers removidos: 1.5×IQR)</sub>",
            yaxis_title="Debt-to-Income (%)",
            xaxis_title="Nível de Escolaridade",
            hovermode="closest",
            template="plotly_white",
            height=600,
            font=dict(size=12),
        )

        if save:
            self._save_html(fig, "debt_ratio_distribution_by_education_no_outliers.png")
        return fig

    def summary_statistics_table(
        self, df: pd.DataFrame, save: bool = True
    ) -> pd.DataFrame:
        """
        Comprehensive summary table with all key statistics by education band.
        Includes n, means, prevalence, and statistical test results.
        """
        _, labels = self.config.education_band_spec()
        tester = EducationDebtTests(df)

        # Get summary
        summary = tester.summary_table(labels)

        # Add statistical tests
        test_income = tester.test_income_by_education(labels)
        test_burden = tester.test_debt_burden_by_education(labels)
        test_prevalence = tester.test_debt_prevalence_by_education(labels)
        test_volume = tester.test_debt_volume_by_education(labels)

        # Create test info row
        test_info = {
            "education_band": "Teste Estatístico",
            "n_uc_households": None,
            "mean_income_r": None,
            "pct_with_debt": None,
            "mean_debt_to_income": None,
            "mean_debt_debtors_r": None,
            "income_test_p": test_income.get("p_value"),
            "burden_test_p": test_burden.get("p_value"),
            "prevalence_test_p": test_prevalence.get("p_value"),
            "volume_test_p": test_volume.get("p_value"),
        }

        summary = pd.concat([summary, pd.DataFrame([test_info])], ignore_index=True)

        if save:
            path = self.config.outputs_dir / "summary_statistics.csv"
            summary.to_csv(path, index=False)

        return summary

    def comprehensive_dashboard(
        self, df: pd.DataFrame, save: bool = True
    ) -> go.Figure:
        """
        4-panel dashboard: income, prevalence, burden, volume (debtors).
        Single figure with subplots.
        """
        _, labels = self.config.education_band_spec()

        income_data = self._by_band(df, "household_income")
        prevalence_data = self._share_with_debt(df)
        burden_data = self._by_band(df, "debt_to_income")

        # Debtors only
        df_debt = df[df["has_debt"] == 1]
        volume_data = self._by_band(df_debt, "total_debt")

        bands_plot = [b for b in labels if not np.isnan(income_data.get(b, np.nan))]

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "Renda Mensal Média",
                "% com Gasto em Empréstimo",
                "Proporção Empréstimo/Renda",
                "Gasto Médio (Devedores)",
            ),
            specs=[[{}, {}], [{}, {}]],
        )

        colors = ["#2E86AB", "#06A77D", "#F77F00", "#8338EC"]

        # Panel 1: income
        fig.add_trace(
            go.Bar(x=bands_plot, y=[income_data[b] for b in bands_plot],
                   marker_color=colors[0], name="Renda", showlegend=False),
            row=1, col=1
        )

        # Panel 2: prevalence
        fig.add_trace(
            go.Bar(x=bands_plot, y=[prevalence_data[b] for b in bands_plot],
                   marker_color=colors[1], name="Prevalência", showlegend=False),
            row=1, col=2
        )

        # Panel 3: burden
        fig.add_trace(
            go.Bar(x=bands_plot, y=[burden_data[b] * 100 for b in bands_plot],
                   marker_color=colors[2], name="Burden", showlegend=False),
            row=2, col=1
        )

        # Panel 4: volume
        fig.add_trace(
            go.Bar(x=bands_plot, y=[volume_data[b] for b in bands_plot],
                   marker_color=colors[3], name="Volume", showlegend=False),
            row=2, col=2
        )

        fig.update_yaxes(title_text="R$", row=1, col=1)
        fig.update_yaxes(title_text="%", row=1, col=2)
        fig.update_yaxes(title_text="%", row=2, col=1)
        fig.update_yaxes(title_text="R$", row=2, col=2)

        fig.update_layout(
            title_text="Painel de Análise: Educação e Dívida em Empréstimos",
            height=800,
            template="plotly_white",
            font=dict(size=11),
        )

        if save:
            self._save_html(fig, "comprehensive_dashboard.png")
        return fig
